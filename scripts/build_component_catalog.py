#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
KINDS = ("backgrounds", "characters", "groups", "modules", "props")
MINIMUM_COUNTS = {"backgrounds": 1, "characters": 1, "groups": 1, "modules": 1, "props": 1}
DEFAULT_LAYERS = {
    "backgrounds": "stage",
    "characters": "subjectFront",
    "groups": "subjectFront",
    "modules": "rear",
    "props": "subjectFront",
}


def read_png_header(path: Path) -> tuple[int, int, bool]:
    with path.open("rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise ValueError(f"Not a PNG: {path}")
        length = struct.unpack(">I", handle.read(4))[0]
        if handle.read(4) != b"IHDR" or length != 13:
            raise ValueError(f"Missing PNG IHDR: {path}")
        width, height, _depth, color_type, _compression, _filter, _interlace = struct.unpack(
            ">IIBBBBB", handle.read(13)
        )
    return width, height, color_type in {4, 6}


def alpha_geometry(path: Path, width: int, height: int) -> tuple[int, int, dict[str, int]]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            "alphaextract",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    alpha = result.stdout
    if len(alpha) != width * height:
        raise ValueError(f"Empty alpha plane: {path}")
    visible = [index for index, value in enumerate(alpha) if value > 8]
    if not visible:
        raise ValueError(f"No visible pixels: {path}")
    left = min(index % width for index in visible)
    right = max(index % width for index in visible)
    top = min(index // width for index in visible)
    bottom = max(index // width for index in visible)
    return min(alpha), max(alpha), {
        "x": left,
        "y": top,
        "width": right - left + 1,
        "height": bottom - top + 1,
    }


def semantic_metadata(kind: str, relative: Path, bbox: dict[str, int] | None) -> dict[str, object]:
    stem = relative.stem
    parts = relative.parts
    category = parts[1] if len(parts) > 2 else stem
    tokens = {part for value in (category, stem) for part in value.split("-") if part}
    facing = "left" if "left" in tokens else "right" if "right" in tokens else "unspecified"
    interaction_tags = sorted(
        tokens
        & {
            "ask",
            "celebrate",
            "choose",
            "complain",
            "compare",
            "explain",
            "handoff",
            "hold",
            "inspect",
            "lift",
            "listen",
            "observe",
            "pay",
            "point",
            "present",
            "push",
            "react",
            "receive",
            "reject",
            "repair",
            "think",
            "wait",
            "walk",
            "work",
            "write",
        }
    )
    data: dict[str, object] = {
        "category": category,
        "variant": stem,
        "tags": sorted(tokens),
        "facing": facing,
        "interaction_tags": interaction_tags,
        "default_layer": DEFAULT_LAYERS[kind],
    }
    if bbox is not None:
        center_x = bbox["x"] + bbox["width"] / 2
        center_y = bbox["y"] + bbox["height"] / 2
        data["content_bbox"] = bbox
        data["anchors"] = {
            "center": {"x": round(center_x, 2), "y": round(center_y, 2)},
            "top": {"x": round(center_x, 2), "y": bbox["y"]},
            "baseline": {
                "x": round(center_x, 2),
                "y": bbox["y"] + bbox["height"] - 1,
            },
        }
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate the fixed collage component catalog.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets" / "component-library",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    output = (args.output or root / "catalog.json").resolve()
    entries: list[dict[str, object]] = []
    counts: dict[str, int] = {}

    for kind in KINDS:
        files = sorted((root / kind).rglob("*.png"))
        counts[kind] = len(files)
        if len(files) < MINIMUM_COUNTS[kind]:
            raise SystemExit(
                f"{kind}: expected at least {MINIMUM_COUNTS[kind]} PNGs, found {len(files)}"
            )

        for path in files:
            width, height, has_alpha = read_png_header(path)
            requires_alpha = kind != "backgrounds"
            if requires_alpha:
                if not has_alpha:
                    raise SystemExit(f"Missing alpha channel: {path}")
                alpha_min, alpha_max, content_bbox = alpha_geometry(path, width, height)
                if alpha_min != 0 or alpha_max < 254:
                    raise SystemExit(
                        f"Invalid alpha range for {path}: min={alpha_min}, max={alpha_max}"
                    )
            else:
                alpha_min = alpha_max = None
                content_bbox = None
                if height <= 0 or abs(width / height - 16 / 9) > 0.01:
                    raise SystemExit(f"Background must be 16:9: {path} is {width}x{height}")

            relative = path.relative_to(root)
            entry: dict[str, object] = {
                    "id": relative.with_suffix("").as_posix(),
                    "kind": kind,
                    "path": f"assets/component-library/{relative.as_posix()}",
                    "width": width,
                    "height": height,
                    "alpha_required": requires_alpha,
                    "alpha_min": alpha_min,
                    "alpha_max": alpha_max,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            entry.update(semantic_metadata(kind, relative, content_bbox))
            entries.append(entry)

    payload = {
        "schema_version": 1,
        "style_id": "house-paper-collage-v01",
        "counts": counts,
        "total": len(entries),
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output), "counts": counts, "total": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
