#!/usr/bin/env python3
"""Move legacy context HOME.md files to inside-folder notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SKIP_PREFIXES = (".", "_")


def context_folders_with_legacy_home(root: Path) -> list[Path]:
    folders: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(SKIP_PREFIXES):
            continue
        if (child / "HOME.md").exists():
            folders.append(child)
    return folders


def run(root: Path, apply: bool) -> dict[str, object]:
    moved: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []

    for folder in context_folders_with_legacy_home(root):
        source = folder / "HOME.md"
        target = folder / f"{folder.name}.md"
        entry = {
            "source": source.relative_to(root).as_posix(),
            "target": target.relative_to(root).as_posix(),
        }
        if target.exists():
            conflicts.append(entry)
            continue
        moved.append(entry)
        if apply:
            source.rename(target)

    return {
        "migration": "2026_05_30_context_folder_notes",
        "mode": "apply" if apply else "dry-run",
        "moved": moved,
        "moved_count": len(moved),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
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
    print(f"moved files: {payload['moved_count']}")
    print(f"conflicts: {payload['conflict_count']}")
    return 1 if payload["conflict_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
