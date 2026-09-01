#!/usr/bin/env python3
"""Align approved narration text to ASR timing and build semantic Remotion captions."""

from __future__ import annotations

import argparse
import bisect
import difflib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALIGN_CHAR = re.compile(r"[\u3400-\u9fffA-Za-z0-9%]")
STRONG_PUNCTUATION = set("。！？!?；;\n")
TRAILING_DISPLAY_PUNCTUATION = "。；;，,：:、"
AUTOMATIC_PROTECTED = re.compile(
    r"(?:\d+(?:\.\d+)?%?)|(?:百分之[零〇一二三四五六七八九十百千万亿点两]+)|(?:[A-Za-z]+轮?)"
)


@dataclass
class TimedChar:
    char: str
    start: float
    end: float
    confidence: float | None


@dataclass
class Fragment:
    text: str
    start_index: int
    end_index: int
    strong_after: bool


def normalized_alignment_chars(text: str) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for index, original in enumerate(text):
        for char in unicodedata.normalize("NFKC", original):
            if ALIGN_CHAR.fullmatch(char):
                result.append((char.lower(), index))
    return result


def load_approved_script(path: Path) -> str:
    if path.suffix.lower() != ".json":
        return path.read_text(encoding="utf-8").strip()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        values = [str(item).strip() for item in data if str(item).strip()]
        return "\n\n".join(values)
    if not isinstance(data, dict):
        raise ValueError("approved script JSON must be an object, array, or string")
    segments = data.get("segments")
    if isinstance(segments, list):
        values = []
        for item in segments:
            if not isinstance(item, dict):
                continue
            value = item.get("spoken") or item.get("spoken_text") or item.get("text")
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        if values:
            return "\n\n".join(values)
    for key in ("spoken", "spoken_text", "text", "script"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("approved script JSON does not contain usable narration text")


def _timed_chars_from_text(text: str, start: float, end: float, confidence: float | None) -> list[TimedChar]:
    chars = [char for char, _ in normalized_alignment_chars(text)]
    if not chars:
        return []
    duration = max(end - start, 0.04 * len(chars))
    step = duration / len(chars)
    return [
        TimedChar(char=char, start=start + index * step, end=start + (index + 1) * step, confidence=confidence)
        for index, char in enumerate(chars)
    ]


def transcript_timed_chars(transcript: dict[str, Any]) -> list[TimedChar]:
    result: list[TimedChar] = []
    for segment in transcript.get("segments") or []:
        words = segment.get("words") if isinstance(segment, dict) else None
        if isinstance(words, list) and words:
            for word in words:
                if not isinstance(word, dict):
                    continue
                try:
                    start = float(word.get("start"))
                    end = float(word.get("end"))
                except (TypeError, ValueError):
                    continue
                result.extend(
                    _timed_chars_from_text(
                        str(word.get("text") or ""),
                        start,
                        end,
                        float(word["confidence"]) if isinstance(word.get("confidence"), (int, float)) else None,
                    )
                )
        elif isinstance(segment, dict):
            try:
                start = float(segment.get("start"))
                end = float(segment.get("end"))
            except (TypeError, ValueError):
                continue
            result.extend(
                _timed_chars_from_text(
                    str(segment.get("text") or ""),
                    start,
                    end,
                    float(segment["confidence"]) if isinstance(segment.get("confidence"), (int, float)) else None,
                )
            )
    return result


def align_script_to_timing(script: str, asr_chars: list[TimedChar]) -> tuple[list[TimedChar], float]:
    script_chars = normalized_alignment_chars(script)
    if not script_chars or not asr_chars:
        raise ValueError("script and transcript both need timed spoken characters")
    script_value = "".join(char for char, _ in script_chars)
    asr_value = "".join(item.char for item in asr_chars)
    matcher = difflib.SequenceMatcher(None, script_value, asr_value, autojunk=False)
    mapped: dict[int, TimedChar] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapped[block.a + offset] = asr_chars[block.b + offset]
    known = sorted(mapped)
    if not known:
        raise ValueError("script could not be aligned to the ASR transcript")

    filled: list[TimedChar] = []
    median_step = max((asr_chars[-1].end - asr_chars[0].start) / max(len(script_chars), 1), 0.045)
    for index, (char, _) in enumerate(script_chars):
        if index in mapped:
            item = mapped[index]
            filled.append(TimedChar(char=char, start=item.start, end=item.end, confidence=item.confidence))
            continue
        insertion = bisect.bisect_left(known, index)
        previous_index = known[insertion - 1] if insertion > 0 else None
        next_index = known[insertion] if insertion < len(known) else None
        if previous_index is not None and next_index is not None:
            previous = mapped[previous_index]
            following = mapped[next_index]
            fraction = (index - previous_index) / max(next_index - previous_index, 1)
            center = previous.end + (following.start - previous.end) * fraction
        elif previous_index is not None:
            previous = mapped[previous_index]
            center = previous.end + median_step * (index - previous_index)
        else:
            following = mapped[next_index]  # type: ignore[index]
            center = following.start - median_step * (next_index - index)  # type: ignore[operator]
        filled.append(TimedChar(char=char, start=max(0.0, center - median_step / 2), end=max(0.0, center + median_step / 2), confidence=None))

    previous_end = 0.0
    for item in filled:
        item.start = max(item.start, previous_end)
        item.end = max(item.end, item.start + 0.01)
        previous_end = item.end
    return filled, matcher.ratio()


def parse_fragments(script: str) -> list[Fragment]:
    fragments: list[Fragment] = []
    pattern = re.compile(r"[^。！？!?；;，,：:、\n]+[。！？!?；;，,：:、\n]*")
    for match in pattern.finditer(script):
        raw = match.group(0)
        content = raw.rstrip("。！？!?；;，,：:、\n").strip()
        if not content:
            continue
        leading = len(raw) - len(raw.lstrip())
        start = match.start() + leading
        end = start + len(content)
        suffix = raw[len(raw.rstrip("。！？!?；;，,：:、\n")) :]
        display = content.rstrip(TRAILING_DISPLAY_PUNCTUATION).strip()
        if display:
            fragments.append(Fragment(display, start, end, any(char in STRONG_PUNCTUATION for char in suffix)))
    return fragments


def visual_units(text: str) -> float:
    total = 0.0
    for char in text:
        if char == "\n":
            continue
        if "\u3400" <= char <= "\u9fff":
            total += 1.0
        elif char.isdigit() or "a" <= char.lower() <= "z":
            total += 0.62
        elif char in ".%":
            total += 0.55
        else:
            total += 0.42
    return total


def protected_spans(text: str, terms: list[str]) -> list[tuple[int, int]]:
    spans = [(match.start(), match.end()) for match in AUTOMATIC_PROTECTED.finditer(text)]
    for term in terms:
        start = 0
        while term and (index := text.find(term, start)) >= 0:
            spans.append((index, index + len(term)))
            start = index + len(term)
    return spans


def safe_boundaries(text: str, terms: list[str]) -> list[int]:
    spans = protected_spans(text, terms)
    return [
        index
        for index in range(1, len(text))
        if not any(start < index < end for start, end in spans)
    ]


def split_fragment(fragment: Fragment, maximum_units: float, terms: list[str]) -> list[Fragment]:
    if visual_units(fragment.text) <= maximum_units:
        return [fragment]
    pieces: list[Fragment] = []
    remaining = fragment
    while visual_units(remaining.text) > maximum_units:
        boundaries = safe_boundaries(remaining.text, terms)
        candidates = [index for index in boundaries if visual_units(remaining.text[:index]) <= maximum_units]
        if not candidates:
            candidates = boundaries
        if not candidates:
            break
        target = maximum_units * 0.82
        split_at = min(candidates, key=lambda index: abs(visual_units(remaining.text[:index]) - target))
        if len(remaining.text) - split_at < 3 and len(candidates) > 1:
            split_at = candidates[-2]
        pieces.append(Fragment(remaining.text[:split_at], remaining.start_index, remaining.start_index + split_at, False))
        remaining = Fragment(remaining.text[split_at:], remaining.start_index + split_at, remaining.end_index, remaining.strong_after)
    if remaining.text:
        pieces.append(remaining)
    return pieces


def build_pages(fragments: list[Fragment], max_line_units: float, max_lines: int, terms: list[str]) -> list[list[Fragment]]:
    maximum = max_line_units * max_lines
    expanded: list[Fragment] = []
    for fragment in fragments:
        expanded.extend(split_fragment(fragment, max_line_units, terms))

    def can_fit(candidate: list[Fragment]) -> bool:
        text = "".join(item.text for item in candidate)
        if visual_units(text) <= max_line_units:
            return True
        if max_lines < 2:
            return False
        cursor = 0
        boundaries = []
        for item in candidate[:-1]:
            cursor += len(item.text)
            boundaries.append(cursor)
        return any(
            visual_units(text[:boundary]) <= max_line_units
            and visual_units(text[boundary:]) <= max_line_units
            for boundary in boundaries
        )

    pages: list[list[Fragment]] = []
    current: list[Fragment] = []
    for fragment in expanded:
        previous_strong = current[-1].strong_after if current else False
        if current and (previous_strong or not can_fit([*current, fragment])):
            pages.append(current)
            current = []
        current.append(fragment)
        if fragment.strong_after and sum(visual_units(item.text) for item in current) >= 4:
            pages.append(current)
            current = []
    if current:
        pages.append(current)
    if len(pages) > 1 and sum(visual_units(item.text) for item in pages[-1]) < 4:
        combined = pages[-2] + pages[-1]
        if sum(visual_units(item.text) for item in combined) <= maximum:
            pages[-2] = combined
            pages.pop()
    return pages


def balanced_display(page: list[Fragment], max_line_units: float, terms: list[str]) -> str:
    text = "".join(item.text for item in page).strip()
    if visual_units(text) <= max_line_units:
        return text
    fragment_boundaries = []
    cursor = 0
    for fragment in page[:-1]:
        cursor += len(fragment.text)
        fragment_boundaries.append(cursor)
    boundaries = fragment_boundaries or safe_boundaries(text, terms)
    candidates = [
        index
        for index in boundaries
        if visual_units(text[:index]) <= max_line_units and visual_units(text[index:]) <= max_line_units
    ]
    if not candidates:
        candidates = safe_boundaries(text, terms)
    if not candidates:
        return text
    split_at = min(candidates, key=lambda index: abs(visual_units(text[:index]) - visual_units(text[index:])))
    if len(text[:split_at]) < 2 or len(text[split_at:]) < 2:
        return text
    return f"{text[:split_at]}\n{text[split_at:]}"


def page_timing(page: list[Fragment], script_chars: list[tuple[str, int]], timing: list[TimedChar]) -> tuple[float, float, float | None]:
    start_index = page[0].start_index
    end_index = page[-1].end_index
    positions = [index for index, (_, original_index) in enumerate(script_chars) if start_index <= original_index < end_index]
    if not positions:
        raise ValueError(f"caption page has no alignable characters: {''.join(item.text for item in page)}")
    selected = [timing[index] for index in positions]
    confidences = [item.confidence for item in selected if isinstance(item.confidence, (int, float))]
    confidence = sum(confidences) / len(confidences) if confidences else None
    return selected[0].start, selected[-1].end, confidence


def build_semantic_captions(
    transcript: dict[str, Any],
    script: str,
    *,
    max_line_units: float = 14,
    max_lines: int = 2,
    min_caption_ms: int = 0,
    min_alignment: float | None = None,
    terms: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    protected_terms = [term.strip() for term in (terms or []) if term.strip()]
    asr_chars = transcript_timed_chars(transcript)
    timing, alignment_ratio = align_script_to_timing(script, asr_chars)
    script_chars = normalized_alignment_chars(script)
    fragments = parse_fragments(script)
    pages = build_pages(fragments, max_line_units, max_lines, protected_terms)
    captions: list[dict[str, Any]] = []
    for page in pages:
        start, end, confidence = page_timing(page, script_chars, timing)
        captions.append(
            {
                "text": balanced_display(page, max_line_units, protected_terms),
                "startMs": round(start * 1000),
                "endMs": round(end * 1000),
                "timestampMs": round(start * 1000),
                "confidence": round(confidence, 4) if confidence is not None else None,
            }
        )
    for index, caption in enumerate(captions):
        next_start = captions[index + 1]["startMs"] if index + 1 < len(captions) else None
        if min_caption_ms > 0:
            if next_start is not None:
                caption["endMs"] = min(max(caption["endMs"], caption["startMs"] + min_caption_ms), next_start - 10)
            else:
                caption["endMs"] = max(caption["endMs"], caption["startMs"] + min_caption_ms)
    status = "generated"
    if min_alignment is not None:
        status = "aligned" if alignment_ratio >= min_alignment else "review_required"
    audit = {
        "schema_version": 1,
        "status": status,
        "alignment_ratio": round(alignment_ratio, 4),
        "min_alignment": min_alignment,
        "caption_pages": len(captions),
        "script_characters": len(script_chars),
        "asr_characters": len(asr_chars),
        "text_source": "script",
        "timing_source": "local_asr",
        "min_caption_ms": min_caption_ms,
        "max_line_units": max_line_units,
        "max_lines": max_lines,
        "protected_terms": protected_terms,
    }
    return captions, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--script", required=True, type=Path, help="Narration text or JSON containing segments[].spoken")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--terms", type=Path, help="Optional UTF-8 file with one protected term per line")
    parser.add_argument("--max-line-units", type=float, default=14)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--min-caption-ms", type=int, default=0)
    parser.add_argument("--min-alignment", type=float)
    args = parser.parse_args()
    if args.min_caption_ms < 0:
        parser.error("--min-caption-ms must not be negative")
    if args.min_alignment is not None and not 0 <= args.min_alignment <= 1:
        parser.error("--min-alignment must be between 0 and 1")
    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    script = load_approved_script(args.script)
    terms = args.terms.read_text(encoding="utf-8").splitlines() if args.terms else []
    try:
        captions, audit = build_semantic_captions(
            transcript,
            script,
            max_line_units=args.max_line_units,
            max_lines=args.max_lines,
            min_caption_ms=args.min_caption_ms,
            min_alignment=args.min_alignment,
            terms=terms,
        )
        from validate_semantic_captions import validate as validate_captions

        source_duration = transcript.get("source_duration_sec")
        validation_errors, validation_metrics = validate_captions(
            captions,
            approved_script=script,
            protected_terms=terms,
            max_line_units=args.max_line_units,
            max_lines=args.max_lines,
            program_duration_ms=(
                round(float(source_duration) * 1000)
                if isinstance(source_duration, (int, float)) and source_duration > 0
                else None
            ),
        )
        audit["validation_errors"] = validation_errors
        audit["validation_metrics"] = validation_metrics
        if validation_errors:
            audit["status"] = "review_required"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(captions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_path = args.audit or args.output.with_name(f"{args.output.stem}-audit.json")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "captions": len(captions), "output": str(args.output.resolve()), "audit": str(audit_path.resolve())}, ensure_ascii=False))
    return 2 if audit["status"] == "review_required" else 0


if __name__ == "__main__":
    raise SystemExit(main())
