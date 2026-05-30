#!/usr/bin/env python3
"""Generate compact agent-readable state for this Obsidian workspace."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from script_utils import configured_context_folders, context_folder_note_path, resolve_vault_root


DEFAULT_ENTITIES = [
    "personal",
    "personal-brand",
    "business",
]

MARKER = "managed-by: _master/system/scripts/context.py"
AGENT_DIR = Path("_master/system/context")
AGENT_CONTEXT_MARKDOWN_PATH = AGENT_DIR / "CONTEXT.md"
LEGACY_AGENT_CONTEXT_MARKDOWN_PATH = AGENT_DIR / ("context" + ".md")
LEGACY_AGENT_SYSTEM_DIR = Path("_master/system/context/system")
DASHBOARD_PATH = Path("_master/Dashboard.md")
SYSTEM_NOTES = {
    "context": "_master/01-Context.md",
    "identity": "_master/02-Identity.md",
    "momentum": "_master/03-Momentum.md",
}


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "quarterly": f"{day.year}-Q{quarter}",
        "yearly": f"{day.year}",
    }


def parse_entities(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def simple_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if value == "":
            data[key] = []
        elif value.lower() == "true":
            data[key] = True
        elif value.lower() == "false":
            data[key] = False
        else:
            data[key] = value.strip('"').strip("'")
    return data


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()


def resolve_obsidian_note_path(root: Path, note_ref: str) -> tuple[Path | None, str | None, str]:
    clean_ref = note_ref.split("|", 1)[0].strip()
    path_part, _, heading = clean_ref.partition("#")
    candidates = [root / path_part]
    if not path_part.endswith(".md"):
        candidates.append(root / f"{path_part}.md")
    if "/_periodic/" in path_part:
        candidates.append(root / path_part.replace("/_periodic/", "/_obsidian/periodic/"))
        if not path_part.endswith(".md"):
            candidates.append(root / f"{path_part.replace('/_periodic/', '/_obsidian/periodic/')}.md")
    for path in candidates:
        if path.is_file():
            return path, heading or None, clean_ref
    return None, heading or None, clean_ref


def extract_heading_section(text: str, heading: str) -> str | None:
    body = strip_frontmatter(text)
    lines = body.splitlines()
    heading_re = re.compile(r"^(#{1,6})\s+" + re.escape(heading.strip()) + r"\s*$")
    start_index: int | None = None
    start_level = 0
    for index, line in enumerate(lines):
        match = heading_re.match(line)
        if match:
            start_index = index + 1
            start_level = len(match.group(1))
            break
    if start_index is None:
        return None
    end_index = len(lines)
    for index in range(start_index, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= start_level:
            end_index = index
            break
    return "\n".join(lines[start_index:end_index]).strip()


def render_embed(root: Path, note_ref: str) -> str:
    path, heading, clean_ref = resolve_obsidian_note_path(root, note_ref)
    if not path:
        return f"_Unresolved embed: `![[{clean_ref}]]`._"
    text = path.read_text(encoding="utf-8")
    content = extract_heading_section(text, heading) if heading else strip_frontmatter(text)
    if content is None:
        rel_path = path.relative_to(root)
        return f"_Missing heading `{heading}` in `{rel_path}`._"
    if not content.strip():
        content = "_No content yet._"
    rel_path = path.relative_to(root)
    source = f"{rel_path}#{heading}" if heading else str(rel_path)
    return f"_Source: `{source}`_\n\n{content.strip()}"


def realize_sync_embeds(root: Path, text: str) -> str:
    def replace_sync(match: re.Match[str]) -> str:
        body = match.group(1)
        embed_refs = re.findall(r"!\[\[([^\]]+)]]", body)
        if not embed_refs:
            return body.strip()
        return "\n\n".join(render_embed(root, embed_ref) for embed_ref in embed_refs)

    return re.sub(r"```sync\n(.*?)\n```", replace_sync, text, flags=re.S)


def realized_system_note(root: Path, source_path: str, generated_at: str) -> str:
    path = root / source_path
    body = realize_sync_embeds(root, strip_frontmatter(path.read_text(encoding="utf-8")))
    return f"""---
type: agent-system
generated: true
generated_at: {generated_at}
managed_by: "{MARKER}"
source: {source_path}
---
{body.strip()}
"""


def is_generated_agent_system_note(path: Path) -> bool:
    props = simple_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    return props.get("type") == "agent-system" and props.get("generated") is True


def write_realized_system_notes(root: Path, generated_at: str) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for key, source_path in SYSTEM_NOTES.items():
        source = root / source_path
        if not source.exists():
            continue
        output_path = AGENT_DIR / source.name
        write_if_changed(root / output_path, realized_system_note(root, source_path, generated_at))
        outputs[key] = str(output_path)
    cleanup_legacy_agent_system_notes(root)
    cleanup_stale_agent_system_notes(root, {Path(path).name for path in SYSTEM_NOTES.values()})
    return outputs


def cleanup_stale_agent_system_notes(root: Path, active_names: set[str]) -> None:
    agent_dir = root / AGENT_DIR
    if not agent_dir.exists():
        return
    for path in sorted(agent_dir.glob("*.md")):
        if path.name in active_names:
            continue
        if is_generated_agent_system_note(path):
            path.unlink()
            print(f"deleted {path}")


def cleanup_legacy_agent_system_notes(root: Path) -> None:
    legacy_dir = root / LEGACY_AGENT_SYSTEM_DIR
    if not legacy_dir.exists():
        return
    for path in sorted(legacy_dir.glob("*.md")):
        if is_generated_agent_system_note(path):
            path.unlink()
            print(f"deleted {path}")


def entity_status(root: Path, entity: str) -> str:
    path = context_folder_note_path(root / entity)
    if not path.exists():
        return ""
    return str(simple_frontmatter(path.read_text(encoding="utf-8")).get("status", "")).strip().lower()


def entity_content_enabled(root: Path, entity: str) -> bool:
    path = context_folder_note_path(root / entity)
    if not path.exists():
        return False
    return bool(simple_frontmatter(path.read_text(encoding="utf-8")).get("content_enabled", False))


def entity_context_type(root: Path, entity: str) -> str:
    path = context_folder_note_path(root / entity)
    if not path.exists():
        return ""
    return str(simple_frontmatter(path.read_text(encoding="utf-8")).get("context_type", "")).strip().lower()


def entity_default_capture(root: Path, entity: str) -> bool:
    path = context_folder_note_path(root / entity)
    if not path.exists():
        return False
    return bool(simple_frontmatter(path.read_text(encoding="utf-8")).get("default_capture", False))


def entity_statuses(root: Path, configured: list[str]) -> dict[str, str]:
    return {entity: entity_status(root, entity) for entity in configured if (root / entity).is_dir()}


def entity_context_types(root: Path, configured: list[str]) -> dict[str, str]:
    return {entity: entity_context_type(root, entity) for entity in configured if (root / entity).is_dir()}


def content_enabled_entities(root: Path, configured: list[str]) -> list[str]:
    return [entity for entity in configured if (root / entity).is_dir() and entity_content_enabled(root, entity)]


def default_capture_context_folder(root: Path, configured: list[str], selected: list[str]) -> str:
    for entity in configured:
        if (root / entity).is_dir() and entity_default_capture(root, entity):
            return entity
    if selected:
        return selected[0]
    return configured[0] if configured else ""


def resolve_entities(root: Path, configured: list[str], explicit: list[str], include_all: bool) -> list[str]:
    if include_all and explicit:
        raise SystemExit("Use either --all or --context-folders, not both.")
    if explicit:
        missing = [entity for entity in explicit if not (root / entity).is_dir()]
        if missing:
            raise SystemExit(f"Explicit context folder(s) not found: {', '.join(missing)}")
        return explicit

    selected: list[str] = []
    for entity in configured:
        entity_path = root / entity
        if not entity_path.is_dir():
            print(f"warning: configured context folder not found: {entity}", file=sys.stderr)
            continue
        if include_all or entity_status(root, entity) == "active":
            selected.append(entity)
    return selected


def collect_tasks(root: Path, entities: list[str], today: dt.date) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "in_progress": [],
        "ongoing": [],
        "to_be_resumed": [],
        "up_next": [],
        "backlog": [],
    }
    for entity in entities:
        task_dir = root / entity / "_obsidian/tasks"
        for path in sorted(task_dir.glob("*.md")):
            props = simple_frontmatter(path.read_text(encoding="utf-8"))
            tags = props.get("tags", [])
            if "task" not in tags:
                continue
            item = {
                "title": props.get("title", path.stem),
                "path": str(path.relative_to(root)),
                "status": props.get("status", ""),
                "priority": props.get("priority", ""),
                "scheduled": props.get("scheduled", ""),
                "due": props.get("due", ""),
                "dateCreated": props.get("dateCreated", ""),
                "contexts": props.get("contexts", []),
            }
            status = str(item["status"])
            if status == "in-progress":
                groups["in_progress"].append(item)
            elif status == "ongoing":
                groups["ongoing"].append(item)
            elif status == "to-be-resumed":
                groups["to_be_resumed"].append(item)
            elif status == "up-next":
                groups["up_next"].append(item)
            elif status == "backlog":
                groups["backlog"].append(item)
    for items in groups.values():
        items.sort(key=task_sort_key)
    return groups


def parse_optional_date(value: str) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def task_sort_key(task: dict[str, Any]) -> tuple[int, dt.date, dt.date, dt.date, str]:
    priority_order = {
        "high": 0,
        "normal": 1,
        "low": 2,
        "none": 3,
        "": 4,
    }
    far_future = dt.date.max
    created = parse_optional_date(str(task.get("dateCreated", ""))) or far_future
    return (
        priority_order.get(str(task.get("priority", "")).lower(), 4),
        parse_optional_date(str(task.get("due", ""))) or far_future,
        parse_optional_date(str(task.get("scheduled", ""))) or far_future,
        created,
        str(task.get("title") or "").lower(),
    )


def markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def task_lines(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "- None"
    return "\n".join(
        f"- [[{task['path']}|{task['title']}]]"
        f" ({task.get('status') or 'no status'}, {task.get('priority') or 'no priority'})"
        for task in tasks
    )


def agent_periodic_paths(periods: dict[str, str]) -> dict[str, str]:
    return {period: str(AGENT_DIR / f"{period_id}.md") for period, period_id in periods.items()}


def context_markdown(
    entities: list[str],
    selected_entities: list[str],
    statuses: dict[str, str],
    context_types: dict[str, str],
    periods: dict[str, str],
    tasks: dict[str, list[dict[str, Any]]],
    content_entities: list[str],
    default_capture_entity: str,
    content_schedules: list[dict[str, str]],
    generated_at: str,
    system_packets: dict[str, str],
) -> str:
    agent_periodic = [f"`{path}`" for path in agent_periodic_paths(periods).values()]
    system_packet_lines = [f"`{path}`" for path in system_packets.values()]
    context_folder_lines = []
    for entity in entities:
        pieces = [statuses.get(entity) or "none"]
        if context_types.get(entity):
            pieces.append(context_types[entity])
        if entity in content_entities:
            pieces.append("content enabled")
        context_folder_lines.append(f"`{entity}`: {', '.join(pieces)}")
    content_schedule_lines = [
        f"`{schedule['path']}` ({schedule['schedule_start']} to {schedule['schedule_end']})"
        for schedule in content_schedules
    ]
    declaration_lines = [f"`{entity}/DECLARATION.md`" for entity in selected_entities]
    content_view_lines = [
        "`_master/_obsidian/bases/content-calendar.base`",
        "`_master/_obsidian/bases/content-kanban.base`",
    ]
    return f"""---
type: agent-context
generated: true
generated_at: {generated_at}
managed_by: "{MARKER}"
---
# Agent Context

## Active Periods

- Daily: {periods["daily"]}
- Weekly: {periods["weekly"]}
- Quarterly: {periods["quarterly"]}
- Yearly: {periods["yearly"]}

## Default Capture Context Folder

- `{default_capture_entity}`

## Context Folders

{markdown_list(context_folder_lines)}

## Content Schedules

{markdown_list(content_schedule_lines)}

## Content Views

{markdown_list(content_view_lines)}

Folder-specific content views live under `<context-folder>/_obsidian/bases/content-*.base`.
Use the master content kanban grouped by `status` to see content by status: `idea`, `cogs-are-turning`, `draft`, `planning-scripting`, `scheduled`, `published`, `cancelled`.

## Entity Declarations

{markdown_list(declaration_lines)}

## Agent System Files

{markdown_list(system_packet_lines)}

## Agent Periodic Notes

{markdown_list(agent_periodic)}

## Context Folder Periodic Notes

Use `<context-folder>/_obsidian/periodic/<daily|weekly|quarterly|yearly>/<period-id>.md`; current period IDs are listed in `Active Periods`.

## Tasks In Progress

{task_lines(tasks["in_progress"])}

## Tasks Ongoing

{task_lines(tasks["ongoing"])}

## Tasks To Be Resumed

{task_lines(tasks["to_be_resumed"])}

## Tasks Up Next

{task_lines(tasks["up_next"])}

## Backlog Next 10

{task_lines(tasks["backlog"][:10])}

## Where To Look First

- `AGENTS.md`
- `_master/01-Context.md`
- relevant `<context-folder>/DECLARATION.md`
- `_master/system/context/CONTEXT.md`
- `_master/_obsidian/bases/tasks-today.base`
- `_master/_obsidian/bases/content-calendar.base`
- `_master/_obsidian/bases/content-kanban.base`
"""


def obsidian_link(path: str, label: str) -> str:
    target = path[:-3] if path.endswith(".md") else path
    return f"[[{target}|{label}]]"


def dashboard_markdown(
    selected_entities: list[str],
    periods: dict[str, str],
    content_schedules: list[dict[str, str]],
    generated_at: str,
) -> str:
    context_lines: list[str] = []
    for entity in selected_entities:
        context_lines.append(f"#### {entity}")
        for period, period_id in periods.items():
            path = f"{entity}/_obsidian/periodic/{period}/{period_id}.md"
            context_lines.append(f"- {period.title()}: {obsidian_link(path, period_id)}")
        context_lines.append("")
    schedule_lines = [
        obsidian_link(schedule["path"], schedule["path"].rsplit("/", 1)[-1].removesuffix(".md"))
        for schedule in content_schedules
    ]
    context_note_lines = [obsidian_link(f"{entity}/{entity}.md", entity) for entity in selected_entities]
    agent_periodics = agent_periodic_paths(periods)
    standing_lines = [
        obsidian_link("_master/system/context/01-Context.md", "01-Context"),
        obsidian_link("_master/system/context/02-Identity.md", "02-Identity"),
        obsidian_link("_master/system/context/03-Momentum.md", "03-Momentum"),
    ]
    periodic_lines = [
        obsidian_link(agent_periodics["yearly"], periods["yearly"]),
        obsidian_link(agent_periodics["weekly"], periods["weekly"]),
        obsidian_link(agent_periodics["quarterly"], periods["quarterly"]),
        obsidian_link(agent_periodics["daily"], periods["daily"]),
    ]
    inbox_lines = [obsidian_link("_master/system/inbox/BRAIN_DUMP.md", "BRAIN_DUMP")]
    base_lines = [
        obsidian_link("_master/_obsidian/bases/tasks-kanban-v1.base", "Tasks Kanban"),
        obsidian_link("_master/_obsidian/bases/content-kanban.base", "Content Kanban"),
    ]
    action_lines = [*base_lines, *schedule_lines]
    return f"""---
type: dashboard
generated: true
generated_at: {generated_at}
managed_by: "{MARKER}"
---
#### Action

{markdown_list(action_lines)}

#### Context

Standing
{markdown_list(standing_lines)}
Periodic
{markdown_list(periodic_lines)}
Inbox
{markdown_list(inbox_lines)}

#### Context Folder Notes

{markdown_list(context_note_lines)}

{chr(10).join(context_lines).rstrip() if context_lines else "- None"}
"""


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def cleanup_legacy_agent_context_markdown(root: Path) -> None:
    path = root / LEGACY_AGENT_CONTEXT_MARKDOWN_PATH
    if not path.exists():
        return
    current_path = root / AGENT_CONTEXT_MARKDOWN_PATH
    try:
        if current_path.exists() and path.samefile(current_path):
            return
    except OSError:
        pass
    props = simple_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    if props.get("type") == "agent-context" and props.get("generated") is True:
        path.unlink()
        print(f"deleted {path}")


def load_existing_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate agent context for the vault.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--configured-context-folders", dest="configured_entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--configured-sub-vaults", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--configured-entities", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--sub-vaults", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--entities", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--keep-agent-periodic-history", action="store_true", help="Keep stale generated agent periodic rollups.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    configured = configured_context_folders(root, parse_entities(args.configured_entities), DEFAULT_ENTITIES)
    explicit = parse_entities(args.entities)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    periodic_generator = importlib.import_module("periodic")
    content_schedule_generator = importlib.import_module("content")
    today = dt.date.fromisoformat(args.date)
    selected_entities = resolve_entities(root, configured, explicit, args.all)
    content_entities = content_enabled_entities(root, configured)
    selected_content_entities = [entity for entity in selected_entities if entity in content_entities]
    generated = dt.datetime.now().isoformat(timespec="seconds")
    content_schedules = content_schedule_generator.generate_content_schedules(
        root,
        selected_content_entities,
        today,
        generated_at=generated,
    )
    selected_entities, periods = periodic_generator.generate_periodic_notes(
        root,
        configured,
        explicit,
        args.all,
        today,
        generated_at=generated,
        keep_agent_periodic_history=args.keep_agent_periodic_history,
    )
    statuses = entity_statuses(root, configured)
    context_types = entity_context_types(root, configured)
    default_capture_entity = default_capture_context_folder(root, configured, selected_entities)
    tasks = collect_tasks(root, selected_entities, today)
    state_path = root / "_master/system/context/context.json"

    system_packets = write_realized_system_notes(root, generated)
    state = {
        "generated": generated,
        "managed_by": MARKER,
        "active_periods": periods,
        "default_capture_context_folder": default_capture_entity,
        "context_folders": configured,
        "context_folder_statuses": statuses,
        "context_folder_types": context_types,
        "selected_context_folders": selected_entities,
        "content_enabled_context_folders": content_entities,
        "content_schedules": content_schedules,
        "operating_system_notes": SYSTEM_NOTES,
        "agent_system_notes": system_packets,
        "entity_declarations": {
            entity: f"{entity}/DECLARATION.md" for entity in selected_entities
        },
        "context_folder_notes": {
            entity: f"{entity}/{entity}.md" for entity in selected_entities
        },
        "agent_periodic_notes": {
            period: path for period, path in agent_periodic_paths(periods).items()
        },
        "content_views": {
            "content_calendar": "_master/_obsidian/bases/content-calendar.base",
            "content_kanban": "_master/_obsidian/bases/content-kanban.base",
            "entity_views": {
                entity: {
                    "content_base": f"{entity}/_obsidian/bases/content-dashboard.base",
                    "queue": f"{entity}/_obsidian/bases/content-queue.base",
                    "calendar": f"{entity}/_obsidian/bases/content-calendar.base",
                    "kanban": f"{entity}/_obsidian/bases/content-kanban.base",
                }
                for entity in content_entities
            },
        },
        "tasks": tasks,
    }
    cleanup_legacy_agent_context_markdown(root)
    write_if_changed(
        root / AGENT_CONTEXT_MARKDOWN_PATH,
        context_markdown(
            configured,
            selected_entities,
            statuses,
            context_types,
            periods,
                tasks,
                content_entities,
                default_capture_entity,
                content_schedules,
                state["generated"],
                system_packets,
        ),
    )
    write_if_changed(state_path, json.dumps(state, indent=2) + "\n")
    write_if_changed(
        root / DASHBOARD_PATH,
        dashboard_markdown(
            selected_entities,
            periods,
            content_schedules,
            state["generated"],
        ),
    )


if __name__ == "__main__":
    main()
