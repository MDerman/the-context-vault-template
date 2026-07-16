#!/usr/bin/env python3
"""Migrate legacy vault skill storage into grouped auto/manual sources."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


AUTO = {
    "_code": ["audit-repo-security", "chrome-devtools-cli", "env-tooling", "gh-open-source-pr", "playwright-cli"],
    "_video": ["ffmpeg-video-assembly", "video-qa-review"],
    "_agents": ["continue", "handoff", "summary", "write-a-skill"],
    "_vault": ["brain-dump-organizer", "vault", "vault-upgrade-repair"],
}
MANUAL = {
    "_code": [
        "chrome-extension-sampler",
        "chrome-lost-window-recovery",
        "design-an-interface",
        "domain-model",
        "improve-codebase-architecture",
        "ubiquitous-language",
    ],
    "_video": ["ai-video-production", "elevenlabs-voiceover", "heygen-avatar-render", "hyperframes-motion-graphics"],
    "_creative": ["openai-image-batch", "frontend-slides"],
    "_agents": ["grill-me"],
    "_gws": ["gmail-invoice-collector"],
}


def move(source: Path, target: Path, root: Path, apply: bool, moved: list[dict[str, str]], conflicts: list[dict[str, str]]) -> None:
    if not (source.exists() or source.is_symlink()):
        return
    entry = {"source": source.relative_to(root).as_posix(), "target": target.relative_to(root).as_posix()}
    if target.exists() or target.is_symlink():
        conflicts.append(entry)
        return
    moved.append(entry)
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)


def remove_known(path: Path, root: Path, apply: bool, removed: list[str]) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    removed.append(path.relative_to(root).as_posix())
    if not apply:
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def update_dependencies(root: Path, apply: bool) -> list[dict[str, str]]:
    path = root / "_master/system/config/deps.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    changed: list[dict[str, str]] = []
    for repo in data.get("repos", []):
        for projection in repo.get("projections", []):
            old = str(projection.get("target", ""))
            name = Path(old).name
            if name == "agent-canvas":
                new = "_master/agents/auto-skills/_creative/agent-canvas"
                new_type = "auto-skill"
            elif name == "frontend-slides":
                new = "_master/agents/manual-skills/_creative/frontend-slides"
                new_type = "manual-skill"
            elif name.startswith("gws-"):
                new = f"_master/agents/manual-skills/_gws/{name}"
                new_type = "manual-skill"
            else:
                continue
            if old == new and projection.get("type") == new_type:
                continue
            changed.append({"source": old, "target": new, "type": new_type})
            projection["target"] = new
            projection["type"] = new_type
    if changed and apply:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def run(root: Path, apply: bool) -> dict[str, Any]:
    agents = root / "_master/agents"
    catalog = agents / "skills"
    manual_root = agents / "manual-skills"
    moved: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    removed: list[str] = []

    for group, names in AUTO.items():
        for name in names:
            source = catalog / name
            if not source.is_symlink():
                move(source, agents / "auto-skills" / group / name, root, apply, moved, conflicts)
    for group, names in MANUAL.items():
        for name in names:
            source = manual_root / name
            if not source.exists():
                source = catalog / name
            if not source.is_symlink():
                move(source, manual_root / group / name, root, apply, moved, conflicts)
    if manual_root.is_dir():
        for source in sorted(manual_root.glob("gws-*")):
            move(source, manual_root / "_gws" / source.name, root, apply, moved, conflicts)

    system = catalog / ".system"
    if (system / ".codex-system-skills.marker").exists():
        remove_known(system, root, apply, removed)
    pdf = catalog / "pdf"
    if (pdf / "LICENSE.txt").exists() and (pdf / "assets").is_dir():
        remove_known(pdf, root, apply, removed)
    explain = catalog / "explain-code"
    if explain.is_dir() and not any(explain.iterdir()):
        remove_known(explain, root, apply, removed)

    known = {name for names in AUTO.values() for name in names} | {
        name for names in MANUAL.values() for name in names
    } | {"agent-canvas", "skybridge"}
    if catalog.is_dir():
        for child in sorted(catalog.iterdir()):
            if child.name in {".DS_Store", ".gitkeep"} or child.name in known or child.is_symlink():
                continue
            conflicts.append(
                {
                    "source": child.relative_to(root).as_posix(),
                    "target": "move manually into _master/agents/auto-skills or manual-skills",
                }
            )

    dependency_changes = update_dependencies(root, apply)
    return {
        "migration": "2026_07_14_skill_source_architecture",
        "mode": "apply" if apply else "dry-run",
        "moved": moved,
        "removed_known_provider_copies": removed,
        "dependency_changes": dependency_changes,
        "conflicts": conflicts,
        "result": "conflict" if conflicts else "ok",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--report", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    report = Path(args.report).expanduser().resolve()
    payload = run(root, apply=args.apply)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"moved: {len(payload['moved'])}; conflicts: {len(payload['conflicts'])}")
    return 1 if payload["conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
