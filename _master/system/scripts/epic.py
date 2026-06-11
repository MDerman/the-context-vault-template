#!/usr/bin/env python3
"""Create, delete, list, and sync context-folder epics."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from script_utils import context_folder_note_path, resolve_vault_root


MARKER = "managed-by: _master/system/scripts/epic.py"
BEGIN_MASTER_VIEWS = f"  # BEGIN {MARKER}: epic views"
END_MASTER_VIEWS = f"  # END {MARKER}: epic views"
STATUS_COLUMN_ORDER = '["backlog","up-next","to-be-resumed","ongoing","in-progress","done","archived"]'


@dataclass(frozen=True)
class Epic:
    context_folder: str
    path: Path
    title: str
    status: str

    @property
    def link_target(self) -> str:
        return f"{self.context_folder}/_obsidian/epics/{self.path.stem}"

    @property
    def view_name(self) -> str:
        return f"{context_label(self.context_folder)} - {self.title}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage TaskNotes epics for context folders.")
    parser.add_argument(
        "--root",
        default=None,
        help="Workspace root. Defaults to auto-discovery from the current directory or script location.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create an epic note and sync its task Bases.")
    create_parser.add_argument("context_folder", help="Context folder, e.g. impression.")
    create_parser.add_argument("title", help="Epic title.")
    create_parser.add_argument("--status", default="in-progress", help="Epic status. Defaults to in-progress.")
    create_parser.add_argument("--dry-run", action="store_true", help="Print intended changes without writing.")

    delete_parser = subparsers.add_parser("delete", help="Delete an epic note and sync generated task Bases.")
    delete_parser.add_argument("context_folder", help="Context folder, e.g. impression.")
    delete_parser.add_argument("title", help="Epic title or epic note filename stem.")
    delete_parser.add_argument(
        "--force",
        action="store_true",
        help="Delete even when tasks still link to this epic. Leaves those task links unchanged.",
    )
    delete_parser.add_argument("--dry-run", action="store_true", help="Print intended changes without writing.")

    rename_parser = subparsers.add_parser("rename", help="Rename an epic and preserve linked tasks/views.")
    rename_parser.add_argument("context_folder", help="Context folder, e.g. impression.")
    rename_parser.add_argument("old_title", help="Existing epic title or epic note filename stem.")
    rename_parser.add_argument("new_title", help="New epic title.")
    rename_parser.add_argument("--dry-run", action="store_true", help="Print intended changes without writing.")

    list_parser = subparsers.add_parser("list", help="List epics in context folders.")
    list_parser.add_argument("--context-folders", help="Comma-separated context folders. Defaults to active folders.")
    list_parser.add_argument("--all", action="store_true", help="Include archived context folders.")

    sync_parser = subparsers.add_parser("sync", help="Regenerate epic task Bases and master kanban epic views.")
    sync_parser.add_argument("--context-folders", help="Comma-separated context folders. Defaults to active folders.")
    sync_parser.add_argument("--all", action="store_true", help="Include archived context folders.")
    sync_parser.add_argument("--dry-run", action="store_true", help="Print intended changes without writing.")

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
        epics.append(
            Epic(
                context_folder=context_root.name,
                path=path,
                title=metadata.get("title") or path.stem,
                status=metadata.get("status") or "",
            )
        )
    return epics


def safe_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value or "Untitled Epic"


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "untitled-epic"


def yaml_double(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def obsidian_link_target(value: str) -> str:
    return value.replace("|", "%7C")


def context_label(context_folder: str) -> str:
    return " ".join(part.capitalize() for part in context_folder.split("-"))


def ensure_context_folder(context_root: Path) -> None:
    if not context_root.exists():
        raise SystemExit(f"Context folder does not exist: {context_root}")
    if not context_folder_note_path(context_root).exists():
        raise SystemExit(f"Context folder is missing its folder note: {context_root}")


def create_epic(root: Path, context_folder: str, title: str, status: str, dry_run: bool) -> int:
    context_root = root / context_folder
    ensure_context_folder(context_root)

    epics_dir = context_root / "_obsidian/epics"
    filename = safe_filename(title) + ".md"
    epic_path = epics_dir / filename
    if epic_path.exists():
        raise SystemExit(f"Epic already exists: {epic_path.relative_to(root)}")

    content = f"""---
title: {yaml_double(title)}
type: epic
status: {status}
contexts:
  - {context_folder}
created: {dt.date.today().isoformat()}
---
"""
    if dry_run:
        print(f"would create: {epic_path.relative_to(root)}", flush=True)
    else:
        epics_dir.mkdir(parents=True, exist_ok=True)
        epic_path.write_text(content, encoding="utf-8")
        print(f"created: {epic_path.relative_to(root)}", flush=True)

    return sync(root, context_folder, include_archived=True, dry_run=dry_run)


def find_epic(context_root: Path, title_or_stem: str) -> Epic | None:
    wanted_stem = safe_filename(title_or_stem)
    wanted_slug = slug(title_or_stem)
    for epic in discover_epics(context_root):
        if epic.path.stem == title_or_stem or epic.path.stem == wanted_stem:
            return epic
        if epic.title == title_or_stem or slug(epic.title) == wanted_slug:
            return epic
    return None


def linked_task_paths(root: Path, epic: Epic) -> list[Path]:
    task_dir = root / epic.context_folder / "_obsidian/tasks"
    if not task_dir.exists():
        return []
    needles = [
        f"[[{epic.link_target}",
        f'link("{epic.link_target}")',
    ]
    paths = []
    for path in sorted(task_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(needle in text for needle in needles):
            paths.append(path)
    return paths


def replace_frontmatter_title(text: str, new_title: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text

    frontmatter_text = text[: end + 4]
    body = text[end + 4 :]
    replacement = f"title: {yaml_double(new_title)}"
    title_re = re.compile(r"^title: .*$", re.MULTILINE)
    if title_re.search(frontmatter_text):
        frontmatter_text = title_re.sub(replacement, frontmatter_text, count=1)
    else:
        frontmatter_text = frontmatter_text.replace("---\n", f"---\n{replacement}\n", 1)
    return frontmatter_text + body


def replace_epic_links(text: str, old_epic: Epic, new_link_target: str, new_title: str) -> str:
    old_target = old_epic.link_target
    new_target = obsidian_link_target(new_link_target)
    text = re.sub(
        r"\[\[" + re.escape(old_target) + r"(?:\|[^\]]*)?\]\]",
        f"[[{new_target}|{new_title}]]",
        text,
    )
    text = text.replace(f'link("{old_target}")', f'link("{new_link_target}")')
    return text


def rename_epic(root: Path, context_folder: str, old_title: str, new_title: str, dry_run: bool) -> int:
    context_root = root / context_folder
    ensure_context_folder(context_root)
    old_epic = find_epic(context_root, old_title)
    if old_epic is None:
        raise SystemExit(f"Epic not found in {context_folder}: {old_title}")

    new_path = old_epic.path.with_name(safe_filename(new_title) + ".md")
    if new_path.exists() and new_path != old_epic.path:
        raise SystemExit(f"Cannot rename; destination epic already exists: {new_path.relative_to(root)}")

    new_link_target = f"{context_folder}/_obsidian/epics/{new_path.stem}"
    linked_tasks = linked_task_paths(root, old_epic)

    if dry_run:
        print(f"would rename: {old_epic.path.relative_to(root)} -> {new_path.relative_to(root)}", flush=True)
        if linked_tasks:
            print(f"would update {len(linked_tasks)} linked task(s)", flush=True)
            for path in linked_tasks[:20]:
                print(f"- {path.relative_to(root)}", flush=True)
            if len(linked_tasks) > 20:
                print(f"- ...and {len(linked_tasks) - 20} more", flush=True)
    else:
        text = old_epic.path.read_text(encoding="utf-8", errors="replace")
        new_text = replace_frontmatter_title(text, new_title)
        if new_path == old_epic.path:
            old_epic.path.write_text(new_text, encoding="utf-8")
        else:
            new_path.write_text(new_text, encoding="utf-8")
            old_epic.path.unlink()
        print(f"renamed: {old_epic.path.relative_to(root)} -> {new_path.relative_to(root)}", flush=True)

        updated_count = 0
        for path in linked_tasks:
            task_text = path.read_text(encoding="utf-8", errors="replace")
            updated_text = replace_epic_links(task_text, old_epic, new_link_target, new_title)
            if updated_text != task_text:
                path.write_text(updated_text, encoding="utf-8")
                updated_count += 1
        print(f"updated linked tasks: {updated_count}", flush=True)

    return sync(root, context_folder, include_archived=True, dry_run=dry_run)


def delete_epic(root: Path, context_folder: str, title_or_stem: str, force: bool, dry_run: bool) -> int:
    context_root = root / context_folder
    ensure_context_folder(context_root)
    epic = find_epic(context_root, title_or_stem)
    if epic is None:
        raise SystemExit(f"Epic not found in {context_folder}: {title_or_stem}")

    linked_tasks = linked_task_paths(root, epic)
    if linked_tasks and not force:
        print(
            f"Refusing to delete {epic.path.relative_to(root)} because {len(linked_tasks)} task(s) still link to it.",
            file=sys.stderr,
        )
        for path in linked_tasks[:20]:
            print(f"- {path.relative_to(root)}", file=sys.stderr)
        if len(linked_tasks) > 20:
            print(f"- ...and {len(linked_tasks) - 20} more", file=sys.stderr)
        print("Re-run with --force if you want to delete the epic note anyway.", file=sys.stderr)
        return 2

    generated_base = root / context_folder / "_obsidian/bases" / f"tasks-epic-{slug(epic.title)}-kanban.base"
    for path in (epic.path, generated_base):
        if not path.exists():
            continue
        if dry_run:
            print(f"would delete: {path.relative_to(root)}", flush=True)
        else:
            path.unlink()
            print(f"deleted: {path.relative_to(root)}", flush=True)

    return sync(root, context_folder, include_archived=True, dry_run=dry_run)


def master_view_content(epics: list[Epic]) -> str:
    lines = [BEGIN_MASTER_VIEWS]
    for epic in epics:
        lines.extend(
            [
                "  - type: tasknotesKanban",
                f"    name: {yaml_double(epic.view_name)}",
                "    filters:",
                "      and:",
                f'        - epic == link("{epic.link_target}")',
                "    groupBy:",
                "      property: status",
                "      direction: ASC",
                "    swimLane: note.projects",
                "    order:",
                "      - status",
                "      - due",
                "      - scheduled",
                "      - contexts",
                "      - file.tags",
                "      - blockedBy",
                "      - file.tasks",
                "      - projects",
                "      - complete_instances",
                "      - recurrence",
                "      - epic",
                "    sort:",
                "      - column: tasknotes_manual_order",
                "        direction: DESC",
                "    options:",
                "      columnWidth: 280",
                "      maxSwimlaneHeight: 99999",
                "      hideEmptyColumns: false",
                f"    columnOrder: '{{\"note.status\":{STATUS_COLUMN_ORDER}}}'",
                "    enableSearch: true",
                "    consolidateStatusIcon: true",
            ]
        )
    lines.append(END_MASTER_VIEWS)
    return "\n".join(lines) + "\n"


def update_master_kanban_views(root: Path, context_roots: list[Path], dry_run: bool) -> str:
    path = root / "_master/_obsidian/bases/tasks-kanban-v1.base"
    if not path.exists():
        return "missing"

    epics = [epic for context_root in context_roots for epic in discover_epics(context_root)]
    block = master_view_content(epics)
    text = path.read_text(encoding="utf-8", errors="replace")

    start = text.find(BEGIN_MASTER_VIEWS)
    end = text.find(END_MASTER_VIEWS)
    if start != -1 and end != -1 and end > start:
        end += len(END_MASTER_VIEWS)
        if end < len(text) and text[end : end + 1] == "\n":
            end += 1
        updated = text[:start] + block + text[end:]
        action = "updated"
    elif start == -1 and end == -1:
        updated = text.rstrip() + "\n" + block
        action = "created"
    else:
        raise SystemExit(f"Found a partial managed epic views block in {path.relative_to(root)}")

    if updated == text:
        return "unchanged"
    if dry_run:
        return f"would {action}"

    path.write_text(updated, encoding="utf-8")
    return action


def run_epic_base_generator(root: Path, context_folders: str | None, include_archived: bool, dry_run: bool) -> int:
    script = root / "_master/system/scripts/generate_epic_kanban_views.py"
    cmd = [sys.executable, str(script), "--root", str(root), "--prune"]
    if context_folders:
        cmd.extend(["--context-folders", context_folders])
    if include_archived:
        cmd.append("--all")
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, cwd=root)
    return result.returncode


def sync(root: Path, context_folders: str | None, include_archived: bool, dry_run: bool) -> int:
    context_roots = discover_context_folders(root, context_folders, include_archived)
    if not context_roots:
        print("No matching context folders found.", file=sys.stderr)
        return 1

    generator_status = run_epic_base_generator(root, context_folders, include_archived, dry_run)
    if generator_status != 0:
        return generator_status

    result = update_master_kanban_views(root, context_roots, dry_run)
    print(f"master tasks-kanban-v1 epic views: {result}: _master/_obsidian/bases/tasks-kanban-v1.base")
    return 0


def list_epics(root: Path, context_folders: str | None, include_archived: bool) -> int:
    context_roots = discover_context_folders(root, context_folders, include_archived)
    for context_root in context_roots:
        epics = discover_epics(context_root)
        if not epics:
            print(f"{context_root.name}: no epics")
            continue
        for epic in epics:
            status = f" ({epic.status})" if epic.status else ""
            print(f"{context_root.name}: {epic.title}{status} -> {epic.path.relative_to(root)}")
    return 0


def main() -> int:
    args = parse_args()
    root = resolve_vault_root(args.root, __file__)

    if args.command == "create":
        return create_epic(root, args.context_folder, args.title, args.status, args.dry_run)
    if args.command == "delete":
        return delete_epic(root, args.context_folder, args.title, args.force, args.dry_run)
    if args.command == "rename":
        return rename_epic(root, args.context_folder, args.old_title, args.new_title, args.dry_run)
    if args.command == "list":
        return list_epics(root, args.context_folders, args.all)
    if args.command == "sync":
        return sync(root, args.context_folders, args.all, args.dry_run)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
