#!/usr/bin/env python3
"""Create TaskNotes task files with validated vault routing."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from script_utils import context_folder_note_path, resolve_vault_root


DEFAULT_TASK_STATUSES = {"backlog", "up-next", "to-be-resumed", "ongoing", "in-progress", "done", "archived"}


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text[4:end].splitlines():
        if raw_line.startswith("  - ") and current_key:
            result.setdefault(current_key, []).append(clean_scalar(raw_line[4:]))
            continue
        current_key = None
        if ":" not in raw_line or raw_line.startswith(" "):
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            result[key] = []
            current_key = key
        else:
            result[key] = clean_scalar(value)
    return result


def task_statuses(root: Path) -> set[str]:
    config = root / ".obsidian/plugins/tasknotes/data.json"
    if not config.exists():
        return DEFAULT_TASK_STATUSES
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_TASK_STATUSES
    statuses = {
        str(item.get("value") or item.get("id"))
        for item in data.get("customStatuses", [])
        if item.get("value") or item.get("id")
    }
    return statuses or DEFAULT_TASK_STATUSES


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def safe_filename(title: str) -> str:
    name = title.replace("/", "-").replace("\\", "-").replace(":", " -").strip()
    return name or "Untitled Task"


def unique_path(folder: Path, title: str) -> Path:
    base = safe_filename(title)
    path = folder / f"{base}.md"
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = folder / f"{base} {index}.md"
        if not candidate.exists():
            return candidate
        index += 1


def ensure_context(root: Path, context: str) -> None:
    note = context_folder_note_path(root / context)
    if not note.exists():
        raise SystemExit(f"Context not found: {context}. Run `vault inventory`.")
    metadata = frontmatter(note.read_text(encoding="utf-8", errors="replace"))
    if str(metadata.get("context_registered", "true")).strip().lower() in {"false", "no", "0"}:
        raise SystemExit(f"Context is unregistered: {context}. Run `vault folder register {context}`.")


def find_note(root: Path, context: str, folder_name: str, label: str) -> Path:
    candidate = Path(label)
    if candidate.suffix == ".md" and candidate.exists():
        return candidate.resolve()
    if candidate.suffix == ".md" and (root / candidate).exists():
        return root / candidate
    folder = root / context / "_obsidian" / folder_name
    matches = []
    for path in sorted(folder.glob("*.md")):
        metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        title = str(metadata.get("title") or path.stem)
        if label in {title, path.stem, str(path.relative_to(root))}:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    kind = "Project" if folder_name == "projects" else "Epic"
    create = f"vault project create {context!r} {label!r}" if folder_name == "projects" else f"vault epic create {context!r} {label!r}"
    if not matches:
        raise SystemExit(f"{kind} not found in {context}: {label}. Create: {create}")
    raise SystemExit(f"{kind} name is ambiguous in {context}: {label}")


def note_link(root: Path, path: Path) -> str:
    metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    title = str(metadata.get("title") or path.stem)
    return f"[[{path.relative_to(root).with_suffix('')}|{title}]]"


def create_task(root: Path, args: argparse.Namespace) -> int:
    ensure_context(root, args.context)
    statuses = task_statuses(root)
    if args.status not in statuses:
        raise SystemExit(f"Unknown task status: {args.status}. Available: {', '.join(sorted(statuses))}")

    project_links = [
        note_link(root, find_note(root, args.context, "projects", project))
        for project in args.project
    ]
    epic_link = note_link(root, find_note(root, args.context, "epics", args.epic)) if args.epic else None

    folder = root / args.context / "_obsidian" / "tasks"
    path = unique_path(folder, args.title)
    now = dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
    lines = [
        "---",
        f"title: {yaml_quote(args.title)}",
        f"status: {args.status}",
        f"priority: {args.priority}",
        "contexts:",
        f"  - {args.context}",
        f"dateCreated: {now}",
        f"dateModified: {now}",
    ]
    if args.due:
        lines.append(f"due: {args.due}")
    if args.scheduled:
        lines.append(f"scheduled: {args.scheduled}")
    if args.time_estimate is not None:
        lines.append(f"timeEstimate: {args.time_estimate}")
    if project_links:
        lines.append("projects:")
        lines.extend(f"  - {yaml_quote(link)}" for link in project_links)
    if epic_link:
        lines.append(f"epic: {yaml_quote(epic_link)}")
    lines.extend(["tags:", "  - task", "---"])
    content = "\n".join(lines) + "\n"
    if args.body:
        content += f"{args.body.rstrip()}\n"

    if args.dry_run:
        print(f"would create: {path.relative_to(root)}")
        print(content, end="")
        return 0

    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"created: {path.relative_to(root)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create TaskNotes tasks with validated context/project/epic links.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Create a TaskNotes task.")
    create.add_argument("context", help="Context folder, e.g. impression.")
    create.add_argument("title", help="Task title.")
    create.add_argument("--project", action="append", default=[], help="Existing project title/path. Repeat for multiple.")
    create.add_argument("--epic", default=None, help="Existing epic title/path.")
    create.add_argument("--status", default="backlog")
    create.add_argument("--priority", default="normal", choices=["highest", "high", "normal", "low", "lowest"])
    create.add_argument("--due", default=None, help="TaskNotes due date/datetime.")
    create.add_argument("--scheduled", default=None, help="TaskNotes scheduled date/datetime.")
    create.add_argument("--time-estimate", type=int, default=None, help="Minutes.")
    create.add_argument("--body", default=None)
    create.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    if args.command == "create":
        return create_task(root, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
