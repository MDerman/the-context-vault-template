#!/usr/bin/env python3
"""Run the vault refresh pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from script_utils import resolve_vault_root


def run(command: list[str], root: Path) -> None:
    subprocess.run(command, cwd=root, check=True)


def run_optional(command: list[str], root: Path, label: str) -> None:
    result = subprocess.run(command, cwd=root)
    if result.returncode != 0:
        print(f"Warning: {label} failed with exit code {result.returncode}; continuing refresh.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh vault agent context and configured sources.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--skip-brain-dump", action="store_true", help="Skip configured Brain Dump ingestion.")
    parser.add_argument("--skip-gcal", action="store_true", help="Skip Google Calendar TaskNotes date mirror.")
    parser.add_argument("--no-clear-brain-dump", action="store_true", help="Ingest Brain Dump without clearing the source note.")
    parser.add_argument("--all", action="store_true", help="Refresh all context folders, passed through to context.py.")
    parser.add_argument("--context-folders", default=None, help="Comma-separated context folders, passed through to context.py.")
    parser.add_argument("--date", default=None, help="Refresh date, passed through to context.py.")
    parser.add_argument("--keep-agent-periodic-history", action="store_true", help="Keep stale generated agent periodic rollups.")
    parser.add_argument("--skip-git-maintenance", action="store_true", help="Skip local Git shallow prune/gc maintenance.")
    parser.add_argument("--git-depth", type=int, default=5, help="Local Git commit history depth to keep during maintenance.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    script_dir = root / "master/system/scripts"

    if not args.skip_brain_dump:
        ingest_command = [sys.executable, str(script_dir / "brain_dump.py"), "--root", str(root)]
        if args.no_clear_brain_dump:
            ingest_command.append("--no-clear")
        run(ingest_command, root)

    if not args.skip_gcal:
        run_optional(
            [sys.executable, str(script_dir / "gcal.py"), "--root", str(root), "sync-tasks", "--apply"],
            root,
            "Google Calendar task sync",
        )

    context_command = [sys.executable, str(script_dir / "context.py"), "--root", str(root)]
    if args.all:
        context_command.append("--all")
    if args.context_folders:
        context_command.extend(["--context-folders", args.context_folders])
    if args.date:
        context_command.extend(["--date", args.date])
    if args.keep_agent_periodic_history:
        context_command.append("--keep-agent-periodic-history")
    run(context_command, root)

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
