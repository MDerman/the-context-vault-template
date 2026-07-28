#!/usr/bin/env python3
"""Generate fixed-window content schedule notes from entity cadence JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from script_utils import configured_context_folders, context_folder_note_path, resolve_vault_root
from vault_layout import MANAGED_CONTENT


DEFAULT_ENTITIES = [
    "personal",
    "personal-brand",
    "business",
]

MARKER = MANAGED_CONTENT
MANAGED_MARKERS = (MARKER,)
CONFIG_RELATIVE_PATH = Path("_obsidian/content/content-cadence.json")
SCHEDULE_DIR = Path("_obsidian/content-schedules")
DEFAULT_SCHEDULE_FORMAT = "publicationThenByWeek"
VALID_SCHEDULE_FORMATS = {"weekly", "weeklyThenByPublication", "publicationThenByWeek"}
ENTITY_NOTE_CURRENT_SCHEDULE_PREFIX = "Current content schedule:"


@dataclass(frozen=True)
class ContentScheduleWindow:
    start: dt.date
    end: dt.date


@dataclass(frozen=True)
class ContentScheduleSlot:
    when: dt.datetime
    publication_id: str
    publication_name: str
    heading: str


def parse_entities(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def simple_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    data: dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.startswith("  ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.lower() == "true":
            data[key.strip()] = True
        elif value.lower() == "false":
            data[key.strip()] = False
        else:
            data[key.strip()] = value.strip('"').strip("'")
    return data


def replace_frontmatter(text: str, updates: dict[str, str]) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        lines = ["---", *[f"{key}: {value}" for key, value in updates.items()], "---"]
        return "\n".join(lines) + "\n" + text.lstrip()
    frontmatter = match.group(1).splitlines()
    seen: set[str] = set()
    updated_lines: list[str] = []
    for line in frontmatter:
        if ":" in line and not line.startswith("  "):
            key = line.split(":", 1)[0].strip()
            if key in updates:
                updated_lines.append(f"{key}: {updates[key]}")
                seen.add(key)
                continue
        updated_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            updated_lines.append(f"{key}: {value}")
    return "---\n" + "\n".join(updated_lines).rstrip() + "\n---\n" + text[match.end():]


def strip_generated_marker_comment(text: str) -> str:
    for marker in MANAGED_MARKERS:
        text = re.sub(rf"\n?<!-- {re.escape(marker)} -->\n?", "\n", text, count=1)
    return text.lstrip("\n")


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
    if not selected:
        raise SystemExit("No context folders selected. Mark a context folder note as status: active, pass --context-folders, or use --all.")
    return selected


def load_cadence_config(root: Path, entity: str) -> dict[str, Any] | None:
    path = root / entity / CONFIG_RELATIVE_PATH
    if not path.exists():
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"warning: could not parse {path}: {exc}", file=sys.stderr)
        return None
    if not config.get("enabled", False):
        return None
    return config


def content_schedule_window(config: dict[str, Any], day: dt.date) -> ContentScheduleWindow:
    anchor = dt.date.fromisoformat(str(config["anchor_date"]))
    window_weeks = int(config.get("window_weeks", 4))
    window_days = window_weeks * 7
    if window_days <= 0:
        raise ValueError("window_weeks must be greater than 0")
    offset = (day - anchor).days // window_days
    start = anchor + dt.timedelta(days=offset * window_days)
    return ContentScheduleWindow(start=start, end=start + dt.timedelta(days=window_days - 1))


def content_schedule_filename(window: ContentScheduleWindow) -> str:
    return f"Content Calendar for {window.start.isoformat()} to {window.end.isoformat()}.md"


def content_schedule_path(root: Path, entity: str, day: dt.date) -> Path | None:
    config = load_cadence_config(root, entity)
    if not config:
        return None
    window = content_schedule_window(config, day)
    return root / entity / SCHEDULE_DIR / content_schedule_filename(window)


def current_schedule_sync_embed(root: Path, entity: str, day: dt.date) -> str:
    path = content_schedule_path(root, entity, day)
    if not path:
        return "_No active content schedule configured for this context folder._"
    link = str(path.relative_to(root).with_suffix(""))
    return f"```sync\n![[{link}]]\n```"


def current_schedule_obsidian_link(root: Path, path: Path) -> str:
    link = str(path.relative_to(root).with_suffix(""))
    return f"[[{link}|{path.stem}]]"


def entity_note_current_schedule_line(root: Path, path: Path) -> str:
    return f"{ENTITY_NOTE_CURRENT_SCHEDULE_PREFIX} {current_schedule_obsidian_link(root, path)}."


def ensure_entity_note_current_schedule_link(root: Path, entity: str, path: Path) -> None:
    entity_note_path = context_folder_note_path(root / entity)
    if not entity_note_path.exists():
        return
    text = entity_note_path.read_text(encoding="utf-8")
    line = entity_note_current_schedule_line(root, path)
    marker_pattern = "|".join(re.escape(marker) for marker in MANAGED_MARKERS)
    old_block_start = rf"<!-- (?:{marker_pattern}):current-content-schedule:start -->"
    old_block_end = rf"<!-- (?:{marker_pattern}):current-content-schedule:end -->"
    old_managed_block_re = re.compile(
        old_block_start
        + r"\n"
        r"(?:Current (?:4-week )?content schedule: .*\n)"
        + old_block_end,
        re.M,
    )
    if old_managed_block_re.search(text):
        updated = old_managed_block_re.sub(line, text, count=1)
    else:
        current_line_re = re.compile(r"^Current (?:4-week )?content schedule: .*$", re.M)
        if current_line_re.search(text):
            updated = current_line_re.sub(line, text, count=1)
        else:
            updated = text.rstrip() + "\n\n" + line + "\n"
    if updated != text:
        entity_note_path.write_text(updated, encoding="utf-8")
        print(f"wrote {entity_note_path}")


def split_cron_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_cron(cron: str) -> tuple[str, str, str, str, str]:
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"expected 5 cron fields, got {len(parts)}")
    return tuple(parts)  # type: ignore[return-value]


def exact_or_star_matches(field: str, value: int, *, minimum: int, maximum: int) -> bool:
    if field == "*":
        return True
    try:
        parsed = int(field)
    except ValueError:
        raise ValueError(f"unsupported cron field {field!r}; use '*' or an exact integer")
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"cron field {field!r} is outside {minimum}-{maximum}")
    return parsed == value


def dow_matches(field: str, date: dt.date) -> bool:
    if field == "*":
        return True
    try:
        parsed = int(field)
    except ValueError:
        raise ValueError(f"unsupported day-of-week field {field!r}; use '*' or 0-7")
    if parsed < 0 or parsed > 7:
        raise ValueError(f"day-of-week field {field!r} is outside 0-7")
    cron_dow = (date.weekday() + 1) % 7
    if parsed == 7:
        parsed = 0
    return parsed == cron_dow


def cron_matches_date(cron: str, date: dt.date) -> tuple[int, int] | None:
    minute, hour, day_of_month, month, day_of_week = parse_cron(cron)
    if not exact_or_star_matches(day_of_month, date.day, minimum=1, maximum=31):
        return None
    if not exact_or_star_matches(month, date.month, minimum=1, maximum=12):
        return None
    if not dow_matches(day_of_week, date):
        return None
    if minute == "*" or hour == "*":
        raise ValueError("minute and hour must be exact integers for content schedule slots")
    parsed_minute = int(minute)
    parsed_hour = int(hour)
    if parsed_minute < 0 or parsed_minute > 59:
        raise ValueError(f"minute field {minute!r} is outside 0-59")
    if parsed_hour < 0 or parsed_hour > 23:
        raise ValueError(f"hour field {hour!r} is outside 0-23")
    return parsed_hour, parsed_minute


def schedule_slots(config: dict[str, Any], window: ContentScheduleWindow) -> list[ContentScheduleSlot]:
    slots: list[ContentScheduleSlot] = []
    publications = config.get("publications", {})
    if not isinstance(publications, dict):
        return slots

    for publication_id, publication_config in publications.items():
        if not isinstance(publication_config, dict):
            continue
        if publication_config.get("enabled", True) is False:
            continue
        publication_name = str(publication_config.get("name") or publication_id)
        slot_headings = publication_config.get("slot_headings", {})
        if not isinstance(slot_headings, dict):
            slot_headings = {}
        for cron in split_cron_list(publication_config.get("cadence")):
            for offset in range((window.end - window.start).days + 1):
                date = window.start + dt.timedelta(days=offset)
                try:
                    time_parts = cron_matches_date(cron, date)
                except ValueError as exc:
                    print(f"warning: skip invalid cron {cron!r} for {publication_id}: {exc}", file=sys.stderr)
                    break
                if not time_parts:
                    continue
                hour, minute = time_parts
                slots.append(
                    ContentScheduleSlot(
                        when=dt.datetime.combine(date, dt.time(hour=hour, minute=minute)),
                        publication_id=str(publication_id),
                        publication_name=publication_name,
                        heading=str(slot_headings.get(cron, "")).strip(),
                    )
                )
    return sorted(slots, key=lambda slot: (slot.when, slot.publication_name, slot.heading))


def schedule_format(config: dict[str, Any]) -> str:
    value = str(config.get("schedule_format") or DEFAULT_SCHEDULE_FORMAT)
    if value not in VALID_SCHEDULE_FORMATS:
        raise ValueError(f"unsupported schedule_format {value!r}; expected one of {sorted(VALID_SCHEDULE_FORMATS)}")
    return value


def enabled_publication_configs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    publications = config.get("publications", {})
    if not isinstance(publications, dict):
        return {}
    enabled: dict[str, dict[str, Any]] = {}
    for publication_id, publication_config in publications.items():
        if not isinstance(publication_config, dict):
            continue
        if publication_config.get("enabled", True) is False:
            continue
        if not split_cron_list(publication_config.get("cadence")):
            continue
        enabled[str(publication_id)] = publication_config
    return enabled


def publication_name(publication_id: str, config: dict[str, Any]) -> str:
    publication_config = enabled_publication_configs(config).get(publication_id, {})
    return str(publication_config.get("name") or publication_id)


def publication_order(config: dict[str, Any], slots: list[ContentScheduleSlot]) -> list[str]:
    enabled = enabled_publication_configs(config)
    configured_order = config.get("publication_order", [])
    ordered: list[str] = []
    if isinstance(configured_order, list):
        ordered.extend(str(publication_id) for publication_id in configured_order if str(publication_id) in enabled)
    for slot in slots:
        if slot.publication_id not in ordered:
            ordered.append(slot.publication_id)
    for publication_id in enabled:
        if publication_id not in ordered:
            ordered.append(publication_id)
    return ordered


def render_slot_heading(slot: ContentScheduleSlot) -> str:
    heading = f"{slot.when:%Y-%m-%d %H:%M} - {slot.publication_name}"
    if slot.heading:
        heading += f" - {slot.heading}"
    return heading


def render_slot_line(slot: ContentScheduleSlot, level: int) -> list[str]:
    return [f"{'#' * level} {render_slot_heading(slot)}", "", ""]


def week_bounds(window: ContentScheduleWindow, week_index: int) -> tuple[dt.date, dt.date]:
    week_start = window.start + dt.timedelta(days=week_index * 7)
    return week_start, week_start + dt.timedelta(days=6)


def render_weekly(config: dict[str, Any], window: ContentScheduleWindow, slots: list[ContentScheduleSlot]) -> list[str]:
    lines: list[str] = []
    for week_index in range(int(config.get("window_weeks", 4))):
        week_start, week_end = week_bounds(window, week_index)
        lines.extend([f"## Week {week_index + 1}: {week_start.isoformat()} to {week_end.isoformat()}", ""])
        week_slots = [slot for slot in slots if week_start <= slot.when.date() <= week_end]
        if not week_slots:
            lines.extend(["_No cadence slots configured._", ""])
            continue
        for slot in week_slots:
            lines.extend(render_slot_line(slot, 3))
    return lines


def render_weekly_then_by_publication(
    config: dict[str, Any],
    window: ContentScheduleWindow,
    slots: list[ContentScheduleSlot],
) -> list[str]:
    lines: list[str] = []
    ordered_publications = publication_order(config, slots)
    for week_index in range(int(config.get("window_weeks", 4))):
        week_start, week_end = week_bounds(window, week_index)
        lines.extend([f"## Week {week_index + 1}: {week_start.isoformat()} to {week_end.isoformat()}", ""])
        for publication_id in ordered_publications:
            publication_slots = [
                slot
                for slot in slots
                if slot.publication_id == publication_id and week_start <= slot.when.date() <= week_end
            ]
            if not publication_slots:
                continue
            lines.extend([f"### {publication_name(publication_id, config)}", ""])
            for slot in publication_slots:
                lines.extend(render_slot_line(slot, 4))
    return lines


def render_publication_then_by_week(
    config: dict[str, Any],
    window: ContentScheduleWindow,
    slots: list[ContentScheduleSlot],
) -> list[str]:
    lines: list[str] = []
    ordered_publications = publication_order(config, slots)
    for publication_id in ordered_publications:
        publication_slots = [slot for slot in slots if slot.publication_id == publication_id]
        if not publication_slots:
            continue
        lines.extend([f"## {publication_name(publication_id, config)}", ""])
        for week_index in range(int(config.get("window_weeks", 4))):
            week_start, week_end = week_bounds(window, week_index)
            week_slots = [slot for slot in publication_slots if week_start <= slot.when.date() <= week_end]
            if not week_slots:
                continue
            lines.extend([f"### Week {week_index + 1}: {week_start.isoformat()} to {week_end.isoformat()}", ""])
            for slot in week_slots:
                lines.extend(render_slot_line(slot, 4))
    return lines


def render_schedule_body(config: dict[str, Any], window: ContentScheduleWindow, slots: list[ContentScheduleSlot]) -> list[str]:
    selected_format = schedule_format(config)
    if selected_format == "weekly":
        return render_weekly(config, window, slots)
    if selected_format == "weeklyThenByPublication":
        return render_weekly_then_by_publication(config, window, slots)
    return render_publication_then_by_week(config, window, slots)


def render_schedule_note(entity: str, config: dict[str, Any], window: ContentScheduleWindow, generated_at: str) -> str:
    title = f"Content Calendar for {window.start.isoformat()} to {window.end.isoformat()}"
    slots = schedule_slots(config, window)
    selected_format = schedule_format(config)
    lines = [
        "---",
        "type: content-schedule",
        f"entity: {entity}",
        f"schedule_start: {window.start.isoformat()}",
        f"schedule_end: {window.end.isoformat()}",
        f"timezone: {config.get('timezone', 'UTC')}",
        f"schedule_format: {selected_format}",
        f"source: {entity}/_obsidian/content/content-cadence.json",
        "generated: true",
        f"generated_at: {generated_at}",
        f'managed_by: "{MARKER}"',
        "---",
        f"## {title}",
        "",
    ]
    lines.extend(render_schedule_body(config, window, slots))
    return "\n".join(lines).rstrip() + "\n"


def ensure_content_schedule(
    root: Path,
    entity: str,
    day: dt.date,
    *,
    force: bool = False,
    generated_at: str | None = None,
) -> dict[str, str] | None:
    config = load_cadence_config(root, entity)
    if not config:
        return None
    generated_at = generated_at or dt.datetime.now().isoformat(timespec="seconds")
    window = content_schedule_window(config, day)
    path = root / entity / SCHEDULE_DIR / content_schedule_filename(window)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        props = simple_frontmatter(existing)
        managed = props.get("managed_by") in MANAGED_MARKERS or any(marker in existing for marker in MANAGED_MARKERS)
        if force:
            if not managed:
                print(f"skip non-managed content schedule: {path}", file=sys.stderr)
            else:
                content = render_schedule_note(entity, config, window, generated_at)
                if existing != content:
                    path.write_text(content, encoding="utf-8")
                    print(f"wrote {path}")
        elif managed and (props.get("managed_by") != MARKER or any(marker in existing for marker in MANAGED_MARKERS)):
            updated = replace_frontmatter(
                strip_generated_marker_comment(existing),
                {
                    "generated": "true",
                    "generated_at": generated_at,
                    "managed_by": f'"{MARKER}"',
                },
            )
            if updated != existing:
                path.write_text(updated, encoding="utf-8")
                print(f"wrote {path}")
        ensure_entity_note_current_schedule_link(root, entity, path)
        return {
            "entity": entity,
            "path": str(path.relative_to(root)),
            "schedule_start": window.start.isoformat(),
            "schedule_end": window.end.isoformat(),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_schedule_note(entity, config, window, generated_at), encoding="utf-8")
    print(f"wrote {path}")
    ensure_entity_note_current_schedule_link(root, entity, path)
    return {
        "entity": entity,
        "path": str(path.relative_to(root)),
        "schedule_start": window.start.isoformat(),
        "schedule_end": window.end.isoformat(),
    }


def generate_content_schedules(
    root: Path,
    entities: list[str],
    day: dt.date,
    *,
    force: bool = False,
    generated_at: str | None = None,
) -> list[dict[str, str]]:
    schedules: list[dict[str, str]] = []
    for entity in entities:
        result = ensure_content_schedule(root, entity, day, force=force, generated_at=generated_at)
        if result:
            schedules.append(result)
    return schedules


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate current 4-week content schedule notes.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--configured-context-folders", dest="configured_entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="Regenerate existing managed content schedule notes.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    configured = configured_context_folders(root, parse_entities(args.configured_entities), DEFAULT_ENTITIES)
    explicit = parse_entities(args.entities)
    selected = resolve_entities(root, configured, explicit, args.all)
    content_entities = [entity for entity in selected if entity_content_enabled(root, entity)]
    generate_content_schedules(root, content_entities, dt.date.fromisoformat(args.date), force=args.force)


if __name__ == "__main__":
    main()
