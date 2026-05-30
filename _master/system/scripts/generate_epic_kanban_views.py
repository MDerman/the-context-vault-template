#!/usr/bin/env python3
"""
Generate TaskNotes Kanban Base views for each epic in each context folder.

By default, this script scans active context folders only. It writes managed `.base`
files to:

    <context-folder>/_obsidian/bases/tasks-epic-<epic-slug>-kanban.base
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from script_utils import context_folder_note_path, resolve_vault_root


MANAGED_MARKER = "managed-by: _master/system/scripts/generate_epic_kanban_views.py"
OLD_MANAGED_MARKER = "managed-by: _master/scripts/generate_epic_kanban_views.py"
MANAGED_MARKERS = (MANAGED_MARKER, OLD_MANAGED_MARKER)
DEFAULT_OUTPUT_FOLDER = "_obsidian/bases"
STATUS_COLUMN_ORDER = '["backlog","up-next","to-be-resumed","ongoing","in-progress","done","archived"]'
GENERATED_AT_RE = re.compile(r"^generated_at: .*$", re.MULTILINE)


@dataclass(frozen=True)
class Epic:
    context_folder: str
    path: Path
    title: str

    @property
    def link_target(self) -> str:
        return f"{self.context_folder}/_obsidian/epics/{self.path.stem}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one TaskNotes Kanban Base view per epic."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Workspace root. Defaults to auto-discovery from the current directory or script location.",
    )
    parser.add_argument(
        "--context-folders",
        dest="context_folders",
        help="Comma-separated context folder names to scan. Defaults to active context folders.",
    )
    parser.add_argument("--sub-vaults", dest="context_folders", help=argparse.SUPPRESS)
    parser.add_argument("--vaults", dest="context_folders", help=argparse.SUPPRESS)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include archived context folders as well as active context folders.",
    )
    parser.add_argument(
        "--output-folder",
        default=DEFAULT_OUTPUT_FOLDER,
        help=f"Output folder inside each context folder. Defaults to {DEFAULT_OUTPUT_FOLDER}.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove stale managed epic Kanban views whose source epic no longer exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes without writing files.",
    )
    return parser.parse_args()


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}

    result: dict[str, str] = {}
    for raw_line in text[4:end].splitlines():
        if ":" not in raw_line or raw_line.startswith(" "):
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        result[key.strip()] = value
    return result


def context_folder_status(context_root: Path) -> str:
    note = context_folder_note_path(context_root)
    if not note.exists():
        return ""
    metadata = frontmatter(note.read_text(encoding="utf-8", errors="replace"))
    if str(metadata.get("context_registered", "true")).strip().lower() in {"false", "no", "0"}:
        return ""
    return metadata.get("status", "")


def discover_context_folders(root: Path, requested: str | None, include_archived: bool) -> list[Path]:
    if requested:
        return [root / name.strip() for name in requested.split(",") if name.strip()]

    context_folders = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name.startswith("_"):
            continue
        if not context_folder_note_path(child).is_file():
            continue
        status = context_folder_status(child)
        if include_archived or status == "active":
            context_folders.append(child)
    return context_folders


def discover_epics(context_root: Path) -> list[Epic]:
    epics_dir = context_root / "_obsidian/epics"
    if not epics_dir.exists():
        return []

    epics = []
    for path in sorted(epics_dir.glob("*.md")):
        metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if metadata.get("type") != "epic":
            continue
        title = metadata.get("title") or path.stem
        epics.append(Epic(context_folder=context_root.name, path=path, title=title))
    return epics


def safe_filename(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "untitled-epic"


def yaml_single(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def yaml_double(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def base_content(epic: Epic) -> str:
    link_filter = f'epic == link("{epic.link_target}")'
    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    return f"""# {epic.context_folder} Epic Kanban - {epic.title}
generated: true
generated_at: {generated_at}
managed_by: "{MANAGED_MARKER}"

filters:
  and:
    - file.hasTag("task")
    - {yaml_single(link_filter)}

views:
  - type: tasknotesKanban
    name: {yaml_double(epic.title + " Kanban")}
    order:
      - status
      - priority
      - due
      - scheduled
      - projects
      - contexts
      - epic
      - file.tags
      - blockedBy
      - file.name
      - recurrence
      - complete_instances
      - file.tasks
    sort:
      - column: tasknotes_manual_order
        direction: DESC
    groupBy:
      property: status
      direction: ASC
    swimLane: note.projects
    options:
      columnWidth: 280
      maxSwimlaneHeight: 99999
      hideEmptyColumns: false
    columnOrder: '{{"note.status":{STATUS_COLUMN_ORDER}}}'
"""


def normalized_generated_content(text: str) -> str:
    return GENERATED_AT_RE.sub("generated_at: <ignored>", text)


def looks_like_legacy_generated_epic_base(path: Path, text: str) -> bool:
    return (
        path.name.startswith("tasks-epic-")
        and path.suffix == ".base"
        and "epic == link(" in text
        and "type: tasknotesKanban" in text
    )


def write_if_needed(path: Path, content: str, dry_run: bool) -> str:
    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="replace")
        managed = any(marker in existing for marker in MANAGED_MARKERS)
        if not managed and not looks_like_legacy_generated_epic_base(path, existing):
            return "skipped non-managed"
        if existing == content or normalized_generated_content(existing) == normalized_generated_content(content):
            return "unchanged"
        action = "updated" if managed else "adopted legacy generated"
    else:
        action = "created"

    if dry_run:
        return f"would {action}"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return action


def prune_stale(output_dir: Path, expected: set[Path], dry_run: bool) -> list[tuple[Path, str]]:
    if not output_dir.exists():
        return []

    results = []
    for path in sorted(output_dir.glob("*.base")):
        if path in expected:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not any(marker in text for marker in MANAGED_MARKERS):
            continue
        if dry_run:
            results.append((path, "would remove"))
        else:
            path.unlink()
            results.append((path, "removed"))
    return results


def main() -> int:
    args = parse_args()
    root = resolve_vault_root(args.root, __file__)
    context_folders = discover_context_folders(root, args.context_folders, args.all)

    if not context_folders:
        print("No matching context folders found.")
        return 1

    changed = False
    for context_root in context_folders:
        epics = discover_epics(context_root)
        output_dir = context_root / args.output_folder
        expected_paths: set[Path] = set()

        for epic in epics:
            output_path = output_dir / f"tasks-epic-{safe_filename(epic.title)}-kanban.base"
            expected_paths.add(output_path)
            result = write_if_needed(output_path, base_content(epic), args.dry_run)
            if result not in {"unchanged"}:
                changed = True
            print(f"{context_root.name}: {result}: {output_path.relative_to(root)}")

        if args.prune:
            for stale_path, result in prune_stale(output_dir, expected_paths, args.dry_run):
                if result not in {"kept non-managed"}:
                    changed = True
                print(f"{context_root.name}: {result}: {stale_path.relative_to(root)}")

        if not epics:
            print(f"{context_root.name}: no epic notes found")

    return 0 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
