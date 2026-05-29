#!/usr/bin/env python3
"""Migrate TaskNotes frontmatter from duration to timeEstimate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def task_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not folder.name[:2].isdigit():
            continue
        tasks = folder / "_obsidian/tasks"
        if tasks.is_dir():
            files.extend(sorted(tasks.rglob("*.md")))
    return files


def migrate_text(text: str) -> tuple[str, bool]:
    if not text.startswith("---\n"):
        return text, False
    end = text.find("\n---", 4)
    if end == -1:
        return text, False
    frontmatter = text[4:end].splitlines()
    body = text[end:]
    has_time_estimate = any(line.startswith("timeEstimate:") for line in frontmatter)
    changed = False
    migrated: list[str] = []
    for line in frontmatter:
        if line.startswith("duration:"):
            changed = True
            if not has_time_estimate:
                migrated.append("timeEstimate:" + line.split(":", 1)[1])
                has_time_estimate = True
            continue
        migrated.append(line)
    if not changed:
        return text, False
    return "---\n" + "\n".join(migrated) + body, True


def run(root: Path, apply: bool) -> dict[str, object]:
    changed_files: list[str] = []
    for path in task_files(root):
        text = path.read_text(encoding="utf-8")
        new_text, changed = migrate_text(text)
        if not changed:
            continue
        changed_files.append(path.relative_to(root).as_posix())
        if apply:
            path.write_text(new_text, encoding="utf-8")
    return {
        "migration": "2026_05_29_tasknotes_duration_to_time_estimate",
        "mode": "apply" if apply else "dry-run",
        "changed_files": changed_files,
        "changed_count": len(changed_files),
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
    print(f"changed files: {payload['changed_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
