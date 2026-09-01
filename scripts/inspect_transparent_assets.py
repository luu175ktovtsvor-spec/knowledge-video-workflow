#!/usr/bin/env python3
"""Inspect existing transparent PNG source files before they enter a video project."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_header(path: Path) -> tuple[int, int, bool]:
    with path.open("rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise ValueError("not a PNG")
        length = struct.unpack(">I", handle.read(4))[0]
        if handle.read(4) != b"IHDR" or length != 13:
            raise ValueError("missing PNG IHDR")
        width, height, _depth, color_type, _compression, _filter, _interlace = struct.unpack(
            ">IIBBBBB", handle.read(13)
        )
    return width, height, color_type in {4, 6}


def read_alpha(path: Path, width: int, height: int, ffmpeg: str) -> bytes:
    result = subprocess.run(
        [
            ffmpeg,
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
    if len(result.stdout) != width * height:
        raise ValueError("could not read the complete alpha plane")
    return result.stdout


def render_preview(
    path: Path, output: Path, width: int, height: int, ffmpeg: str
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(path),
            "-f",
            "lavfi",
            "-i",
            f"color=c=0xf4efe7:s={width}x{height}",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x20242b:s={width}x{height}",
            "-filter_complex",
            "[0:v]format=rgba,split=2[fg1][fg2];"
            "[1:v][fg1]overlay=0:0:format=auto[light];"
            "[2:v][fg2]overlay=0:0:format=auto[dark];"
            "[light][dark]hstack=inputs=2[out]",
            "-map",
            "[out]",
            "-frames:v",
            "1",
            str(output),
        ],
        check=True,
    )


def collect_paths(inputs: list[Path]) -> list[Path]:
    paths: set[Path] = set()
    for raw in inputs:
        path = raw.resolve()
        if path.is_dir():
            paths.update(candidate.resolve() for candidate in path.rglob("*.png"))
        elif path.is_file():
            paths.add(path)
        else:
            raise SystemExit(f"input does not exist: {path}")
    return sorted(paths)


def inspect(path: Path, ffmpeg: str, edge_margin: int) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "status": "invalid",
        "errors": [],
        "warnings": [],
    }
    try:
        width, height, has_alpha = read_png_header(path)
        item.update({"width": width, "height": height, "has_alpha": has_alpha})
        if not has_alpha:
            item["errors"].append("missing alpha channel")
            return item

        alpha = read_alpha(path, width, height, ffmpeg)
        visible = [index for index, value in enumerate(alpha) if value > 8]
        if not visible:
            item["errors"].append("no visible pixels")
            return item

        left = min(index % width for index in visible)
        right = max(index % width for index in visible)
        top = min(index // width for index in visible)
        bottom = max(index // width for index in visible)
        clearances = {
            "left": left,
            "right": width - 1 - right,
            "top": top,
            "bottom": height - 1 - bottom,
        }
        risky_edges = [name for name, value in clearances.items() if value < edge_margin]
        item.update(
            {
                "alpha_min": min(alpha),
                "alpha_max": max(alpha),
                "content_bbox": {
                    "x": left,
                    "y": top,
                    "width": right - left + 1,
                    "height": bottom - top + 1,
                },
                "edge_clearance_px": clearances,
                "risky_edges": risky_edges,
            }
        )
        if min(alpha) > 0:
            item["errors"].append("no fully transparent background pixels")
        if risky_edges:
            item["warnings"].append(
                "visible content reaches the source boundary; inspect for cropped body parts or props"
            )
        item["status"] = "invalid" if item["errors"] else "review" if item["warnings"] else "ok"
        return item
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        item["errors"].append(str(exc))
        return item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("component-library", "user-provided", "imagegen"),
        help="Real origin of the inspected PNG files",
    )
    parser.add_argument("--output", type=Path, required=True, help="JSON report path")
    parser.add_argument(
        "--preview-dir",
        type=Path,
        help="Optional directory for light/dark background preview PNGs",
    )
    parser.add_argument(
        "--edge-margin",
        type=int,
        default=4,
        help="Minimum transparent clearance in pixels before an edge is flagged",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Optional batch pre-screen: return non-zero for review or invalid; never replaces visual inspection",
    )
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required")
    if args.edge_margin < 1:
        raise SystemExit("--edge-margin must be at least 1")

    paths = collect_paths(args.inputs)
    if not paths:
        raise SystemExit("no PNG files found")

    results: list[dict[str, Any]] = []
    for index, path in enumerate(paths, start=1):
        item = inspect(path, ffmpeg, args.edge_margin)
        if args.preview_dir and item.get("width") and item.get("height") and item.get("has_alpha"):
            preview_name = f"{index:03d}-{path.stem}-light-dark.png"
            preview_path = args.preview_dir.resolve() / preview_name
            try:
                render_preview(
                    path,
                    preview_path,
                    int(item["width"]),
                    int(item["height"]),
                    ffmpeg,
                )
                item["preview"] = str(preview_path)
            except subprocess.CalledProcessError as exc:
                item["errors"].append(f"preview render failed: {exc}")
                item["status"] = "invalid"
        results.append(item)

    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("ok", "review", "invalid")
    }
    report = {
        "status": "ready" if counts["invalid"] == 0 else "invalid",
        "source_kind": args.source_kind,
        "edge_margin_px": args.edge_margin,
        "manual_review_required": True,
        "review_rule": (
            "Open every light/dark preview at full size. Confirm complete heads, hands, feet, joints, "
            "group members and prop outlines; an automatic ok result does not prove semantic completeness."
        ),
        "counts": counts,
        "items": results,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "counts": counts}, ensure_ascii=False))
    if counts["invalid"] or (args.strict and counts["review"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
