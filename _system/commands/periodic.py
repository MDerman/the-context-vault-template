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
THEMATIC_BREAK_LINES = {"---", "***"}


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


def is_daily_carry_section(heading: str, body_lines: list[str]) -> bool:
    if "tasks i want to get done today" in heading.casefold():
        return True
    for line in body_lines:
        if line.strip():
            return checklist_item(line) is not None
    return False


def filter_carried_daily_lines(lines: list[str]) -> list[str]:
    carried: list[str] = []
    for line in lines:
        item = checklist_item(line)
        if not item:
            carried.append(line)
            continue
        mark, body = item
        if mark == " " and body:
            carried.append(line)
    return carried


def carried_daily_sections(text: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    carried: dict[str, list[str]] = {}
    for index, line in enumerate(lines):
        heading = secondary_heading(line)
        if not heading:
            continue
        end = section_end(lines, index + 1, 2)
        body_lines = lines[index + 1 : end]
        if not is_daily_carry_section(heading, body_lines):
            continue
        body = filter_carried_daily_lines(body_lines)
        if any(line.strip() for line in body):
            carried[heading] = body
    return carried


def find_secondary_section(lines: list[str], heading: str) -> tuple[int, int, int] | None:
    for index, line in enumerate(lines):
        if secondary_heading(line) == heading:
            return index, index + 1, section_end(lines, index + 1, 2)
    return None


def carried_line_key(line: str) -> tuple[str, str] | None:
    if not line.strip():
        return None
    if line.strip() in THEMATIC_BREAK_LINES:
        return "thematic-break", ""
    item = checklist_item(line)
    if item and item[1]:
        return "checklist", item[1]
    return "text", line.strip()


def content_insert_index(lines: list[str], start: int, end: int) -> int:
    cursor = end
    while cursor > start and not lines[cursor - 1].strip():
        cursor -= 1
    while cursor > start and lines[cursor - 1].strip() in THEMATIC_BREAK_LINES:
        cursor -= 1
        while cursor > start and not lines[cursor - 1].strip():
            cursor -= 1
    return cursor


def missing_carried_lines(target_lines: list[str], source_lines: list[str]) -> list[str]:
    existing = {key for line in target_lines if (key := carried_line_key(line)) is not None}
    pending: list[str] = []
    for line in source_lines:
        key = carried_line_key(line)
        if key is None:
            if pending and pending[-1].strip():
                pending.append(line)
            continue
        if key in existing:
            continue
        pending.append(line)
        existing.add(key)
    while pending and not pending[-1].strip():
        pending.pop()
    return pending


def nested_heading_indexes(lines: list[str]) -> list[int]:
    return [index for index, line in enumerate(lines) if (heading_level(line) or 0) > 2]


def merge_carried_section_body(target: list[str], source: list[str]) -> list[str]:
    merged = list(target)
    source_headings = nested_heading_indexes(source)
    source_root_end = source_headings[0] if source_headings else len(source)
    target_headings = nested_heading_indexes(merged)
    target_root_end = target_headings[0] if target_headings else len(merged)
    pending = missing_carried_lines(merged[:target_root_end], source[:source_root_end])
    if pending:
        insert_at = content_insert_index(merged, 0, target_root_end)
        merged[insert_at:insert_at] = pending

    for position, source_heading_index in enumerate(source_headings):
        source_end = source_headings[position + 1] if position + 1 < len(source_headings) else len(source)
        source_heading_line = source[source_heading_index]
        source_body = source[source_heading_index + 1 : source_end]
        matching_heading = next(
            (
                index
                for index in nested_heading_indexes(merged)
                if merged[index].strip() == source_heading_line.strip()
            ),
            None,
        )
        if matching_heading is None:
            section_keys = {key for line in merged if (key := carried_line_key(line)) is not None}
            new_body = [
                line
                for line in source_body
                if line.strip() not in THEMATIC_BREAK_LINES or ("thematic-break", "") not in section_keys
            ]
            while new_body and not new_body[-1].strip():
                new_body.pop()
            insert_at = content_insert_index(merged, 0, len(merged))
            block = [source_heading_line, *new_body]
            if insert_at > 0 and merged[insert_at - 1].strip() and block[0].strip():
                block.insert(0, "")
            merged[insert_at:insert_at] = block
            continue

        following = [index for index in nested_heading_indexes(merged) if index > matching_heading]
        target_end = following[0] if following else len(merged)
        pending = missing_carried_lines(merged[matching_heading + 1 : target_end], source_body)
        if pending:
            insert_at = content_insert_index(merged, matching_heading + 1, target_end)
            merged[insert_at:insert_at] = pending
    return merged


def append_carried_daily_sections(text: str, carried: dict[str, list[str]]) -> str:
    if not carried:
        return text
    lines = text.splitlines()
    changed = False

    for heading, source_body in carried.items():
        section = find_secondary_section(lines, heading)
        if not section:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"## {heading}")
            lines.extend(source_body)
            changed = True
            continue

        _, start, end = section
        merged_body = merge_carried_section_body(lines[start:end], source_body)
        if merged_body != lines[start:end]:
            lines[start:end] = merged_body
            changed = True

    if not changed:
        return text
    return "\n".join(lines) + "\n"


def latest_daily_note_before(daily_dir: Path, day: dt.date) -> Path | None:
    candidates: list[tuple[dt.date, Path]] = []
    for candidate in daily_dir.glob("*.md"):
        try:
            candidate_day = dt.date.fromisoformat(candidate.stem)
        except ValueError:
            continue
        if candidate_day < day:
            candidates.append((candidate_day, candidate))
    return max(candidates, default=(None, None), key=lambda item: item[0])[1]


def carry_forward_daily_sections(root: Path, entities: list[str], day: dt.date) -> None:
    current_id = day.isoformat()
    for entity in entities:
        daily_dir = root / entity / "_obsidian/periodic/daily"
        previous_path = latest_daily_note_before(daily_dir, day)
        current_path = daily_dir / f"{current_id}.md"
        if previous_path is None or not current_path.exists():
            continue
        carried = carried_daily_sections(previous_path.read_text(encoding="utf-8"))
        if not carried:
            continue
        current = current_path.read_text(encoding="utf-8")
        updated = append_carried_daily_sections(current, carried)
        if updated != current:
            current_path.write_text(updated, encoding="utf-8")
            print(f"carried daily section content into {current_path}")


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
    if fmt == "YYYY":
        return dt.date(int(value), 1, 1)
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
    if period == "daily" and path.exists():
        return
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
            carry_forward_daily_sections(root, entities, day)
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
