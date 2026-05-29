#!/usr/bin/env python3
"""Generate agent-readable periodic notes for the current active context folder set."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from script_utils import configured_context_folders, resolve_vault_root

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from content import current_schedule_sync_embed


DEFAULT_ENTITIES = [
    "01-personal",
    "02-personal-brand",
    "03-business",
]

MARKER = "managed-by: master/system/scripts/periodic.py"
BOOTSTRAP_MARKER = "managed-by: master/system/bootstrap/bootstrap_vault.py"
OLD_MARKER_CURRENT_PATH = "managed-by: master/system/scripts/periodic.py"
OLD_MARKER_LONG_PATH = "managed-by: master/system/scripts/generate_master_periodic_notes_for_now.py"
OLD_MARKER = "managed-by: master/scripts/generate_master_periodic_notes_for_now.py"
OLD_BOOTSTRAP_MARKER = "managed-by: master/system/bootstrap/setup/bootstrap_vault.py"
OLD_BOOTSTRAP_MARKER_LONG_PATH = "managed-by: master/bootstrap/setup/bootstrap_vault.py"
MANAGED_ENTITY_MARKERS = (
    MARKER,
    BOOTSTRAP_MARKER,
    OLD_MARKER_CURRENT_PATH,
    OLD_MARKER_LONG_PATH,
    OLD_MARKER,
    OLD_BOOTSTRAP_MARKER,
    OLD_BOOTSTRAP_MARKER_LONG_PATH,
)
AGENT_DIR = Path("master/system/context")
LEGACY_AGENT_PERIODIC_DIR = Path("master/system/context/periodic")
CURRENT_CONTENT_SCHEDULE_PLACEHOLDER = "{{current_content_schedule_sync_embed}}"


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "quarterly": f"{day.year}-Q{quarter}",
        "yearly": f"{day.year}",
    }


def yaml_list(items: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in items)


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()


def indent_block(text: str) -> str:
    if not text.strip():
        return "_No content yet._"
    return text.strip()


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


def is_generated_agent_periodic_note(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    props = parse_frontmatter(text)
    return props.get("type") == "agent-periodic" and props.get("generated", "").lower() == "true"


def agent_periodic_path(root: Path, period_id: str) -> Path:
    return root / AGENT_DIR / f"{period_id}.md"


def entity_status(root: Path, entity: str) -> str:
    path = root / entity / "HOME.md"
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
        raise SystemExit("No context folders selected. Mark a context folder HOME.md as status: active, pass --context-folders, or use --all.")
    return selected


def render_template(root: Path, template: str, entity: str, period_id: str, day: dt.date) -> str:
    rendered = template
    rendered = rendered.replace("<% tp.file.title %>", period_id)
    rendered = rendered.replace("<% tp.file.folder(true).split('/')[0] %>", entity)
    rendered = rendered.replace('<% tp.file.folder(true).split("/")[0] %>', entity)
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


def entity_periodic_body(root: Path, entity: str, period: str, period_id: str) -> str:
    path = root / entity / "_obsidian/periodic" / period / f"{period_id}.md"
    if not path.exists():
        return f"_Missing source note: `{path.relative_to(root)}`._"
    text = strip_frontmatter(path.read_text(encoding="utf-8"))
    return indent_block(text)


def agent_periodic_note(root: Path, entities: list[str], period: str, period_id: str, generated_at: str) -> str:
    sections = "\n\n".join(
        f"## {entity}\n\n_Source: `{entity}/_obsidian/periodic/{period}/{period_id}.md`_\n\n"
        f"{entity_periodic_body(root, entity, period, period_id)}"
        for entity in entities
    )
    return f"""---
type: agent-periodic
period: {period}
period_id: {period_id}
generated: true
generated_at: {generated_at}
managed_by: "{MARKER}"
source_context_folders:
{yaml_list(entities)}
---
# {period_id} agent {period}

{sections}
"""


def write_agent_periodic_note(root: Path, entities: list[str], period: str, period_id: str, generated_at: str) -> None:
    path = agent_periodic_path(root, period_id)
    content = agent_periodic_note(root, entities, period, period_id, generated_at)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if not is_generated_agent_periodic_note(path) and not any(marker in existing for marker in MANAGED_ENTITY_MARKERS):
            print(f"skip non-managed agent periodic note: {path}")
            return
        if existing == content:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def cleanup_agent_periodic_history(root: Path, current_paths: set[Path]) -> None:
    agent_dir = root / AGENT_DIR
    if agent_dir.exists():
        for path in sorted(agent_dir.glob("*.md")):
            if path in current_paths:
                continue
            if is_generated_agent_periodic_note(path):
                path.unlink()
                print(f"deleted {path}")

    legacy_dir = root / LEGACY_AGENT_PERIODIC_DIR
    if legacy_dir.exists():
        for path in sorted(legacy_dir.glob("*/*.md")):
            if is_generated_agent_periodic_note(path):
                path.unlink()
                print(f"deleted {path}")


def generate_periodic_notes(
    root: Path,
    configured: list[str],
    explicit: list[str],
    include_all: bool,
    day: dt.date,
    *,
    generated_at: str | None = None,
    keep_agent_periodic_history: bool = False,
) -> tuple[list[str], dict[str, str]]:
    entities = resolve_entities(root, configured, explicit, include_all)
    periods = active_periods(day)
    current_paths: set[Path] = set()
    generated_at = generated_at or dt.datetime.now().isoformat(timespec="seconds")

    for period, period_id in periods.items():
        for entity in entities:
            ensure_entity_note(root, entity, period, period_id, day)
        write_agent_periodic_note(root, entities, period, period_id, generated_at)
        current_paths.add(agent_periodic_path(root, period_id))
    if not keep_agent_periodic_history:
        cleanup_agent_periodic_history(root, current_paths)
    return entities, periods

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate agent periodic notes for now.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--configured-context-folders", dest="configured_entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--configured-sub-vaults", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--configured-entities", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders for this run.")
    parser.add_argument("--sub-vaults", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--entities", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true", help="Use all configured context folders.")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--keep-agent-periodic-history", action="store_true", help="Keep stale generated agent periodic rollups.")
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
        keep_agent_periodic_history=args.keep_agent_periodic_history,
    )


if __name__ == "__main__":
    main()
