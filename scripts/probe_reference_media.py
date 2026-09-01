#!/usr/bin/env python3
"""Create bounded visual/audio evidence for a local reference video."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def parse_rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


def probe_media(source: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
        ]
    )
    raw = json.loads(result.stdout)
    video = next((stream for stream in raw.get("streams", []) if stream.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("reference media has no video stream")
    audio = [stream for stream in raw.get("streams", []) if stream.get("codec_type") == "audio"]
    duration = float(raw.get("format", {}).get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise ValueError("reference media duration is unavailable")

    tags = video.get("tags") if isinstance(video.get("tags"), dict) else {}
    normalized_tags = {str(key).casefold(): value for key, value in tags.items()}

    def tag(*names: str) -> object | None:
        return next((normalized_tags[name.casefold()] for name in names if name.casefold() in normalized_tags), None)

    camera_metadata = {
        "camera_make": tag("make", "com.apple.quicktime.make"),
        "camera_model": tag("model", "com.apple.quicktime.model"),
        "lens_model": tag("lens_model", "lensmodel", "com.apple.quicktime.lens_model"),
        "focal_length": tag("focal_length", "focallength"),
        "focal_length_35mm": tag("focal_length_in_35mm_format", "focal_length_35mm"),
        "color_temperature": tag("color_temperature", "colortemperature"),
        "white_balance": tag("white_balance", "whitebalance"),
    }
    camera_metadata = {key: value for key, value in camera_metadata.items() if value not in (None, "")}
    average_fps = parse_rate(video.get("avg_frame_rate"))
    nominal_fps = parse_rate(video.get("r_frame_rate"))
    preferred_fps = average_fps or nominal_fps

    return {
        "source": str(source.resolve()),
        "source_sha256": sha256_file(source),
        "duration_seconds": round(duration, 3),
        "video": {
            "codec": video.get("codec_name"),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "fps": round(preferred_fps, 3),
            "average_fps": round(average_fps, 6),
            "nominal_fps": round(nominal_fps, 6),
            "variable_frame_rate_suspected": bool(
                average_fps and nominal_fps and abs(average_fps - nominal_fps) > 0.01
            ),
            "pixel_format": video.get("pix_fmt"),
            "color_space": video.get("color_space"),
            "color_transfer": video.get("color_transfer"),
            "color_primaries": video.get("color_primaries"),
            "camera_metadata": camera_metadata,
        },
        "audio": {
            "present": bool(audio),
            "stream_count": len(audio),
            "codecs": [stream.get("codec_name") for stream in audio],
            "sample_rates": [stream.get("sample_rate") for stream in audio],
        },
    }


def contact_tile_size(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return 320, 180
    if width >= height:
        tile_width = 320
        tile_height = max(180, round(tile_width * height / width))
    else:
        tile_height = 426
        tile_width = max(180, round(tile_height * width / height))
    tile_width += tile_width % 2
    tile_height += tile_height % 2
    return tile_width, tile_height


def create_contact_sheet(source: Path, output: Path, duration: float, width: int, height: int) -> None:
    sample_count = 12
    sampling_fps = max(0.001, sample_count / duration)
    tile_width, tile_height = contact_tile_size(width, height)
    filter_graph = (
        f"fps={sampling_fps:.8f},"
        f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=decrease,"
        f"pad={tile_width}:{tile_height}:(ow-iw)/2:(oh-ih)/2:color=#111318,"
        "tile=4x3:padding=6:margin=6:color=#0b0d12"
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vf",
            filter_graph,
            "-frames:v",
            "1",
            "-y",
            str(output),
        ]
    )


def create_waveform(source: Path, output: Path) -> None:
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            "aformat=channel_layouts=mono,showwavespic=s=1080x260:colors=#F9D65C",
            "-frames:v",
            "1",
            "-y",
            str(output),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a local reference video and create bounded evidence artifacts")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        parser.error(f"source video not found: {source}")
    for dependency in ("ffmpeg", "ffprobe"):
        if shutil.which(dependency) is None:
            parser.error(f"required executable not found: {dependency}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        metadata = probe_media(source)
        (args.output_dir / "probe.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        create_contact_sheet(
            source,
            args.output_dir / "contact-sheet.png",
            metadata["duration_seconds"],
            metadata["video"]["width"],
            metadata["video"]["height"],
        )
        if metadata["audio"]["present"]:
            create_waveform(source, args.output_dir / "audio-waveform.png")
    except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
        print(f"reference probe failed: {exc}", file=sys.stderr)
        return 1

    created = ["probe.json", "contact-sheet.png"]
    if metadata["audio"]["present"]:
        created.append("audio-waveform.png")
    print(json.dumps({"status": "ok", "output_dir": str(args.output_dir.resolve()), "created": created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
