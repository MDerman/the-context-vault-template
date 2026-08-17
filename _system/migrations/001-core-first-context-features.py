#!/usr/bin/env python3
"""Migrate context notes from types/content_enabled to composable capabilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def truthy(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in {"true", "yes", "1"}


def migrate_text(text: str) -> tuple[str, list[str]]:
    if not text.startswith("---\n"):
        return text, []
    end = text.find("\n---", 4)
    if end == -1:
        return text, []
    lines = text[4:end].splitlines()
    old_content = False
    schedules = False
    output: list[str] = []
    changes: list[str] = []
    for line in lines:
        if ":" not in line or line.startswith(" "):
            output.append(line)
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key == "content_enabled":
            old_content = truthy(raw_value)
            changes.append("removed content_enabled")
            continue
        if key == "context_type":
            changes.append("removed context_type")
            continue
        if key == "content_schedules_enabled":
            schedules = truthy(raw_value)
            if not schedules:
                changes.append("removed false content_schedules_enabled")
            continue
        output.append(line)
    if old_content or schedules:
        output.append("content_schedules_enabled: true")
        if old_content and not schedules:
            changes.append("enabled content schedules")
    if not changes:
        return text, []
    body_start = end + len("\n---")
    body = text[body_start:]
    return "---\n" + "\n".join(output) + "\n---" + body, changes


def registered_context_notes(root: Path) -> list[Path]:
    result: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        note = child / f"{child.name}.md"
        if note.is_file():
            result.append(note)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--report", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    changed: list[dict[str, object]] = []
    for path in registered_context_notes(root):
        original = path.read_text(encoding="utf-8")
        rendered, actions = migrate_text(original)
        if not actions:
            continue
        changed.append({"path": path.relative_to(root).as_posix(), "actions": actions})
        if args.apply:
            path.write_text(rendered, encoding="utf-8")

    report = {
        "migration": "001-core-first-context-features",
        "mode": "apply" if args.apply else "dry-run",
        "changed": changed,
        "changed_count": len(changed),
    }
    report_path = Path(args.report).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
