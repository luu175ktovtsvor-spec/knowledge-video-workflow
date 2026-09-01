#!/usr/bin/env python3
"""Check local tools and packaged resources without judging visual quality."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COMMANDS = ("node", "npm", "ffmpeg", "ffprobe")
OPTIONAL_COMMANDS = ("yt-dlp",)
REQUIRED_FILES = (
    "SKILL.md",
    "assets/collage-plan.example.json",
    "assets/component-library/catalog.json",
    "assets/remotion-template/package.json",
    "assets/hyperframes-template/package.json",
    "scripts/inspect_transparent_assets.py",
)
KINDS = ("backgrounds", "characters", "groups", "modules", "props")
VERSION_ARGS = {
    "node": ("--version",),
    "npm": ("--version",),
    "ffmpeg": ("-version",),
    "ffprobe": ("-version",),
    "yt-dlp": ("--version",),
}


def command_version(path: str | None, args: tuple[str, ...]) -> str | None:
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    first_line = result.stdout.splitlines()[0].strip() if result.stdout else ""
    return first_line or None


def major_version(value: str | None) -> int | None:
    if not value:
        return None
    token = value.lstrip("v").split(".", 1)[0]
    return int(token) if token.isdigit() else None


def main() -> int:
    commands = {name: shutil.which(name) for name in (*REQUIRED_COMMANDS, *OPTIONAL_COMMANDS)}
    versions = {
        name: command_version(commands[name], VERSION_ARGS[name])
        for name in commands
    }
    files = {name: (ROOT / name).is_file() for name in REQUIRED_FILES}
    errors = [f"missing command: {name}" for name in REQUIRED_COMMANDS if not commands[name]]
    errors.extend(f"missing file: {name}" for name, exists in files.items() if not exists)
    if sys.version_info < (3, 10):
        errors.append(f"Python 3.10 or later is required, got {sys.version.split()[0]}")
    node_major = major_version(versions.get("node"))
    if node_major is not None and node_major < 22:
        errors.append(f"Node.js 22 or later is required, got {versions['node']}")

    catalog_path = ROOT / "assets/component-library/catalog.json"
    catalog: dict[str, object] = {}
    actual_counts: dict[str, int] = {}
    if catalog_path.is_file():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid component catalog: {exc}")
        for kind in KINDS:
            actual_counts[kind] = len(list((catalog_path.parent / kind).rglob("*.png")))
        expected_counts = catalog.get("counts") if isinstance(catalog.get("counts"), dict) else {}
        if expected_counts != actual_counts:
            errors.append("component catalog counts do not match files; run build_component_catalog.py")
        if catalog.get("total") != sum(actual_counts.values()):
            errors.append("component catalog total does not match files")

    result = {
        "status": "ok" if not errors else "invalid",
        "python": {"path": sys.executable, "version": sys.version.split()[0]},
        "minimum_versions": {"python": "3.10", "node": "22"},
        "required_commands": {name: commands[name] for name in REQUIRED_COMMANDS},
        "optional_commands": {name: commands[name] for name in OPTIONAL_COMMANDS},
        "command_versions": versions,
        "required_files": files,
        "component_counts": actual_counts,
        "component_total": sum(actual_counts.values()),
        "errors": errors,
        "note": "This check covers environment and packaged files only. Review rendered video separately.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
