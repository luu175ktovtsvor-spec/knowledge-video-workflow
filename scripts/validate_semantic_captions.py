#!/usr/bin/env python3
"""Validate semantic caption timing, line breaks, content, and protected terms."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ALIGN_CHAR = re.compile(r"[\u3400-\u9fffA-Za-z0-9%]")


def normalized(text: str) -> str:
    return "".join(
        char.lower()
        for original in text
        for char in unicodedata.normalize("NFKC", original)
        if ALIGN_CHAR.fullmatch(char)
    )


def visual_units(text: str) -> float:
    total = 0.0
    for char in text:
        if "\u3400" <= char <= "\u9fff":
            total += 1
        elif char.isalnum():
            total += 0.62
        elif char in ".%":
            total += 0.55
        else:
            total += 0.42
    return total


def validate(
    captions: Any,
    *,
    approved_script: str | None = None,
    protected_terms: list[str] | None = None,
    max_line_units: float = 14,
    max_lines: int = 2,
    program_duration_ms: int | None = None,
    min_duration_sec: float | None = None,
    max_duration_sec: float | None = None,
    max_reading_rate: float | None = None,
    min_similarity: float | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(captions, list) or not captions:
        return ["captions must be a non-empty list"], {}
    previous_end = -1
    texts: list[str] = []
    maximum_reading_rate = 0.0
    for index, caption in enumerate(captions):
        label = f"captions[{index}]"
        if not isinstance(caption, dict):
            errors.append(f"{label} must be an object")
            continue
        text = str(caption.get("text") or "").strip()
        if not text:
            errors.append(f"{label}.text must not be empty")
            continue
        lines = text.split("\n")
        if len(lines) > max_lines:
            errors.append(f"{label} exceeds {max_lines} lines")
        if any(not line.strip() for line in lines):
            errors.append(f"{label} has an empty line")
        if any(len(normalized(line)) < 2 for line in lines) and len(normalized(text)) >= 4:
            errors.append(f"{label} has a one-character orphan line")
        for line_index, line in enumerate(lines):
            if visual_units(line) > max_line_units + 0.2:
                errors.append(f"{label} line {line_index + 1} exceeds the visual width budget")
        try:
            start = int(caption.get("startMs"))
            end = int(caption.get("endMs"))
        except (TypeError, ValueError):
            errors.append(f"{label} needs integer startMs/endMs")
            continue
        if start < 0 or end <= start:
            errors.append(f"{label} needs 0 <= startMs < endMs")
        if program_duration_ms is not None and end > program_duration_ms + 50:
            errors.append(f"{label}.endMs exceeds the program duration")
        if start < previous_end:
            errors.append(f"{label} overlaps the previous caption")
        previous_end = end
        duration = max((end - start) / 1000, 0.001)
        if min_duration_sec is not None and duration < min_duration_sec:
            errors.append(f"{label} is displayed for less than {min_duration_sec:g} seconds")
        if max_duration_sec is not None and duration > max_duration_sec:
            errors.append(f"{label} is displayed for more than {max_duration_sec:g} seconds")
        maximum_reading_rate = max(maximum_reading_rate, len(normalized(text)) / duration)
        texts.append(text.replace("\n", ""))

    joined = "".join(texts)
    terms = [term.strip() for term in (protected_terms or []) if term.strip()]
    for term in terms:
        if term in joined and not any(term in text for text in texts):
            errors.append(f"protected term is split across caption pages: {term}")
    for index in range(len(texts) - 1):
        left, right = texts[index], texts[index + 1]
        if not left or not right:
            continue
        if re.search(r"(?:\d|\.)$", left) and re.match(r"^(?:\d|%|万|亿|元|年)", right):
            errors.append(f"numeric expression is split between captions {index} and {index + 1}")
        if re.search(r"[ABCDabcd]$", left) and right.startswith("轮"):
            errors.append(f"financing round is split between captions {index} and {index + 1}")
        if left.endswith("百") and right.startswith("分之"):
            errors.append(f"percentage expression is split between captions {index} and {index + 1}")

    similarity = None
    if approved_script is not None:
        expected = normalized(approved_script)
        actual = normalized(joined)
        similarity = difflib.SequenceMatcher(None, expected, actual, autojunk=False).ratio() if expected else 0.0
        if min_similarity is not None and similarity < min_similarity:
            errors.append(f"caption text similarity {similarity:.4f} is below {min_similarity:.4f}")
    if max_reading_rate is not None and maximum_reading_rate > max_reading_rate:
        errors.append(f"caption reading rate exceeds {max_reading_rate:g} normalized characters per second")
    metrics = {
        "caption_pages": len(captions),
        "max_reading_rate": round(maximum_reading_rate, 3),
        "text_similarity": round(similarity, 4) if similarity is not None else None,
        "protected_terms": terms,
    }
    return errors, metrics


def load_script(path: Path) -> str:
    if path.suffix.lower() != ".json":
        return path.read_text(encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        return "\n\n".join(
            str(item.get("spoken") or item.get("spoken_text") or item.get("text") or "").strip()
            for item in data["segments"]
            if isinstance(item, dict) and str(item.get("spoken") or item.get("spoken_text") or item.get("text") or "").strip()
        )
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("spoken", "spoken_text", "text", "script"):
            if isinstance(data.get(key), str):
                return data[key]
    raise ValueError("script JSON does not contain usable narration text")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captions", type=Path)
    parser.add_argument("--script", type=Path)
    parser.add_argument("--terms", type=Path)
    parser.add_argument("--max-line-units", type=float, default=14)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--duration-sec", type=float)
    parser.add_argument("--min-duration-sec", type=float)
    parser.add_argument("--max-duration-sec", type=float)
    parser.add_argument("--max-reading-rate", type=float)
    parser.add_argument("--min-similarity", type=float)
    args = parser.parse_args()
    captions = json.loads(args.captions.read_text(encoding="utf-8"))
    script = load_script(args.script) if args.script else None
    terms = args.terms.read_text(encoding="utf-8").splitlines() if args.terms else []
    errors, metrics = validate(
        captions,
        approved_script=script,
        protected_terms=terms,
        max_line_units=args.max_line_units,
        max_lines=args.max_lines,
        program_duration_ms=round(args.duration_sec * 1000) if args.duration_sec is not None else None,
        min_duration_sec=args.min_duration_sec,
        max_duration_sec=args.max_duration_sec,
        max_reading_rate=args.max_reading_rate,
        min_similarity=args.min_similarity,
    )
    print(json.dumps({"status": "ok" if not errors else "invalid", "errors": errors, "metrics": metrics}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
