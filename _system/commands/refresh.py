#!/usr/bin/env python3
"""Run the full vault refresh pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

from script_utils import configured_context_folders, context_folder_note_path, resolve_vault_root


DEFAULT_ENTITIES = ["personal", "personal-brand", "business"]


def parse_entities(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def entity_content_enabled(root: Path, entity: str) -> bool:
    note = context_folder_note_path(root / entity)
    if not note.exists():
        return False
    for line in note.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("content_enabled:"):
            return line.split(":", 1)[1].strip().lower() in {"true", "yes", "1"}
    return False


def generate_derived_views(
    root: Path,
    *,
    configured_entities: list[str] | None = None,
    explicit_entities: list[str] | None = None,
    include_all: bool = False,
    day: dt.date | None = None,
) -> tuple[list[str], dict[str, str], list[dict[str, str]]]:
    """Generate content schedules, periodic source notes, vault rollups, and Dashboard."""
    import content
    import dashboard
    import periodic

    day = day or dt.date.today()
    configured = configured_context_folders(root, configured_entities or [], DEFAULT_ENTITIES)
    explicit = explicit_entities or []
    selected = periodic.resolve_entities(root, configured, explicit, include_all)
    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    content_entities = [entity for entity in selected if entity_content_enabled(root, entity)]
    schedules = content.generate_content_schedules(
        root,
        content_entities,
        day,
        generated_at=generated_at,
    )
    selected, periods = periodic.generate_periodic_notes(
        root,
        configured,
        explicit,
        include_all,
        day,
        generated_at=generated_at,
    )
    dashboard.write_dashboard(root, selected, periods, schedules, generated_at, day)
    return selected, periods, schedules


def run(command: list[str], root: Path) -> None:
    subprocess.run(command, cwd=root, check=True)


def run_optional(command: list[str], root: Path, label: str) -> None:
    result = subprocess.run(command, cwd=root)
    if result.returncode != 0:
        print(f"Warning: {label} failed with exit code {result.returncode}; continuing refresh.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh vault schedules, periodic rollups, Dashboard, and integrations.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--sync-brain-dump", action="store_true", help="Ingest configured Brain Dump Apple Note.")
    parser.add_argument("--skip-gcal", action="store_true", help="Skip Google Calendar TaskNotes date mirror.")
    parser.add_argument(
        "--no-clear-brain-dump",
        action="store_true",
        help="When used with --sync-brain-dump, ingest Brain Dump without clearing the source note.",
    )
    parser.add_argument("--all", action="store_true", help="Refresh all registered context folders.")
    parser.add_argument("--context-folders", default=None, help="Comma-separated context folders for this refresh.")
    parser.add_argument("--date", default=None, help="Refresh date in YYYY-MM-DD form. Defaults to today.")
    parser.add_argument("--skip-git-maintenance", action="store_true", help="Skip local Git shallow prune/gc maintenance.")
    parser.add_argument("--git-depth", type=int, default=5, help="Local Git commit history depth to keep during maintenance.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    script_dir = root / "_system/commands"

    if args.sync_brain_dump:
        ingest_command = [sys.executable, str(script_dir / "brain_dump.py"), "--root", str(root)]
        if args.no_clear_brain_dump:
            ingest_command.append("--no-clear")
        run(ingest_command, root)

    if not args.skip_gcal:
        run_optional(
            [
                sys.executable,
                str(script_dir / "gcal.py"),
                "--root",
                str(root),
                "sync-tasks",
                "--apply",
                "--prune-orphaned-task-events",
            ],
            root,
            "Google Calendar task sync",
        )

    generate_derived_views(
        root,
        explicit_entities=parse_entities(args.context_folders),
        include_all=args.all,
        day=dt.date.fromisoformat(args.date) if args.date else dt.date.today(),
    )

    if not args.skip_git_maintenance:
        run_optional(
            [
                sys.executable,
                str(script_dir / "git_maintenance.py"),
                "--root",
                str(root),
                "--depth",
                str(args.git_depth),
            ],
            root,
            "Git maintenance",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
