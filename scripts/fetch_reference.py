#!/usr/bin/env python3
"""Download permitted reference samples with yt-dlp and save metadata."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cookies", type=Path)
    parser.add_argument("--cookies-from-browser", choices=["chrome", "firefox", "edge", "safari"])
    parser.add_argument("--playlist", action="store_true", help="Allow playlist/profile traversal when it is in scope")
    parser.add_argument("--max-downloads", type=int, help="Optional cap across all supplied URLs")
    args = parser.parse_args()
    if args.max_downloads is not None and args.max_downloads <= 0:
        parser.error("--max-downloads must be positive")
    if not shutil.which("yt-dlp"):
        parser.error("yt-dlp is required: python3 -m pip install yt-dlp")
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp", "--write-info-json",
        "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "--output", str(output / "%(id)s-%(title).80s.%(ext)s"),
    ]
    if not args.playlist:
        command.append("--no-playlist")
    if args.max_downloads is not None:
        command.extend(["--max-downloads", str(args.max_downloads)])
    if args.cookies:
        command.extend(["--cookies", str(args.cookies.expanduser().resolve())])
    elif args.cookies_from_browser:
        command.extend(["--cookies-from-browser", args.cookies_from_browser])
    command.extend(args.urls)
    result = subprocess.run(command)
    print(
        json.dumps(
            {
                "status": "ok" if result.returncode == 0 else "failed",
                "output_dir": str(output),
                "url_count": len(args.urls),
                "playlist": args.playlist,
                "max_downloads": args.max_downloads,
            },
            ensure_ascii=False,
        )
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
