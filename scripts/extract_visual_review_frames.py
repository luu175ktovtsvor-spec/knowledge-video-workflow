#!/usr/bin/env python3
"""Extract contact sheets for human review of a rendered knowledge video."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def clean_pages(directory: Path, pattern: str = "*.jpg") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob(pattern):
        path.unlink()


def probe_duration(video: Path, ffprobe: str) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return float(result.stdout.strip())


def render_pages(
    *,
    ffmpeg: str,
    video: Path,
    output_pattern: Path,
    filter_graph: str,
    seek: float | None = None,
) -> None:
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if seek is not None:
        command.extend(["-ss", f"{seek:.3f}"])
    command.extend(
        [
            "-i",
            str(video),
            "-an",
            "-vf",
            filter_graph,
            "-fps_mode",
            "vfr",
            "-q:v",
            "2",
            str(output_pattern),
        ]
    )
    run(command)


def render_single_page(
    *, ffmpeg: str, video: Path, output: Path, filter_graph: str
) -> None:
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-an",
            "-vf",
            filter_graph,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output),
        ]
    )


def render_detail_frame(
    *, ffmpeg: str, video: Path, output: Path, time_sec: float
) -> None:
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-ss",
            f"{time_sec:.3f}",
            "-map",
            "0:v:0",
            "-an",
            "-frames:v",
            "1",
            str(output),
        ]
    )


def group(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--beats", type=Path, help="Optional visual-beats JSON with frame timing")
    parser.add_argument("--fps", type=int, default=30, help="Timeline fps used by --beats")
    parser.add_argument("--ending-seconds", type=float, default=30.0)
    parser.add_argument(
        "--detail-times",
        type=float,
        nargs="+",
        default=[],
        help="Optional seconds to export as native-resolution PNG detail frames",
    )
    args = parser.parse_args()

    video = args.video.resolve()
    if not video.is_file():
        raise SystemExit(f"Video does not exist: {video}")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("ffmpeg and ffprobe are required")

    output = args.output.resolve()
    full_dir = output / "full-1fps"
    ending_dir = output / "ending-2fps"
    beat_dir = output / "beat-start-mid-end"
    detail_dir = output / "detail-frames"
    clean_pages(full_dir)
    clean_pages(ending_dir)
    clean_pages(beat_dir)
    clean_pages(detail_dir, "*.png")

    duration = probe_duration(video, ffprobe)
    full_items = [
        {"sample": index, "time_sec": float(index)}
        for index in range(max(1, math.ceil(duration)))
    ]
    render_pages(
        ffmpeg=ffmpeg,
        video=video,
        output_pattern=full_dir / "%02d.jpg",
        filter_graph="fps=1,scale=320:180,tile=5x6:padding=4:margin=4",
    )

    ending_start = max(0.0, duration - args.ending_seconds)
    ending_count = max(1, math.ceil((duration - ending_start) * 2))
    ending_items = [
        {"sample": index, "time_sec": round(ending_start + index / 2, 3)}
        for index in range(ending_count)
    ]
    render_pages(
        ffmpeg=ffmpeg,
        video=video,
        output_pattern=ending_dir / "%02d.jpg",
        filter_graph="fps=2,scale=480:270,tile=4x4:padding=4:margin=4",
        seek=ending_start,
    )

    beat_items: list[dict[str, Any]] = []
    if args.beats:
        data = json.loads(args.beats.read_text(encoding="utf-8"))
        beats = data.get("beats") if isinstance(data, dict) else None
        if not isinstance(beats, list) or not beats:
            raise SystemExit("--beats must contain a non-empty beats list")
        for index, beat in enumerate(beats):
            if not isinstance(beat, dict):
                raise SystemExit(f"beats[{index}] must be an object")
            start = int(beat["from_frame"])
            length = int(beat["duration_frames"])
            inset = max(1, min(6, length // 4))
            samples = [
                ("start", start + inset),
                ("mid", start + length // 2),
                ("end", start + length - inset - 1),
            ]
            seen_frames = {frame for _, frame in samples}
            events = beat.get("internal_events")
            if isinstance(events, list):
                for event_index, event in enumerate(events):
                    if not isinstance(event, dict):
                        continue
                    at_frame = event.get("at_frame")
                    if not isinstance(at_frame, int) or not 0 <= at_frame < length:
                        continue
                    event_frame = start + at_frame
                    if event_frame in seen_frames:
                        continue
                    event_id = str(event.get("id") or f"event-{event_index + 1}")
                    samples.append((f"event:{event_id}", event_frame))
                    seen_frames.add(event_frame)
            samples.sort(key=lambda item: item[1])
            for sample_type, frame in samples:
                beat_items.append(
                    {
                        "beat_index": index,
                        "sample": sample_type,
                        "frame": frame,
                        "time_sec": round(frame / args.fps, 3),
                        "narration_anchor": beat.get("narration_anchor", ""),
                    }
                )
        for page_index, page_items in enumerate(group(beat_items, 30), start=1):
            expression = "+".join(f"eq(n,{item['frame']})" for item in page_items)
            render_single_page(
                ffmpeg=ffmpeg,
                video=video,
                output=beat_dir / f"{page_index:02d}.jpg",
                filter_graph=f"select='{expression}',scale=320:180,tile=5x6:padding=4:margin=4",
            )

    detail_items: list[dict[str, Any]] = []
    for index, time_sec in enumerate(sorted(set(args.detail_times)), start=1):
        if not math.isfinite(time_sec) or not 0 <= time_sec <= duration:
            raise SystemExit(
                f"--detail-times values must fall inside 0..{duration:.3f} seconds"
            )
        filename = f"{index:02d}-{time_sec:.3f}s.png"
        render_detail_frame(
            ffmpeg=ffmpeg,
            video=video,
            output=detail_dir / filename,
            time_sec=time_sec,
        )
        detail_items.append(
            {
                "time_sec": round(time_sec, 3),
                "file": f"detail-frames/{filename}",
                "review": "Inspect at native resolution for crop, alpha edge, occlusion and focus hierarchy.",
            }
        )

    manifest = {
        "video": str(video),
        "duration_sec": round(duration, 3),
        "review_rule": "Open every contact-sheet page to locate problems, then inspect detail-frames at native resolution and finish with continuous playback.",
        "full_1fps_pages": group(full_items, 30),
        "ending_2fps_pages": group(ending_items, 16),
        "beat_start_mid_end_pages": group(beat_items, 30),
        "detail_frames": detail_items,
    }
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output),
                "manifest": str(manifest_path),
                "full_pages": len(manifest["full_1fps_pages"]),
                "ending_pages": len(manifest["ending_2fps_pages"]),
                "beat_pages": len(manifest["beat_start_mid_end_pages"]),
                "detail_frames": len(detail_items),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
