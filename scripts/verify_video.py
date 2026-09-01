#!/usr/bin/env python3
"""Inspect a rendered video and verify only the delivery targets supplied by the caller."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def probe_media(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("ffprobe returned invalid JSON")
    return data


def parse_visual_events(log: str) -> dict[str, list[dict[str, float]]]:
    black = [
        {"start": float(start), "end": float(end), "duration": float(duration)}
        for start, end, duration in re.findall(
            r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)",
            log,
        )
    ]
    starts = [float(value) for value in re.findall(r"freeze_start:\s*([0-9.]+)", log)]
    durations = [float(value) for value in re.findall(r"freeze_duration:\s*([0-9.]+)", log)]
    freezes = [
        {"start": start, "duration": duration, "end": start + duration}
        for start, duration in zip(starts, durations)
    ]
    return {"black": black, "freeze": freezes}


def parse_audio_analysis(log: str) -> dict[str, Any]:
    silence = [
        {"start": float(start), "end": float(end), "duration": float(duration)}
        for start, end, duration in re.findall(
            r"silence_start:\s*([0-9.]+).*?silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)",
            log,
            flags=re.S,
        )
    ]
    summary = log.rsplit("Summary:", 1)[-1] if "Summary:" in log else log
    loudness = re.search(r"Integrated loudness:\s*\n\s*I:\s*([-0-9.]+)\s*LUFS", summary)
    range_match = re.search(r"Loudness range:\s*\n\s*LRA:\s*([-0-9.]+)\s*LU", summary)
    peak = re.search(r"True peak:\s*\n\s*Peak:\s*([-0-9.]+)\s*dBFS", summary)
    return {
        "integrated_lufs": float(loudness.group(1)) if loudness else None,
        "loudness_range_lu": float(range_match.group(1)) if range_match else None,
        "true_peak_dbtp": float(peak.group(1)) if peak else None,
        "silence": silence,
    }


def audit_video(
    path: Path,
    *,
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_duration: float | None = None,
    duration_tolerance: float = 0.25,
    expected_video_codec: str | None = None,
    expected_audio_codec: str | None = None,
    expected_container: str | None = None,
    allow_no_audio: bool = False,
    lufs_min: float | None = None,
    lufs_max: float | None = None,
    max_true_peak: float | None = None,
    anomaly_threshold_sec: float | None = None,
    strict_content_anomalies: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file() or path.stat().st_size <= 0:
        return {"status": "invalid", "errors": [f"missing or empty video: {path}"], "warnings": []}
    try:
        probe = probe_media(path)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "errors": [str(exc)], "warnings": []}
    streams = probe.get("streams") if isinstance(probe.get("streams"), list) else []
    video_streams = [item for item in streams if item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    video = video_streams[0] if video_streams else {}
    audio = audio_streams[0] if audio_streams else {}
    duration = float((probe.get("format") or {}).get("duration") or 0)
    format_names = {
        item.strip()
        for item in str((probe.get("format") or {}).get("format_name") or "").split(",")
        if item.strip()
    }
    if expected_container and expected_container not in format_names:
        errors.append(f"container must include {expected_container}, got {sorted(format_names)}")
    if not video:
        errors.append("delivery has no video stream")
    elif expected_video_codec and video.get("codec_name") != expected_video_codec:
        errors.append(f"video codec must be {expected_video_codec}, got {video.get('codec_name')}")
    if not audio and not allow_no_audio:
        errors.append("delivery has no audio stream")
    elif audio and expected_audio_codec and audio.get("codec_name") != expected_audio_codec:
        errors.append(f"audio codec must be {expected_audio_codec}, got {audio.get('codec_name')}")
    if duration <= 0:
        errors.append("delivery duration is unavailable")
    if expected_duration is not None and abs(duration - expected_duration) > duration_tolerance:
        errors.append(
            f"duration {duration:.3f}s differs from expected {expected_duration:.3f}s by more than {duration_tolerance:.3f}s"
        )
    if expected_width is not None and video.get("width") != expected_width:
        errors.append(f"width must be {expected_width}, got {video.get('width')}")
    if expected_height is not None and video.get("height") != expected_height:
        errors.append(f"height must be {expected_height}, got {video.get('height')}")

    decode = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
            "-f",
            "null",
            "-",
        ]
    )
    decode_errors = decode.stderr.strip()
    if decode.returncode != 0 or decode_errors:
        errors.append("full decode failed" + (f": {decode_errors[-1000:]}" if decode_errors else ""))

    visual_result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-vf",
            "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-50dB:d=1",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    if visual_result.returncode != 0:
        errors.append(
            "visual anomaly analysis failed"
            + (f": {visual_result.stderr.strip()[-1000:]}" if visual_result.stderr.strip() else "")
        )
    visual = parse_visual_events(visual_result.stderr)
    if anomaly_threshold_sec is not None:
        long_black = [item for item in visual["black"] if item["duration"] > anomaly_threshold_sec]
        long_freeze = [item for item in visual["freeze"] if item["duration"] > anomaly_threshold_sec]
        for label, events in (("black", long_black), ("freeze", long_freeze)):
            if events:
                message = f"detected {len(events)} {label} interval(s) longer than {anomaly_threshold_sec}s"
                (errors if strict_content_anomalies else warnings).append(message)

    audio_analysis: dict[str, Any] | None = None
    if audio:
        audio_result = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-vn",
                "-af",
                "silencedetect=n=-45dB:d=0.8,ebur128=peak=true",
                "-f",
                "null",
                "-",
            ]
        )
        if audio_result.returncode != 0:
            errors.append(
                "audio analysis failed"
                + (f": {audio_result.stderr.strip()[-1000:]}" if audio_result.stderr.strip() else "")
            )
        audio_analysis = parse_audio_analysis(audio_result.stderr)
        loudness = audio_analysis.get("integrated_lufs")
        peak = audio_analysis.get("true_peak_dbtp")
        if (lufs_min is not None or lufs_max is not None) and loudness is None:
            errors.append("integrated loudness could not be measured")
        elif loudness is not None and lufs_min is not None and loudness < lufs_min:
            errors.append(f"integrated loudness {loudness:.1f} LUFS is below {lufs_min:.1f}")
        elif loudness is not None and lufs_max is not None and loudness > lufs_max:
            errors.append(f"integrated loudness {loudness:.1f} LUFS exceeds {lufs_max:.1f}")
        if max_true_peak is not None and peak is None:
            errors.append("true peak could not be measured")
        elif peak is not None and max_true_peak is not None and peak > max_true_peak:
            errors.append(f"true peak {peak:.1f} dBTP exceeds {max_true_peak:.1f} dBTP")
        if anomaly_threshold_sec is not None:
            long_silence = [item for item in audio_analysis["silence"] if item["duration"] > anomaly_threshold_sec]
            if long_silence:
                message = f"detected {len(long_silence)} silence interval(s) longer than {anomaly_threshold_sec}s"
                (errors if strict_content_anomalies else warnings).append(message)

    return {
        "status": "ok" if not errors else "invalid",
        "path": str(path.resolve()),
        "media": {
            "duration_sec": round(duration, 3),
            "container_formats": sorted(format_names),
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "video": {
                "codec": video.get("codec_name"),
                "width": video.get("width"),
                "height": video.get("height"),
                "frame_rate": video.get("avg_frame_rate") or video.get("r_frame_rate"),
            },
            "audio": {
                "present": bool(audio),
                "codec": audio.get("codec_name") if audio else None,
                "sample_rate": audio.get("sample_rate") if audio else None,
                "channels": audio.get("channels") if audio else None,
            },
        },
        "full_decode_passed": decode.returncode == 0 and not decode_errors,
        "visual_analysis_passed": visual_result.returncode == 0,
        "audio_analysis_passed": audio_result.returncode == 0 if audio else None,
        "visual_analysis": visual,
        "audio_analysis": audio_analysis,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--expected-duration", type=float)
    parser.add_argument("--duration-tolerance", type=float, default=0.25)
    parser.add_argument("--expected-video-codec")
    parser.add_argument("--expected-audio-codec")
    parser.add_argument("--expected-container")
    parser.add_argument("--allow-no-audio", action="store_true")
    parser.add_argument("--lufs-min", type=float)
    parser.add_argument("--lufs-max", type=float)
    parser.add_argument("--max-true-peak", type=float)
    parser.add_argument("--anomaly-threshold-sec", type=float)
    parser.add_argument("--strict-content-anomalies", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.lufs_min is not None and args.lufs_max is not None and args.lufs_min > args.lufs_max:
        parser.error("--lufs-min must not exceed --lufs-max")
    if args.anomaly_threshold_sec is not None and args.anomaly_threshold_sec <= 0:
        parser.error("--anomaly-threshold-sec must be positive")
    if args.strict_content_anomalies and args.anomaly_threshold_sec is None:
        parser.error("--strict-content-anomalies requires --anomaly-threshold-sec")
    result = audit_video(
        args.video.expanduser().resolve(),
        expected_width=args.expected_width,
        expected_height=args.expected_height,
        expected_duration=args.expected_duration,
        duration_tolerance=args.duration_tolerance,
        expected_video_codec=args.expected_video_codec,
        expected_audio_codec=args.expected_audio_codec,
        expected_container=args.expected_container,
        allow_no_audio=args.allow_no_audio,
        lufs_min=args.lufs_min,
        lufs_max=args.lufs_max,
        max_true_peak=args.max_true_peak,
        anomaly_threshold_sec=args.anomaly_threshold_sec,
        strict_content_anomalies=args.strict_content_anomalies,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
