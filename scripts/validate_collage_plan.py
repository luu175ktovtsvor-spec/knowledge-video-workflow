#!/usr/bin/env python3
"""Validate the structure and referenced assets of a 2D collage video plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STYLE_ID = "fixed-2d-collage-knowledge-v1"
STATUS = {"planned", "assets-ready", "final"}
ASSET_ROLES = {"background", "character", "evidence", "group", "module", "prop", "foreground"}
LAYERS = {
    "stage",
    "rear",
    "subjectBack",
    "occluder",
    "subjectFront",
    "graphic",
    "keyword",
    "chapter",
    "transition",
    "titleCard",
    "caption",
}
ROLE_LAYERS = {
    "background": {"stage"},
    "character": {"subjectBack", "subjectFront"},
    "group": {"subjectBack", "subjectFront"},
    "module": {"rear", "occluder"},
    "prop": {"rear", "subjectBack", "subjectFront", "graphic"},
    "evidence": {"graphic"},
    "foreground": {"occluder", "transition"},
}
BEAT_KINDS = {"scene", "title-card"}
STAGE_MODES = {"scene", "diagram"}
ACTIONS = {
    "slide-fade",
    "pop-scale",
    "pose-swap",
    "prop-contact",
    "state-replace",
    "crop-reveal",
    "group-build",
    "foreground-wipe",
}
COMPONENT_MOTIONS = (ACTIONS - {"foreground-wipe"}) | {"hold", "exit"}
SEMANTIC_ROLES = {"subject", "action-object", "context", "result", "evidence"}
LAYOUT_MODES = {
    "stage-subject-object",
    "stage-two-party",
    "stage-center-build",
    "diagram-focus",
    "diagram-sequence",
}
ACTION_AXES = {"left-to-right", "right-to-left", "center-out", "top-to-bottom", "none"}
TRANSITIONS = {
    "hard-cut",
    "cross-fade",
    "blur-cut",
    "pose-swap",
    "foreground-wipe",
    "title-card",
}
def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def png_has_alpha(path: Path) -> bool:
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    color_type = data[25]
    return color_type in {4, 6} or b"tRNS" in data


def safe_project_path(root: Path, raw: object) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def signature(beat: dict[str, Any]) -> tuple[Any, ...]:
    states = tuple(
        sorted(
            (
                str(item.get("asset_id") or ""),
                str(item.get("state") or ""),
                str(item.get("placement") or ""),
            )
            for item in as_list(beat.get("subject_states"))
            if isinstance(item, dict)
        )
    )
    return (
        beat.get("stage_mode"),
        beat.get("background_id"),
        beat.get("composition"),
        states,
        tuple(sorted(str(value) for value in as_list(beat.get("prop_ids")))),
        tuple(sorted(str(value) for value in as_list(beat.get("code_graphics")))),
    )


def visual_component_ids(beat: dict[str, Any]) -> list[str]:
    values = [
        str(item.get("asset_id"))
        for item in as_list(beat.get("subject_states"))
        if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
    ]
    values.extend(str(value) for value in as_list(beat.get("prop_ids")))
    values.extend(str(value) for value in as_list(beat.get("code_graphics")))
    return values


def validate(data: Any, plan_path: Path, *, structural_only: bool = False) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["plan must be a JSON object"], {}
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("layer_contract_version") != 1:
        errors.append("layer_contract_version must be 1")
    if data.get("style_id") != STYLE_ID:
        errors.append(f"style_id must be {STYLE_ID}")
    status = data.get("status")
    if status not in STATUS:
        errors.append(f"status must be one of {sorted(STATUS)}")

    format_data = data.get("format") if isinstance(data.get("format"), dict) else {}
    width, height = format_data.get("width"), format_data.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        errors.append("format width and height must be positive integers")
    elif abs(width / height - 16 / 9) > 0.01:
        errors.append("format must use a 16:9 aspect ratio")
    fps = format_data.get("fps")
    if not isinstance(fps, (int, float)) or fps <= 0:
        errors.append("format.fps must be positive")
    duration_frames = format_data.get("duration_frames")
    if not isinstance(duration_frames, int) or duration_frames <= 0:
        errors.append("format.duration_frames must be a positive integer")
        duration_frames = 0

    narration = data.get("narration") if isinstance(data.get("narration"), dict) else {}
    target_rate = narration.get("target_chars_per_sec")
    if target_rate is not None and not (
        isinstance(target_rate, list)
        and len(target_rate) == 2
        and all(isinstance(value, (int, float)) and value > 0 for value in target_rate)
        and float(target_rate[0]) <= float(target_rate[1])
    ):
        errors.append("narration.target_chars_per_sec, when provided, must be an ascending positive range")

    assets = as_list(data.get("assets"))
    asset_map: dict[str, dict[str, Any]] = {}
    for index, asset in enumerate(assets):
        label = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label} must be an object")
            continue
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not asset_id:
            errors.append(f"{label}.id must be non-empty text")
            continue
        if asset_id in asset_map:
            errors.append(f"duplicate asset id: {asset_id}")
            continue
        asset_map[asset_id] = asset
        role = asset.get("role")
        if role not in ASSET_ROLES:
            errors.append(f"{label}.role must be one of {sorted(ASSET_ROLES)}")
        default_layer = asset.get("default_layer")
        if default_layer not in LAYERS:
            errors.append(f"{label}.default_layer must be one of {sorted(LAYERS)}")
        elif role in ROLE_LAYERS and default_layer not in ROLE_LAYERS[role]:
            errors.append(
                f"{label}.default_layer {default_layer!r} is invalid for role {role!r}; "
                f"expected one of {sorted(ROLE_LAYERS[role])}"
            )
        if asset.get("role") == "evidence":
            if not isinstance(asset.get("source_note"), str) or not str(asset.get("source_note")).strip():
                errors.append(f"{label}.source_note is required for evidence assets")
        raw_source = asset.get("source_ref")
        if not isinstance(raw_source, str) or not raw_source.startswith("public/"):
            errors.append(f"{label}.source_ref must be a project-relative public/ path")
        if status in {"assets-ready", "final"} and not structural_only:
            path = safe_project_path(plan_path.parent, raw_source)
            if path is None:
                errors.append(f"{label}.source_ref escapes the project or is invalid")
            elif not path.is_file() or path.stat().st_size <= 0:
                errors.append(f"{label}.source_ref is missing or empty: {raw_source}")
            elif asset.get("alpha_required") is True:
                if path.suffix.lower() != ".png" or not png_has_alpha(path):
                    errors.append(f"{label} requires a real-alpha PNG")

    beats = as_list(data.get("beats"))
    if not beats:
        errors.append("beats must be a non-empty list")
    expected_from = 0
    title_cards = 0
    scene_beats = 0
    signatures: list[tuple[Any, ...] | None] = []
    for index, beat in enumerate(beats):
        label = f"beats[{index}]"
        if not isinstance(beat, dict):
            errors.append(f"{label} must be an object")
            signatures.append(None)
            continue
        kind = beat.get("kind")
        if kind not in BEAT_KINDS:
            errors.append(f"{label}.kind must be scene or title-card")
        try:
            start = int(beat.get("from_frame"))
            beat_duration = int(beat.get("duration_frames"))
        except (TypeError, ValueError):
            errors.append(f"{label} needs integer from_frame/duration_frames")
            signatures.append(None)
            continue
        if start != expected_from:
            errors.append(f"{label}.from_frame must be {expected_from} for a continuous timeline")
        if beat_duration <= 0:
            errors.append(f"{label}.duration_frames must be positive")
        expected_from = start + max(beat_duration, 0)
        for field in ("id", "narration_anchor", "viewer_task", "composition", "transition_out"):
            if not isinstance(beat.get(field), str) or not str(beat.get(field)).strip():
                errors.append(f"{label}.{field} must be non-empty text")
        if beat.get("transition_out") not in TRANSITIONS:
            errors.append(f"{label}.transition_out must be one of {sorted(TRANSITIONS)}")
        events = as_list(beat.get("internal_events"))
        if not events:
            errors.append(f"{label}.internal_events must contain at least one information event")
        previous_event_frame = -1
        for event_index, event in enumerate(events):
            event_label = f"{label}.internal_events[{event_index}]"
            if not isinstance(event, dict):
                errors.append(f"{event_label} must be an object")
                continue
            at_frame = event.get("at_frame")
            if not isinstance(at_frame, int) or not 0 <= at_frame < beat_duration:
                errors.append(f"{event_label}.at_frame must fall inside the beat")
            elif at_frame < previous_event_frame:
                errors.append(f"{event_label}.at_frame must be ordered")
            else:
                previous_event_frame = at_frame
            if event.get("action") not in ACTIONS:
                errors.append(f"{event_label}.action must be one of {sorted(ACTIONS)}")
            for field in ("id", "target", "result"):
                if not isinstance(event.get(field), str) or not str(event.get(field)).strip():
                    errors.append(f"{event_label}.{field} must be non-empty text")

        if kind == "title-card":
            title_cards += 1
            if beat.get("background_id") is not None:
                errors.append(f"{label} title-card background_id must be null")
            if beat.get("stage_mode") is not None:
                errors.append(f"{label} title-card stage_mode must be null")
            if not isinstance(beat.get("title_text"), str) or not beat["title_text"].strip():
                errors.append(f"{label}.title_text is required for a title-card")
            signatures.append(None)
        elif kind == "scene":
            scene_beats += 1
            stage_mode = beat.get("stage_mode")
            if stage_mode not in STAGE_MODES:
                errors.append(f"{label}.stage_mode must be one of {sorted(STAGE_MODES)}")
            background_id = beat.get("background_id")
            if stage_mode == "scene":
                if background_id not in asset_map or asset_map.get(background_id, {}).get("role") != "background":
                    errors.append(f"{label}.background_id must reference a background asset in scene mode")
            elif stage_mode == "diagram" and background_id is not None:
                if background_id not in asset_map or asset_map.get(background_id, {}).get("role") != "background":
                    errors.append(f"{label}.background_id must be null or reference a background asset in diagram mode")
            subject_states = as_list(beat.get("subject_states"))
            prop_ids = [str(value) for value in as_list(beat.get("prop_ids"))]
            code_graphics = [str(value) for value in as_list(beat.get("code_graphics"))]
            if not subject_states and not prop_ids and not code_graphics:
                errors.append(f"{label} cannot be background-only")
            visual_contract = beat.get("visual_contract")
            if not isinstance(visual_contract, dict):
                errors.append(f"{label}.visual_contract must be an object")
            else:
                for field in ("start_state", "visible_action", "end_state"):
                    if not isinstance(visual_contract.get(field), str) or not str(visual_contract.get(field)).strip():
                        errors.append(f"{label}.visual_contract.{field} must be non-empty text")
                essential = as_list(visual_contract.get("essential_components"))
                if not essential or not all(isinstance(value, str) and value for value in essential):
                    errors.append(f"{label}.visual_contract.essential_components must contain component ids")
                elif len(essential) != len(set(essential)):
                    errors.append(f"{label}.visual_contract.essential_components must not contain duplicates")
                else:
                    used_components = visual_component_ids(beat)
                    if set(essential) != set(used_components):
                        errors.append(
                            f"{label}.visual_contract.essential_components must exactly match used components; "
                            f"expected {sorted(set(used_components))}"
                        )
                    primary = visual_contract.get("primary_component")
                    if primary not in essential:
                        errors.append(f"{label}.visual_contract.primary_component must reference an essential component")
                    if visual_contract.get("layout_mode") not in LAYOUT_MODES:
                        errors.append(f"{label}.visual_contract.layout_mode must be one of {sorted(LAYOUT_MODES)}")
                    if visual_contract.get("action_axis") not in ACTION_AXES:
                        errors.append(f"{label}.visual_contract.action_axis must be one of {sorted(ACTION_AXES)}")
                    bindings = visual_contract.get("component_bindings")
                    if not isinstance(bindings, dict) or set(bindings) != set(essential):
                        errors.append(f"{label}.visual_contract.component_bindings keys must exactly match essential components")
                    else:
                        for component_id, binding in bindings.items():
                            binding_label = f"{label}.visual_contract.component_bindings[{component_id!r}]"
                            if not isinstance(binding, dict):
                                errors.append(f"{binding_label} must be an object")
                                continue
                            if binding.get("role") not in SEMANTIC_ROLES:
                                errors.append(f"{binding_label}.role must be one of {sorted(SEMANTIC_ROLES)}")
                            if not isinstance(binding.get("phrase"), str) or not str(binding.get("phrase")).strip():
                                errors.append(f"{binding_label}.phrase must be non-empty text")
                            if binding.get("motion") not in COMPONENT_MOTIONS:
                                errors.append(f"{binding_label}.motion must be one of {sorted(COMPONENT_MOTIONS)}")
            for state_index, state in enumerate(subject_states):
                state_label = f"{label}.subject_states[{state_index}]"
                if not isinstance(state, dict):
                    errors.append(f"{state_label} must be an object")
                    continue
                asset_id = state.get("asset_id")
                if asset_id not in asset_map or asset_map.get(asset_id, {}).get("role") not in {"character", "group"}:
                    errors.append(f"{state_label}.asset_id must reference a character/group asset")
                for field in ("state", "placement"):
                    if not isinstance(state.get(field), str) or not str(state.get(field)).strip():
                        errors.append(f"{state_label}.{field} must be non-empty text")
            for prop_id in prop_ids:
                if prop_id not in asset_map or asset_map.get(prop_id, {}).get("role") not in {"evidence", "module", "prop", "foreground"}:
                    errors.append(f"{label}.prop_ids references an unknown evidence/module/prop/foreground asset: {prop_id}")
            subtitle = beat.get("subtitle")
            if subtitle is not None and not isinstance(subtitle, str):
                errors.append(f"{label}.subtitle must be text when provided")
            signatures.append(signature(beat))

    if duration_frames and expected_from != duration_frames:
        errors.append(f"beats end at {expected_from}, expected format.duration_frames {duration_frames}")
    for index in range(1, len(signatures)):
        if signatures[index] is None or signatures[index - 1] is None:
            continue
        if signatures[index] == signatures[index - 1]:
            errors.append(f"beats[{index}] repeats the previous visual composition; merge it or change the visible state")

    metrics = {
        "assets": len(asset_map),
        "beats": len(beats),
        "scene_beats": scene_beats,
        "title_cards": title_cards,
        "duration_frames": duration_frames,
        "duration_seconds": round(duration_frames / 30, 3) if duration_frames else 0,
    }
    return errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--structural-only", action="store_true")
    args = parser.parse_args()
    try:
        data = json.loads(args.plan.read_text(encoding="utf-8"))
        errors, metrics = validate(data, args.plan.resolve(), structural_only=args.structural_only)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "errors": [str(exc)], "metrics": {}}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok" if not errors else "invalid", "errors": errors, "metrics": metrics}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
