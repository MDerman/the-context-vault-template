#!/usr/bin/env python3
"""Print low-context vault routing inventory for agents."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


DEFAULT_TASK_STATUSES = ["backlog", "up-next", "to-be-resumed", "ongoing", "in-progress", "done", "archived"]


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


def note_info(root: Path, context: str, kind: str, path: Path) -> dict[str, Any]:
    metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    return {
        "context": context,
        "title": str(metadata.get("title") or path.stem),
        "status": str(metadata.get("status") or ""),
        "epic": str(metadata.get("epic") or ""),
        "path": str(path.relative_to(root)),
        "kind": kind,
    }


def task_statuses(root: Path) -> list[str]:
    config = root / ".obsidian/plugins/tasknotes/data.json"
    if not config.exists():
        return DEFAULT_TASK_STATUSES
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_TASK_STATUSES
    statuses = []
    for item in data.get("customStatuses", []):
        value = item.get("value") or item.get("id")
        if value:
            statuses.append(str(value))
    return statuses or DEFAULT_TASK_STATUSES


def discover_contexts(root: Path) -> list[dict[str, Any]]:
    contexts = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not re.match(r"^\d\d-", child.name):
            continue
        home = child / "HOME.md"
        if not home.exists():
            continue
        metadata = frontmatter(home.read_text(encoding="utf-8", errors="replace"))
        contexts.append(
            {
                "name": child.name,
                "status": str(metadata.get("status") or "none"),
                "content_enabled": str(metadata.get("content_enabled") or "false").lower() in {"true", "yes", "1"},
            }
        )
    return contexts


def collect_notes(root: Path, contexts: list[dict[str, Any]], kind: str, active_only: bool) -> dict[str, list[dict[str, Any]]]:
    folder_name = "projects" if kind == "project" else "epics"
    grouped: dict[str, list[dict[str, Any]]] = {}
    for context in contexts:
        if active_only and context["status"] != "active":
            continue
        context_name = context["name"]
        folder = root / context_name / "_obsidian" / folder_name
        grouped[context_name] = []
        if not folder.exists():
            continue
        grouped[context_name] = [
            note_info(root, context_name, kind, path)
            for path in sorted(folder.glob("*.md"))
        ]
    return grouped


def build_inventory(root: Path, active_only: bool) -> dict[str, Any]:
    contexts = discover_contexts(root)
    shown_contexts = [item for item in contexts if not active_only or item["status"] == "active"]
    return {
        "task_statuses": task_statuses(root),
        "contexts": shown_contexts,
        "epics": collect_notes(root, contexts, "epic", active_only),
        "projects": collect_notes(root, contexts, "project", active_only),
    }


def print_grouped(title: str, grouped: dict[str, list[dict[str, Any]]]) -> None:
    print(f"\n{title}:")
    for context, items in grouped.items():
        print(f"  {context}:")
        if not items:
            print("    - none")
            continue
        for item in items:
            status = f" [{item['status']}]" if item["status"] else ""
            epic = f" epic={item['epic']}" if item["epic"] else ""
            print(f"    - {item['title']}{status}{epic} -> {item['path']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print vault contexts, statuses, projects, and epics.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--active-only", action="store_true", help="Show active context folders only.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    inventory = build_inventory(root, args.active_only)
    if args.json:
        print(json.dumps(inventory, indent=2))
        return 0

    print("Vault inventory")
    print(f"Task statuses: {', '.join(inventory['task_statuses'])}")
    print("\nContexts:")
    for context in inventory["contexts"]:
        content = " content" if context["content_enabled"] else ""
        print(f"  - {context['name']} [{context['status']}]{content}")
    print_grouped("Epics", inventory["epics"])
    print_grouped("Projects", inventory["projects"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
