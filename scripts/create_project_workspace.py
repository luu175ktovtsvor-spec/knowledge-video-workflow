#!/usr/bin/env python3
"""Create a project-isolated Remotion or HyperFrames workspace."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
STARTERS = {
    "remotion": SKILL_ROOT / "assets" / "remotion-template",
    "hyperframes": SKILL_ROOT / "assets" / "hyperframes-template",
}
EXCLUDED_NAMES = {".DS_Store", ".git", "node_modules", "out", "dist"}
REQUIRED_FILES = {
    "remotion": {"package.json", "package-lock.json", "src/index.ts", "src/Root.tsx", "src/CollageKnowledgeVideo.tsx"},
    "hyperframes": {"package.json", "package-lock.json", "index.html", "hyperframes.json"},
}
PLAN_TEMPLATE = SKILL_ROOT / "assets" / "collage-plan.example.json"
COMPONENT_LIBRARY = SKILL_ROOT / "assets" / "component-library"
COMPONENT_KINDS = ("backgrounds", "characters", "groups", "modules", "props")


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def create_workspace(destination: Path, engine: str = "remotion") -> dict[str, object]:
    if engine not in STARTERS:
        raise ValueError(f"unknown engine: {engine}")
    starter = STARTERS[engine]
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    if destination == Path(destination.anchor) or destination == Path.home().resolve():
        raise ValueError("destination must be a new task-specific directory, not a broad root")
    if is_within(destination, SKILL_ROOT.resolve()):
        raise ValueError("project workspaces must be created outside the installed Skill")
    missing = sorted(relative for relative in REQUIRED_FILES[engine] if not (starter / relative).is_file())
    if missing:
        raise ValueError(f"starter is incomplete: {missing}")
    if not PLAN_TEMPLATE.is_file():
        raise ValueError("collage plan template is missing")
    component_catalog_path = COMPONENT_LIBRARY / "catalog.json"
    if not component_catalog_path.is_file():
        raise ValueError("component library catalog is missing")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        starter,
        destination,
        ignore=shutil.ignore_patterns(*EXCLUDED_NAMES),
    )
    shutil.copy2(PLAN_TEMPLATE, destination / "collage-plan.json")
    component_destination = (destination / "public" / "media" / "house-components") if engine == "remotion" else (destination / "assets" / "house-components")
    component_destination.mkdir(parents=True, exist_ok=True)
    for kind in COMPONENT_KINDS:
        shutil.copytree(
            COMPONENT_LIBRARY / kind,
            component_destination / kind,
            ignore=shutil.ignore_patterns(*EXCLUDED_NAMES),
        )
    component_catalog = json.loads(component_catalog_path.read_text(encoding="utf-8"))
    for entry in component_catalog.get("entries", []):
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            entry["path"] = entry["path"].replace(
                "assets/component-library/", ("media/house-components/" if engine == "remotion" else "assets/house-components/"), 1
            )
    (component_destination / "catalog.json").write_text(
        json.dumps(component_catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    leaked = sorted(
        str(path.relative_to(destination))
        for path in destination.rglob("*")
        if path.name in EXCLUDED_NAMES
    )
    if leaked:
        shutil.rmtree(destination)
        raise RuntimeError(f"excluded starter artifacts leaked into the workspace: {leaked}")
    return {
        "status": "ok",
        "workspace": str(destination),
        "engine": engine,
        "starter": str(starter),
        "plan": str(destination / "collage-plan.json"),
        "component_library": str(component_destination),
        "component_count": component_catalog.get("total"),
        "next_steps": [
            "cd into the workspace",
            "run npm ci",
            "choose scene or diagram stage_mode for every beat",
            f"select components from {component_destination.relative_to(destination)}",
            "edit and validate collage-plan.json",
            "render and review the amount of representative content appropriate to the project",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--engine", choices=sorted(STARTERS), default="remotion")
    args = parser.parse_args()
    try:
        result = create_workspace(args.destination, args.engine)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
