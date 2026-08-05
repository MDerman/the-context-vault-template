#!/usr/bin/env python3
"""Run the full vault refresh pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from script_utils import configured_context_folders, context_folder_note_path, resolve_vault_root


DEFAULT_ENTITIES = ["personal", "personal-brand", "business"]
REFRESH_COMPLETION_MARKER = Path("_system/local/state/refresh-complete.json")
CONTEXT_NINE_CLI_COMMAND = "context-nine:refresh-periodic-tabs"


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


def local_today() -> dt.date:
    return dt.date.today()


def write_refresh_completion(
    root: Path,
    day: dt.date,
    periods: dict[str, str],
    *,
    completed_at: dt.datetime | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    completed_at = completed_at or dt.datetime.now().astimezone()
    completed_at_text = completed_at.isoformat(timespec="seconds")
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "runId": run_id or f"{completed_at_text}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
        "completedAt": completed_at_text,
        "effectiveDate": day.isoformat(),
        "periods": periods,
    }
    path = root / REFRESH_COMPLETION_MARKER
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def obsidian_process_is_running() -> bool:
    names = ["Obsidian"] if sys.platform == "darwin" else ["obsidian"] if sys.platform.startswith("linux") else []
    for name in names:
        try:
            result = subprocess.run(
                ["pgrep", "-x", name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return False
        if result.returncode == 0:
            return True
    return False


def obsidian_cli_path() -> str | None:
    candidates = [shutil.which("obsidian")]
    if sys.platform == "darwin":
        candidates.append("/usr/local/bin/obsidian")
    elif sys.platform.startswith("linux"):
        candidates.append(str(Path.home() / ".local/bin/obsidian"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def notify_context_nine(root: Path, payload: dict[str, object]) -> bool:
    if not obsidian_process_is_running():
        return False
    command = obsidian_cli_path()
    if not command:
        return False
    args = [
        command,
        CONTEXT_NINE_CLI_COMMAND,
        f"date={payload['effectiveDate']}",
        f"run-id={payload['runId']}",
    ]
    try:
        result = subprocess.run(args, cwd=root, text=True, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Warning: Context Nine refresh notification failed: {error}; marker fallback remains active.", file=sys.stderr)
        return False
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        print(f"Warning: Context Nine refresh notification failed: {detail}; marker fallback remains active.", file=sys.stderr)
        return False
    if result.stdout.strip():
        print(f"Context Nine periodic tabs: {result.stdout.strip()}")
    return True


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
    git_preflight_group = parser.add_mutually_exclusive_group()
    git_preflight_group.add_argument(
        "--skip-git-preflight",
        action="store_true",
        help="Skip fetch and fast-forward-only Git preflight.",
    )
    git_preflight_group.add_argument(
        "--best-effort-git-preflight",
        action="store_true",
        help="Attempt Git preflight but continue local generation if fetch or fast-forward is blocked.",
    )
    parser.add_argument("--git-depth", type=int, default=100, help="Local Git commit history depth to keep during maintenance.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    script_dir = root / "_system/commands"

    if not args.skip_git_preflight:
        preflight_command = [sys.executable, str(script_dir / "git_preflight.py"), "--root", str(root)]
        if args.best_effort_git_preflight:
            run_optional(preflight_command, root, "Git preflight")
        else:
            run(preflight_command, root)

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

    day = dt.date.fromisoformat(args.date) if args.date else local_today()
    _, periods, _ = generate_derived_views(
        root,
        explicit_entities=parse_entities(args.context_folders),
        include_all=args.all,
        day=day,
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
    if day == local_today():
        completion = write_refresh_completion(root, day, periods)
        notify_context_nine(root, completion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
