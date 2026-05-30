#!/usr/bin/env python3
"""Delete current generated agent periodic notes and optional context sources."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from script_utils import configured_context_folders, context_folder_note_path, resolve_vault_root


DEFAULT_ENTITIES = [
    "personal",
    "personal-brand",
    "business",
]

PERIODS = ["daily", "weekly", "quarterly", "yearly"]
AGENT_DIR = Path("_master/system/context")
LEGACY_AGENT_PERIODIC_DIR = Path("_master/system/context/periodic")
SAFE_MARKERS = [
    "managed-by: _master/system/bootstrap/bootstrap_vault.py",
    "managed-by: _master/system/bootstrap/setup/bootstrap_vault.py",
    "managed-by: _master/system/scripts/periodic.py",
    "managed-by: _master/system/scripts/generate_master_periodic_notes_for_now.py",
    "managed-by: _master/bootstrap/setup/bootstrap_vault.py",
    "managed-by: _master/scripts/generate_master_periodic_notes_for_now.py",
    "generated: true",
]


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "quarterly": f"{day.year}-Q{quarter}",
        "yearly": f"{day.year}",
    }


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


def entity_status(root: Path, entity: str) -> str:
    path = context_folder_note_path(root / entity)
    if not path.exists():
        return ""
    return parse_frontmatter(path.read_text(encoding="utf-8")).get("status", "").strip().lower()


def parse_csv(value: str | None) -> list[str]:
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
        if include_all or entity_status(root, entity) != "active":
            selected.append(entity)
    return selected


def is_safe_to_delete(path: Path, force: bool) -> bool:
    if force:
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(marker in text for marker in SAFE_MARKERS)


def delete_periodic_notes(root: Path, entities: list[str], periods: dict[str, str], dry_run: bool, force: bool) -> tuple[int, int]:
    deleted = 0
    skipped = 0
    for entity in entities:
        for period, period_id in periods.items():
            path = root / entity / "_obsidian/periodic" / period / f"{period_id}.md"
            if not path.exists():
                continue
            if not is_safe_to_delete(path, force):
                print(f"skip non-managed periodic note: {path}")
                skipped += 1
                continue
            if dry_run:
                print(f"[dry-run] delete {path}")
            else:
                path.unlink()
                print(f"deleted {path}")
            deleted += 1
    return deleted, skipped


def delete_agent_periodic_notes(root: Path, periods: dict[str, str], dry_run: bool, force: bool) -> tuple[int, int]:
    deleted = 0
    skipped = 0
    for period, period_id in periods.items():
        candidates = [
            root / AGENT_DIR / f"{period_id}.md",
            root / LEGACY_AGENT_PERIODIC_DIR / period / f"{period_id}.md",
        ]
        for path in candidates:
            if not path.exists():
                continue
            if not is_safe_to_delete(path, force):
                print(f"skip non-managed agent periodic note: {path}")
                skipped += 1
                continue
            if dry_run:
                print(f"[dry-run] delete {path}")
            else:
                path.unlink()
                print(f"deleted {path}")
            deleted += 1
    return deleted, skipped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Delete current generated agent periodic notes and optional context folder source notes."
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--configured-context-folders", dest="configured_entities", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--configured-sub-vaults", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--configured-entities", dest="configured_entities", help=argparse.SUPPRESS)
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders to clean.")
    parser.add_argument("--sub-vaults", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--entities", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true", help="Clean every configured context folder.")
    parser.add_argument("--skip-agent", action="store_true", help="Do not delete generated master agent periodic notes.")
    parser.add_argument("--agent-only", action="store_true", help="Delete only generated master agent periodic notes.")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument(
        "--periods",
        default=",".join(PERIODS),
        help="Comma-separated period types to delete. Defaults to daily,weekly,quarterly,yearly.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Delete even when a note is not marked generated/managed.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    configured = configured_context_folders(root, parse_csv(args.configured_entities), DEFAULT_ENTITIES)
    explicit = parse_csv(args.entities)
    requested_periods = parse_csv(args.periods)
    unknown_periods = [period for period in requested_periods if period not in PERIODS]
    if unknown_periods:
        raise SystemExit(f"Unknown period type(s): {', '.join(unknown_periods)}")

    if args.agent_only and (explicit or args.all):
        raise SystemExit("Use --agent-only without --context-folders or --all.")

    periods = active_periods(dt.date.fromisoformat(args.date))
    periods = {period: periods[period] for period in requested_periods}

    deleted = 0
    skipped = 0
    if not args.skip_agent:
        count, skip_count = delete_agent_periodic_notes(root, periods, args.dry_run, args.force)
        deleted += count
        skipped += skip_count

    if not args.agent_only:
        entities = resolve_entities(root, configured, explicit, args.all)
        if entities:
            count, skip_count = delete_periodic_notes(root, entities, periods, args.dry_run, args.force)
            deleted += count
            skipped += skip_count
        elif explicit or args.all:
            print("No matching context folders to clean.")

    if deleted == 0:
        if skipped:
            print(f"No current periodic notes deleted; skipped {skipped} non-managed note(s). Use --force to delete editable source notes.")
        else:
            print("No current periodic notes matched.")


if __name__ == "__main__":
    main()
