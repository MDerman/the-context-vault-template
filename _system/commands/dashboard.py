"""Render the generated Obsidian dashboard for the refresh pipeline."""

from __future__ import annotations

import calendar
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from vault_layout import (
    DASHBOARD_ACTION_LINKS_PATH,
    DASHBOARD_PATH,
    MANAGED_DASHBOARD,
    VAULT_CONFIG_PATH,
    VAULT_PERIODIC_DIR,
)

DEFAULT_DASHBOARD_CHECKLIST_CONFIG = {
    "end_of_week_day": "sunday",
    "monthly_sops_reminder_day": "last_day",
}
WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


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


def load_vault_config(root: Path) -> dict[str, Any]:
    path = root / VAULT_CONFIG_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def dashboard_checklist_config(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("dashboard_checklist", {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        key: str(raw.get(key, default)).strip().lower()
        for key, default in DEFAULT_DASHBOARD_CHECKLIST_CONFIG.items()
    }


def ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def checklist_heading(day: dt.date) -> str:
    return f"Checklist for {day.strftime('%a')}, {ordinal(day.day)} {day.strftime('%B')}"


def end_of_month(day: dt.date) -> dt.date:
    return dt.date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def quarter_end(day: dt.date) -> dt.date:
    quarter = ((day.month - 1) // 3) + 1
    month = quarter * 3
    return dt.date(day.year, month, calendar.monthrange(day.year, month)[1])


def configured_weekday(settings: dict[str, str]) -> int:
    return WEEKDAY_INDEX.get(settings.get("end_of_week_day", "sunday"), WEEKDAY_INDEX["sunday"])


def is_end_of_week_day(day: dt.date, settings: dict[str, str]) -> bool:
    return day.weekday() == configured_weekday(settings)


def is_monthly_sops_day(day: dt.date, settings: dict[str, str]) -> bool:
    value = settings.get("monthly_sops_reminder_day", "last_day")
    if value == "first_day":
        return day.day == 1
    return day == end_of_month(day)


def is_quarter_planning_day(day: dt.date, settings: dict[str, str]) -> bool:
    target = quarter_end(day)
    if day == target - dt.timedelta(days=1):
        return True
    days_until = (target - day).days
    return is_end_of_week_day(day, settings) and 0 < days_until <= 7


def month_label(period_id: str) -> str:
    try:
        year, month = period_id.split("-", 1)
        return dt.date(int(year), int(month), 1).strftime("%B %Y")
    except ValueError:
        return period_id


def unchecked_checkbox_count(text: str) -> int:
    return len(re.findall(r"^\s*[-*]\s+\[\s\]", text, flags=re.M))


def stale_monthly_sops(root: Path, current_month: str, fallback_entities: list[str]) -> list[tuple[str, int]]:
    """Count open SOPs in source notes indexed by historic vault monthly rollups."""
    items: list[tuple[str, int]] = []
    monthly_dir = root / VAULT_PERIODIC_DIR / "monthly"
    if not monthly_dir.exists():
        return items
    for path in sorted(monthly_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        props = simple_frontmatter(text)
        if props.get("type") != "vault-periodic" or props.get("period") != "monthly":
            continue
        if props.get("generated") is not True:
            continue
        period_id = str(props.get("period_id") or path.stem)
        if period_id >= current_month:
            continue
        entities = props.get("source_context_folders")
        if not isinstance(entities, list) or not entities:
            entities = fallback_entities
        count = 0
        for entity in entities:
            source = root / str(entity) / "_obsidian/periodic/monthly" / f"{period_id}.md"
            if source.exists():
                count += unchecked_checkbox_count(source.read_text(encoding="utf-8", errors="replace"))
        if count:
            items.append((period_id, count))
    return items


def obsidian_link(path: str, label: str) -> str:
    target = path[:-3] if path.endswith(".md") else path
    return f"[[{target}|{label}]]"


def dashboard_checklist_lines(
    root: Path,
    day: dt.date,
    periods: dict[str, str],
    config: dict[str, Any],
    selected_entities: list[str] | None = None,
) -> list[str]:
    settings = dashboard_checklist_config(config)
    lines = [
        "[ ] "
        + obsidian_link(
            f"_system/_obsidian/periodic/daily/{periods['daily']}.md",
            "Plan and review day",
        )
    ]
    if is_end_of_week_day(day, settings):
        iso = day.isocalendar()
        lines.append(
            "[ ] "
            + obsidian_link(
                f"_system/_obsidian/periodic/weekly/{periods['weekly']}.md",
                f"Plan next week and review the {ordinal(iso.week)} week of {iso.year}",
            )
        )
    if is_monthly_sops_day(day, settings):
        lines.append(
            "[ ] "
            + obsidian_link(
                f"_system/_obsidian/periodic/monthly/{periods['monthly']}.md",
                "Monthly SOPs",
            )
        )
    for period_id, count in stale_monthly_sops(root, periods["monthly"], selected_entities or []):
        lines.append(
            "[ ] "
            + obsidian_link(
                f"_system/_obsidian/periodic/monthly/{period_id}.md",
                f"Finish Monthly SOPs for {month_label(period_id)}",
            )
            + f" ({count} open)"
        )
    if is_quarter_planning_day(day, settings):
        lines.append(
            "[ ] "
            + obsidian_link(
                f"_system/_obsidian/periodic/quarterly/{periods['quarterly']}.md",
                "Plan next quarter and review past quarter",
            )
        )
    return lines


def markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def private_dashboard_action_lines(root: Path) -> list[str]:
    path = root / DASHBOARD_ACTION_LINKS_PATH
    if not path.exists():
        return []
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        lines.append(stripped)
    return lines


def dashboard_markdown(
    root: Path,
    selected_entities: list[str],
    periods: dict[str, str],
    content_schedules: list[dict[str, str]],
    generated_at: str,
    today: dt.date,
    config: dict[str, Any],
) -> str:
    context_lines: list[str] = []
    for entity in selected_entities:
        context_lines.append(f"#### {entity}")
        for period, period_id in periods.items():
            if period == "monthly":
                continue
            path = f"{entity}/_obsidian/periodic/{period}/{period_id}.md"
            context_lines.append(f"- {period.title()}: {obsidian_link(path, period_id)}")
        context_lines.append("")
    schedule_lines = [
        obsidian_link(schedule["path"], schedule["path"].rsplit("/", 1)[-1].removesuffix(".md"))
        for schedule in content_schedules
    ]
    context_note_lines = [obsidian_link(f"{entity}/{entity}.md", entity) for entity in selected_entities]
    inbox_lines = [obsidian_link("_system/inbox/BRAIN_DUMP.md", "BRAIN_DUMP")]
    base_lines = [
        obsidian_link("_system/_obsidian/bases/tasks-kanban-v1.base", "Tasks Kanban"),
        obsidian_link("_system/_obsidian/bases/content-kanban.base", "Content Kanban"),
    ]
    action_lines = [*base_lines, *schedule_lines, *inbox_lines, *private_dashboard_action_lines(root)]
    return f"""---
type: dashboard
generated: true
generated_at: {generated_at}
managed_by: "{MANAGED_DASHBOARD}"
---
#### Action

{markdown_list(action_lines)}

##### {checklist_heading(today)}

{markdown_list(dashboard_checklist_lines(root, today, periods, config, selected_entities))}

#### Home Pages

{markdown_list(context_note_lines)}

{chr(10).join(context_lines).rstrip() if context_lines else "- None"}
"""


def write_dashboard(
    root: Path,
    selected_entities: list[str],
    periods: dict[str, str],
    content_schedules: list[dict[str, str]],
    generated_at: str,
    today: dt.date,
) -> Path:
    path = root / DASHBOARD_PATH
    content = dashboard_markdown(
        root,
        selected_entities,
        periods,
        content_schedules,
        generated_at,
        today,
        load_vault_config(root),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}")
    return path
