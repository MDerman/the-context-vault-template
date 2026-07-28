#!/usr/bin/env python3
"""Print live, low-context vault routing inventory for agents."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from script_utils import context_folder_note_path, resolve_vault_root
from vault_layout import VAULT_PERIODIC_DIR


DEFAULT_TASK_STATUSES = ["backlog", "up-next", "to-be-resumed", "ongoing", "in-progress", "done", "archived"]
ROUTING_TASK_STATUSES = ["in-progress", "ongoing", "to-be-resumed", "up-next"]
PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")


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


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "1"}


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "monthly": f"{day.year}-{day.month:02d}",
        "quarterly": f"{day.year}-Q{quarter}",
        "yearly": str(day.year),
    }


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


def context_periodic_paths(root: Path, name: str, periods: dict[str, str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for period, period_id in periods.items():
        path = Path(name) / "_obsidian/periodic" / period / f"{period_id}.md"
        result[period] = {"path": path.as_posix(), "exists": (root / path).exists()}
    return result


def discover_contexts(root: Path, periods: dict[str, str]) -> list[dict[str, Any]]:
    contexts = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name.startswith("_"):
            continue
        note = context_folder_note_path(child)
        if not note.exists():
            continue
        metadata = frontmatter(note.read_text(encoding="utf-8", errors="replace"))
        if str(metadata.get("context_registered", "true")).strip().lower() in {"false", "no", "0"}:
            continue
        contexts.append(
            {
                "name": child.name,
                "status": str(metadata.get("status") or "none"),
                "context_type": str(metadata.get("context_type") or "business"),
                "content_enabled": truthy(metadata.get("content_enabled")),
                "default_capture": truthy(metadata.get("default_capture")),
                "note_path": note.relative_to(root).as_posix(),
                "periodic_notes": context_periodic_paths(root, child.name, periods),
            }
        )
    return contexts


def default_capture_context(contexts: list[dict[str, Any]]) -> str:
    for context in contexts:
        if context["default_capture"]:
            return str(context["name"])
    for context in contexts:
        if context["status"] == "active":
            return str(context["name"])
    return str(contexts[0]["name"]) if contexts else ""


def vault_periodic_paths(root: Path, periods: dict[str, str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for period, period_id in periods.items():
        path = VAULT_PERIODIC_DIR / period / f"{period_id}.md"
        result[period] = {"path": path.as_posix(), "exists": (root / path).exists()}
    return result


def current_content_schedules(root: Path, contexts: list[dict[str, Any]], day: dt.date) -> list[dict[str, str]]:
    schedules: list[dict[str, str]] = []
    for context in contexts:
        if not context["content_enabled"]:
            continue
        folder = root / str(context["name"]) / "_obsidian/content-schedules"
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            if metadata.get("type") != "content-schedule":
                continue
            start = str(metadata.get("schedule_start") or "")
            end = str(metadata.get("schedule_end") or "")
            if start and end and start <= day.isoformat() <= end:
                schedules.append(
                    {
                        "context": str(context["name"]),
                        "path": path.relative_to(root).as_posix(),
                        "schedule_start": start,
                        "schedule_end": end,
                    }
                )
    return schedules


def collect_notes(root: Path, contexts: list[dict[str, Any]], kind: str) -> dict[str, list[dict[str, Any]]]:
    folder_name = "projects" if kind == "project" else "epics"
    grouped: dict[str, list[dict[str, Any]]] = {}
    for context in contexts:
        context_name = str(context["name"])
        folder = root / context_name / "_obsidian" / folder_name
        grouped[context_name] = []
        if folder.exists():
            grouped[context_name] = [
                note_info(root, context_name, kind, path)
                for path in sorted(folder.glob("*.md"))
            ]
    return grouped


def optional_date(value: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def task_sort_key(task: dict[str, Any]) -> tuple[int, dt.date, dt.date, dt.date, str]:
    priority = {"high": 0, "normal": 1, "low": 2, "none": 3, "": 4}
    far_future = dt.date.max
    return (
        priority.get(str(task.get("priority", "")).lower(), 4),
        optional_date(task.get("due")) or far_future,
        optional_date(task.get("scheduled")) or far_future,
        optional_date(task.get("dateCreated")) or far_future,
        str(task.get("title") or "").lower(),
    )


def collect_tasks(root: Path, contexts: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, int]]]:
    grouped = {status: [] for status in ROUTING_TASK_STATUSES}
    counts: dict[str, dict[str, int]] = {}
    for context in contexts:
        name = str(context["name"])
        counts[name] = {}
        folder = root / name / "_obsidian/tasks"
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            metadata = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            status = str(metadata.get("status") or "")
            if not status:
                continue
            counts[name][status] = counts[name].get(status, 0) + 1
            if status not in grouped:
                continue
            grouped[status].append(
                {
                    "context": name,
                    "title": str(metadata.get("title") or path.stem),
                    "status": status,
                    "priority": str(metadata.get("priority") or ""),
                    "scheduled": str(metadata.get("scheduled") or ""),
                    "due": str(metadata.get("due") or ""),
                    "dateCreated": str(metadata.get("dateCreated") or ""),
                    "path": path.relative_to(root).as_posix(),
                }
            )
    for tasks in grouped.values():
        tasks.sort(key=task_sort_key)
    return grouped, counts


def build_inventory(root: Path, active_only: bool, day: dt.date | None = None) -> dict[str, Any]:
    day = day or dt.date.today()
    periods = active_periods(day)
    all_contexts = discover_contexts(root, periods)
    contexts = [item for item in all_contexts if not active_only or item["status"] == "active"]
    tasks, task_counts = collect_tasks(root, contexts)
    return {
        "date": day.isoformat(),
        "active_periods": periods,
        "default_capture_context": default_capture_context(all_contexts),
        "task_statuses": task_statuses(root),
        "contexts": contexts,
        "vault_periodic_notes": vault_periodic_paths(root, periods),
        "content_schedules": current_content_schedules(root, contexts, day),
        "task_counts": task_counts,
        "tasks": tasks,
        "backlog_counts": {name: counts.get("backlog", 0) for name, counts in task_counts.items()},
        "epics": collect_notes(root, contexts, "epic"),
        "projects": collect_notes(root, contexts, "project"),
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


def print_path_group(title: str, paths: dict[str, dict[str, Any]]) -> None:
    print(f"\n{title}:")
    for period, item in paths.items():
        missing = " (missing)" if not item["exists"] else ""
        print(f"  - {period}: {item['path']}{missing}")


def print_inventory(inventory: dict[str, Any]) -> None:
    print("Vault inventory")
    periods = inventory["active_periods"]
    print(f"Date: {inventory['date']}")
    print("Periods: " + ", ".join(f"{period}={periods[period]}" for period in PERIODS))
    print(f"Default capture: {inventory['default_capture_context'] or 'none'}")
    print(f"Task statuses: {', '.join(inventory['task_statuses'])}")
    print("\nContexts:")
    for context in inventory["contexts"]:
        flags = [context["status"], context["context_type"]]
        if context["content_enabled"]:
            flags.append("content")
        if context["default_capture"]:
            flags.append("default capture")
        print(f"  - {context['name']} [{', '.join(flags)}] -> {context['note_path']}")
        if context["status"] == "active":
            for period, item in context["periodic_notes"].items():
                missing = " (missing)" if not item["exists"] else ""
                print(f"      {period}: {item['path']}{missing}")
    print_path_group("Vault periodic rollups", inventory["vault_periodic_notes"])
    print("\nContent schedules:")
    if not inventory["content_schedules"]:
        print("  - none")
    for schedule in inventory["content_schedules"]:
        print(f"  - {schedule['context']}: {schedule['path']} ({schedule['schedule_start']} to {schedule['schedule_end']})")
    print("\nTask counts:")
    for context, counts in inventory["task_counts"].items():
        rendered = ", ".join(f"{status}={count}" for status, count in sorted(counts.items())) or "none"
        print(f"  - {context}: {rendered}")
    for status in ROUTING_TASK_STATUSES:
        print(f"\nTasks {status}:")
        tasks = inventory["tasks"][status]
        if not tasks:
            print("  - none")
        for task in tasks:
            print(f"  - {task['title']} [{task['context']}] -> {task['path']}")
    print("\nBacklog counts:")
    for context, count in inventory["backlog_counts"].items():
        print(f"  - {context}: {count}")
    print_grouped("Epics", inventory["epics"])
    print_grouped("Projects", inventory["projects"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print live vault periods, routing sources, tasks, projects, and epics.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--active-only", action="store_true", help="Show active context folders only.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    inventory = build_inventory(root, args.active_only)
    if args.json:
        print(json.dumps(inventory, indent=2))
        return 0
    print_inventory(inventory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
