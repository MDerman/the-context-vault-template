#!/usr/bin/env python3
"""Create and list vault project notes."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from script_utils import context_folder_note_path, resolve_vault_root


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


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def safe_filename(title: str) -> str:
    name = title.replace("/", "-").replace("\\", "-").replace(":", " -").strip()
    return name or "Untitled Project"


def ensure_context(root: Path, context: str) -> Path:
    path = root / context
    note = context_folder_note_path(path)
    if not note.exists():
        raise SystemExit(f"Context not found: {context}. Run `vault inventory`.")
    metadata = frontmatter(note.read_text(encoding="utf-8", errors="replace"))
    if str(metadata.get("context_registered", "true")).strip().lower() in {"false", "no", "0"}:
        raise SystemExit(f"Context is unregistered: {context}. Run `vault folder register {context}`.")
    return path


def find_epic(root: Path, context: str, name: str) -> Path:
    candidate = Path(name)
    if candidate.suffix == ".md" and candidate.exists():
        return candidate
    if candidate.suffix == ".md" and (root / candidate).exists():
        return root / candidate
    folder = root / context / "_obsidian" / "epics"
    matches = []
    for path in sorted(folder.glob("*.md")):
        metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        title = str(metadata.get("title") or path.stem)
        if name in {title, path.stem, str(path.relative_to(root))}:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"Epic not found in {context}: {name}. Create: vault epic create {context!r} {name!r}")
    raise SystemExit(f"Epic name is ambiguous in {context}: {name}")


def link_for(root: Path, path: Path, title: str) -> str:
    return f"[[{path.relative_to(root).with_suffix('')}|{title}]]"


def create_project(root: Path, context: str, title: str, status: str, epic_name: str | None, dry_run: bool) -> int:
    ensure_context(root, context)
    folder = root / context / "_obsidian" / "projects"
    path = folder / f"{safe_filename(title)}.md"
    if path.exists():
        raise SystemExit(f"Project already exists: {path.relative_to(root)}")

    epic_line = ""
    if epic_name:
        epic_path = find_epic(root, context, epic_name)
        epic_title = str(frontmatter(epic_path.read_text(encoding="utf-8", errors="replace")).get("title") or epic_path.stem)
        epic_line = f"epic: {yaml_quote(link_for(root, epic_path, epic_title))}\n"

    now = dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
    content = (
        "---\n"
        f"title: {yaml_quote(title)}\n"
        "type: project\n"
        f"status: {status}\n"
        "contexts:\n"
        f"  - {context}\n"
        f"{epic_line}"
        f"created: {now}\n"
        "---\n"
    )

    if dry_run:
        print(f"would create: {path.relative_to(root)}")
        print(content, end="")
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"created: {path.relative_to(root)}")
    return 0


def list_projects(root: Path, context: str | None) -> int:
    contexts = [context] if context else []
    if not contexts:
        for child in sorted(root.iterdir()):
            note = context_folder_note_path(child)
            if not child.is_dir() or not note.exists():
                continue
            metadata = frontmatter(note.read_text(encoding="utf-8", errors="replace"))
            if str(metadata.get("context_registered", "true")).strip().lower() in {"false", "no", "0"}:
                continue
            contexts.append(child.name)
    for context_name in contexts:
        folder = root / context_name / "_obsidian" / "projects"
        print(f"{context_name}:")
        if not folder.exists():
            print("  - none")
            continue
        items = sorted(folder.glob("*.md"))
        if not items:
            print("  - none")
            continue
        for path in items:
            metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            title = str(metadata.get("title") or path.stem)
            status = str(metadata.get("status") or "")
            suffix = f" [{status}]" if status else ""
            print(f"  - {title}{suffix} -> {path.relative_to(root)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage vault project notes.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Create a project note.")
    create.add_argument("context")
    create.add_argument("title")
    create.add_argument("--status", default="backlog")
    create.add_argument("--epic", default=None)
    create.add_argument("--dry-run", action="store_true")
    listing = sub.add_parser("list", help="List project notes.")
    listing.add_argument("--context", default=None)
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    if args.command == "create":
        return create_project(root, args.context, args.title, args.status, args.epic, args.dry_run)
    if args.command == "list":
        return list_projects(root, args.context)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
