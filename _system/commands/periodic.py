#!/usr/bin/env python3
"""Generate source periodic notes and vault Sync Embed rollups."""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import re
import sys
from pathlib import Path

from script_utils import configured_context_folders, context_folder_note_path, resolve_vault_root
from vault_layout import MANAGED_BOOTSTRAP, MANAGED_PERIODIC, VAULT_PERIODIC_DIR

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from content import current_schedule_sync_embed


DEFAULT_ENTITIES = [
    "personal",
    "personal-brand",
    "business",
]

MANAGED_ENTITY_MARKERS = (MANAGED_PERIODIC, MANAGED_BOOTSTRAP)
CURRENT_CONTENT_SCHEDULE_PLACEHOLDER = "{{current_content_schedule_sync_embed}}"
TEMPLATER_DATE_NOW_RE = re.compile(r"<%\s*tp\.date\.now\((.*?)\)\s*%>")
TEMPLATER_CURSOR_RE = re.compile(r"<%\s*tp\.file\.cursor\(\)\s*%>")
SECONDARY_HEADING_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+")
CHECKLIST_RE = re.compile(r"^\s*-\s+\[(?P<mark>[ xX])\]\s*(?P<body>.*)$")


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "monthly": f"{day.year}-{day.month:02d}",
        "quarterly": f"{day.year}-Q{quarter}",
        "yearly": f"{day.year}",
    }


def yaml_list(items: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in items)


def personal_first_entities(entities: list[str]) -> list[str]:
    return sorted(entities, key=lambda entity: 0 if entity == "personal" else 1)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith("  "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def heading_level(line: str) -> int | None:
    match = HEADING_RE.match(line)
    return len(match.group(1)) if match else None


def secondary_heading(line: str) -> str | None:
    match = SECONDARY_HEADING_RE.match(line)
    return match.group(1).strip() if match else None


def checklist_item(line: str) -> tuple[str, str] | None:
    match = CHECKLIST_RE.match(line)
    if not match:
        return None
    return match.group("mark"), match.group("body").strip()


def section_end(lines: list[str], start_index: int, max_level: int) -> int:
    for index in range(start_index, len(lines)):
        level = heading_level(lines[index])
        if level is not None and level <= max_level:
            return index
    return len(lines)


def carried_daily_checklists(text: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    carried: dict[str, list[str]] = {}
    for index, line in enumerate(lines):
        heading = secondary_heading(line)
        if not heading:
            continue
        end = section_end(lines, index + 1, 2)
        cursor = index + 1
        while cursor < end and not lines[cursor].strip():
            cursor += 1
        if cursor >= end or not checklist_item(lines[cursor]):
            continue
        items: list[str] = []
        seen: set[str] = set()
        while cursor < end:
            if not lines[cursor].strip():
                cursor += 1
                continue
            item = checklist_item(lines[cursor])
            if not item:
                break
            mark, body = item
            if mark == " " and body and body not in seen:
                items.append(body)
                seen.add(body)
            cursor += 1
        if items:
            carried.setdefault(heading, []).extend(items)
    return carried


def find_secondary_section(lines: list[str], heading: str) -> tuple[int, int, int] | None:
    for index, line in enumerate(lines):
        if secondary_heading(line) == heading:
            return index, index + 1, section_end(lines, index + 1, 2)
    return None


def target_checklist_bodies(lines: list[str], start: int, end: int) -> set[str]:
    bodies: set[str] = set()
    for line in lines[start:end]:
        item = checklist_item(line)
        if item and item[1]:
            bodies.add(item[1])
    return bodies


def remove_blank_checklist_items(lines: list[str], start: int, end: int) -> list[str]:
    section = [line for line in lines[start:end] if not (checklist_item(line) and not checklist_item(line)[1])]
    return [*lines[:start], *section, *lines[end:]]


def checklist_insert_index(lines: list[str], start: int, end: int) -> int:
    cursor = start
    while cursor < end and not lines[cursor].strip():
        cursor += 1
    if cursor >= end:
        return end
    if not checklist_item(lines[cursor]):
        return cursor
    while cursor < end and checklist_item(lines[cursor]):
        cursor += 1
    return cursor


def append_carried_daily_checklists(text: str, carried: dict[str, list[str]]) -> str:
    if not carried:
        return text
    lines = text.splitlines()
    changed = False

    for heading, source_items in carried.items():
        section = find_secondary_section(lines, heading)
        existing: set[str] = set()
        if section:
            _, start, end = section
            existing = target_checklist_bodies(lines, start, end)
        pending: list[str] = []
        seen = set(existing)
        for body in source_items:
            if body and body not in seen:
                pending.append(body)
                seen.add(body)
        if not pending:
            continue

        if not section:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"## {heading}")
            lines.extend(f"- [ ] {body}" for body in pending)
            changed = True
            continue

        _, start, end = section
        lines = remove_blank_checklist_items(lines, start, end)
        _, start, end = find_secondary_section(lines, heading) or (0, len(lines), len(lines))
        insert_at = checklist_insert_index(lines, start, end)
        lines[insert_at:insert_at] = [f"- [ ] {body}" for body in pending]
        changed = True

    if not changed:
        return text
    return "\n".join(lines) + "\n"


def carry_forward_daily_checklists(root: Path, entities: list[str], day: dt.date) -> None:
    previous_id = (day - dt.timedelta(days=1)).isoformat()
    current_id = day.isoformat()
    for entity in entities:
        daily_dir = root / entity / "_obsidian/periodic/daily"
        previous_path = daily_dir / f"{previous_id}.md"
        current_path = daily_dir / f"{current_id}.md"
        if not previous_path.exists() or not current_path.exists():
            continue
        carried = carried_daily_checklists(previous_path.read_text(encoding="utf-8"))
        if not carried:
            continue
        current = current_path.read_text(encoding="utf-8")
        updated = append_carried_daily_checklists(current, carried)
        if updated != current:
            current_path.write_text(updated, encoding="utf-8")
            print(f"carried daily checklist items into {current_path}")


def split_templater_args(value: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and quote:
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            current.append(char)
            quote = char
            continue
        if char == ",":
            args.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current or value.endswith(","):
        args.append("".join(current).strip())
    return args


def unquote_templater_arg(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def clamp_day(year: int, month: int, day: int) -> int:
    return min(day, calendar.monthrange(year, month)[1])


def add_months(day: dt.date, months: int) -> dt.date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return day.replace(year=year, month=month, day=clamp_day(year, month, day.day))


def add_years(day: dt.date, years: int) -> dt.date:
    year = day.year + years
    return day.replace(year=year, day=clamp_day(year, day.month, day.day))


def parse_offset(value: str | None) -> tuple[int, int, int]:
    if not value:
        return 0, 0, 0
    value = unquote_templater_arg(value).strip()
    if re.fullmatch(r"[+-]?\d+", value):
        return 0, 0, int(value)
    match = re.fullmatch(
        r"([+-])?P(?:(?P<years>[+-]?\d+)Y)?(?:(?P<months>[+-]?\d+)M)?(?:(?P<weeks>[+-]?\d+)W)?(?:(?P<days>[+-]?\d+)D)?",
        value,
    )
    if not match:
        raise ValueError(f"unsupported Templater date offset: {value}")
    sign = -1 if match.group(1) == "-" else 1
    years = int(match.group("years") or 0) * sign
    months = int(match.group("months") or 0) * sign
    days = (int(match.group("weeks") or 0) * 7 + int(match.group("days") or 0)) * sign
    return years, months, days


def parse_moment_date(value: str, fmt: str) -> dt.date:
    value = value.strip()
    if fmt == "YYYY-MM-DD":
        return dt.date.fromisoformat(value)
    if fmt == "GGGG-[W]WW":
        match = re.fullmatch(r"(\d{4})-W(\d{2})", value)
        if match:
            return dt.date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
    if fmt == "YYYY-MM":
        match = re.fullmatch(r"(\d{4})-(\d{2})", value)
        if match:
            return dt.date(int(match.group(1)), int(match.group(2)), 1)
    if fmt == "YYYY-[Q]Q":
        match = re.fullmatch(r"(\d{4})-Q([1-4])", value)
        if match:
            return dt.date(int(match.group(1)), (int(match.group(2)) - 1) * 3 + 1, 1)
    return dt.date.fromisoformat(value)


def format_moment_date(day: dt.date, fmt: str) -> str:
    output: list[str] = []
    i = 0
    while i < len(fmt):
        if fmt[i] == "[":
            end = fmt.find("]", i + 1)
            if end != -1:
                output.append(fmt[i + 1 : end])
                i = end + 1
                continue
        if fmt.startswith("YYYY", i):
            output.append(f"{day.year:04d}")
            i += 4
        elif fmt.startswith("GGGG", i):
            output.append(f"{day.isocalendar().year:04d}")
            i += 4
        elif fmt.startswith("WW", i):
            output.append(f"{day.isocalendar().week:02d}")
            i += 2
        elif fmt.startswith("MM", i):
            output.append(f"{day.month:02d}")
            i += 2
        elif fmt.startswith("DD", i):
            output.append(f"{day.day:02d}")
            i += 2
        elif fmt.startswith("Q", i):
            output.append(str(((day.month - 1) // 3) + 1))
            i += 1
        else:
            output.append(fmt[i])
            i += 1
    return "".join(output)


def render_templater_date_now(expression_args: str, period_id: str, day: dt.date) -> str:
    args = split_templater_args(expression_args)
    if not args:
        return ""
    output_format = unquote_templater_arg(args[0])
    offset_arg = args[1] if len(args) >= 2 else None
    if len(args) >= 3:
        reference = period_id if args[2].strip() == "tp.file.title" else unquote_templater_arg(args[2])
        reference_format = unquote_templater_arg(args[3]) if len(args) >= 4 else "YYYY-MM-DD"
        base_day = parse_moment_date(reference, reference_format)
    else:
        base_day = day
    years, months, days = parse_offset(offset_arg)
    rendered_day = add_years(base_day, years)
    rendered_day = add_months(rendered_day, months)
    rendered_day = rendered_day + dt.timedelta(days=days)
    return format_moment_date(rendered_day, output_format)


def is_generated_vault_periodic_note(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    props = parse_frontmatter(text)
    return props.get("type") == "vault-periodic" and props.get("generated", "").lower() == "true"


def vault_periodic_path(root: Path, period: str, period_id: str) -> Path:
    return root / VAULT_PERIODIC_DIR / period / f"{period_id}.md"


def entity_status(root: Path, entity: str) -> str:
    path = context_folder_note_path(root / entity)
    if not path.exists():
        return ""
    return parse_frontmatter(path.read_text(encoding="utf-8")).get("status", "").strip().lower()


def parse_entities(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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


def render_template(root: Path, template: str, entity: str, period_id: str, day: dt.date) -> str:
    rendered = template
    rendered = rendered.replace("<% tp.file.title %>", period_id)
    rendered = rendered.replace("<% tp.file.folder(true).split('/')[0] %>", entity)
    rendered = rendered.replace('<% tp.file.folder(true).split("/")[0] %>', entity)
    rendered = TEMPLATER_DATE_NOW_RE.sub(lambda match: render_templater_date_now(match.group(1), period_id, day), rendered)
    rendered = TEMPLATER_CURSOR_RE.sub("", rendered)
    rendered = rendered.replace(CURRENT_CONTENT_SCHEDULE_PLACEHOLDER, current_schedule_sync_embed(root, entity, day))
    return rendered


def entity_template_note(root: Path, entity: str, period: str, period_id: str, day: dt.date) -> str:
    template_path = root / entity / "_obsidian/templates" / "periodic" / f"{period}-template.md"
    if not template_path.exists():
        print(f"warning: missing template: {template_path}", file=sys.stderr)
        return ""
    return render_template(root, template_path.read_text(encoding="utf-8"), entity, period_id, day)


def ensure_entity_note(root: Path, entity: str, period: str, period_id: str, day: dt.date) -> None:
    path = root / entity / "_obsidian/periodic" / period / f"{period_id}.md"
    content = entity_template_note(root, entity, period, period_id, day)
    if content and not content.endswith("\n"):
        content += "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return
        if not any(marker in existing for marker in MANAGED_ENTITY_MARKERS):
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def vault_periodic_note(root: Path, entities: list[str], period: str, period_id: str, generated_at: str) -> str:
    entities = personal_first_entities(entities)
    sections = "\n\n".join(
        f"## {entity}\n\n```sync\n![[{entity}/_obsidian/periodic/{period}/{period_id}]]\n```"
        for entity in entities
    )
    return f"""---
type: vault-periodic
period: {period}
period_id: {period_id}
generated: true
source_context_folders:
{yaml_list(entities)}
generated_at: {generated_at}
managed_by: "{MANAGED_PERIODIC}"
---
# {period_id} vault {period}

{sections}
"""


def write_vault_periodic_note(root: Path, entities: list[str], period: str, period_id: str, generated_at: str) -> None:
    path = vault_periodic_path(root, period, period_id)
    content = vault_periodic_note(root, entities, period, period_id, generated_at)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if not is_generated_vault_periodic_note(path) and not any(marker in existing for marker in MANAGED_ENTITY_MARKERS):
            print(f"skip non-managed vault periodic note: {path}")
            return
        if existing == content:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def generate_periodic_notes(
    root: Path,
    configured: list[str],
    explicit: list[str],
    include_all: bool,
    day: dt.date,
    *,
    generated_at: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    entities = resolve_entities(root, configured, explicit, include_all)
    periods = active_periods(day)
    generated_at = generated_at or dt.datetime.now().isoformat(timespec="seconds")

    for period, period_id in periods.items():
        for entity in entities:
            ensure_entity_note(root, entity, period, period_id, day)
        if period == "daily":
            carry_forward_daily_checklists(root, entities, day)
        write_vault_periodic_note(root, entities, period, period_id, generated_at)
    return entities, periods

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate source periodic notes and vault Sync Embed rollups.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--configured-context-folders", dest="configured_entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--configured-sub-vaults", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--configured-entities", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders for this run.")
    parser.add_argument("--sub-vaults", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--entities", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true", help="Use all configured context folders.")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    configured = configured_context_folders(root, parse_entities(args.configured_entities), DEFAULT_ENTITIES)
    explicit = parse_entities(args.entities)
    generate_periodic_notes(
        root,
        configured,
        explicit,
        args.all,
        dt.date.fromisoformat(args.date),
        generated_at=dt.datetime.now().isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    main()
