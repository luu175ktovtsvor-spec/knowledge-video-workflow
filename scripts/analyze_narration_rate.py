#!/usr/bin/env python3
"""Measure approximate Mandarin narration rate from timestamped transcript segments."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
NON_HAN_TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")


def spoken_units(text: str) -> int:
    """Approximate spoken units after the script has normalized numbers and acronyms."""
    han_count = len(HAN.findall(text))
    other_count = 0
    for token in NON_HAN_TOKEN.findall(text):
        if token.isalpha() and token.isupper() and len(token) <= 8:
            other_count += len(token)
        else:
            other_count += 1
    return han_count + other_count


def segment_times(segment: dict) -> tuple[float, float] | None:
    start, end = segment.get("start"), segment.get("end")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return float(start), float(end)
    start_ms, end_ms = segment.get("startMs"), segment.get("endMs")
    if isinstance(start_ms, (int, float)) and isinstance(end_ms, (int, float)):
        return float(start_ms) / 1000, float(end_ms) / 1000
    return None


def analyze(
    data: dict,
    slow_threshold: float | None = None,
    fast_threshold: float | None = None,
) -> dict:
    raw_segments = data.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("transcript must contain a segments list")
    rows: list[dict] = []
    total_units = 0
    active_duration = 0.0
    for index, segment in enumerate(raw_segments):
        if not isinstance(segment, dict):
            continue
        times = segment_times(segment)
        text = str(segment.get("text", "")).strip()
        if times is None or not text:
            continue
        start, end = times
        duration = end - start
        if duration <= 0:
            continue
        units = spoken_units(text)
        rate = units / duration
        row = {
            "index": index,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "spoken_units": units,
            "rate": round(rate, 3),
            "text": text,
        }
        if slow_threshold is not None and fast_threshold is not None:
            row["classification"] = "slow" if rate < slow_threshold else "fast" if rate > fast_threshold else "normal"
        rows.append(row)
        total_units += units
        active_duration += duration
    if not rows:
        raise ValueError("transcript has no usable timed text segments")
    program_duration = rows[-1]["end"] - rows[0]["start"]
    result = {
        "measurement": "approximate_spoken_units_per_second",
        "note": "Normalize numbers and acronyms to their spoken forms before treating this as a pace decision.",
        "thresholds": (
            {"slow": slow_threshold, "fast": fast_threshold}
            if slow_threshold is not None and fast_threshold is not None
            else None
        ),
        "summary": {
            "segments": len(rows),
            "spoken_units": total_units,
            "active_rate": round(total_units / active_duration, 3),
            "program_rate_including_gaps": round(total_units / program_duration, 3),
        },
        "segments": rows,
    }
    if slow_threshold is not None and fast_threshold is not None:
        result["summary"]["slow_segments"] = sum(row["classification"] == "slow" for row in rows)
        result["summary"]["fast_segments"] = sum(row["classification"] == "fast" for row in rows)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--slow", type=float)
    parser.add_argument("--fast", type=float)
    args = parser.parse_args()
    if (args.slow is None) != (args.fast is None):
        parser.error("--slow and --fast must be supplied together")
    if args.slow is not None and args.slow >= args.fast:
        parser.error("--slow must be lower than --fast")
    data = json.loads(args.transcript.read_text(encoding="utf-8"))
    print(json.dumps(analyze(data, args.slow, args.fast), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
