#!/usr/bin/env python3
"""Small command dispatcher for common vault operations."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]

COMMANDS = {
    "refresh": SCRIPT_DIR / "refresh.py",
    "sync": SCRIPT_DIR / "brain_dump.py",
    "context": SCRIPT_DIR / "context.py",
    "inventory": SCRIPT_DIR / "inventory.py",
    "content": SCRIPT_DIR / "content.py",
    "periodic": SCRIPT_DIR / "periodic.py",
    "attachments": SCRIPT_DIR / "attachments.py",
    "backup": SCRIPT_DIR / "backup.py",
    "bootstrap-export": SCRIPT_DIR / "bootstrap_export.py",
    "epic": SCRIPT_DIR / "epic.py",
    "project": SCRIPT_DIR / "project.py",
    "task": SCRIPT_DIR / "task.py",
    "folder": SCRIPT_DIR / "folder.py",
    "gcal": SCRIPT_DIR / "gcal.py",
    "git-maintenance": SCRIPT_DIR / "git_maintenance.py",
    "mobile-profile": SCRIPT_DIR / "mobile_profile.py",
    "profile": SCRIPT_DIR / "profile.py",
    "path-audit": SCRIPT_DIR / "path_audit.py",
    "triage": ROOT / "_master/agents/skills/brain-dump-organizer/scripts/triage.py",
    "upgrade": SCRIPT_DIR / "upgrade.py",
}


def print_help() -> None:
    print(
        """usage: vault <command> [args...]

Common commands:
  root         Print the current vault root path.
  refresh      Ingest configured sources and regenerate agent context.
  sync         Import the configured Brain Dump Apple Note.
  context      Regenerate agent-readable context and dashboard files.
  inventory    Print contexts, statuses, epics, and projects for routing.
  content      Generate current content schedule notes.
  periodic     Generate current agent periodic rollups.
  attachments  Dry-run, apply, or verify attachment routing.
  backup       Back up root .obsidian.
  bootstrap-export  Export the public bootstrap vault.
  epic         Create, rename, delete, list epics and sync epic task Bases.
  project      Create and list project notes.
  task         Create TaskNotes tasks with validated project/epic links.
  folder       Create/register a context folder.
  gcal         Read/write Google Calendar time blocks and task date mirrors.
  git-maintenance  Keep local Git history shallow and prune local objects.
  mobile-profile  Create/update .obsidian-mobile with safe mobile plugins and theme settings.
  profile      Preview/apply Obsidian profile, theme, hotkey, and plugin upgrades.
  path-audit   Find persisted vault-root paths that make the vault non-portable.
  triage       Prepare/apply Brain Dump organizer proposals.
  upgrade      Preview/apply public bootstrap vault upgrades.

Examples:
  cd "$(vault root)"
  vault refresh
  vault refresh --all
  vault inventory
  vault task create business "Follow up with partner" --project "Partnerships" --epic "Growth"
  vault project create business "New Project" --epic "Growth"
  vault attachments --verify-only
  vault bootstrap-export --dry-run
  vault epic create business "New Epic"
  vault gcal list --days 7 --calendar all --json
  vault git-maintenance
  vault mobile-profile
  vault profile upgrade --dry-run
  vault path-audit
  vault triage prepare
  vault upgrade --dry-run

Run `vault <command> --help` for command-specific flags."""
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print_help()
        return 0

    command = args.pop(0)
    if command == "root":
        print(ROOT)
        return 0

    script = COMMANDS.get(command)
    if script is None:
        print(f"Unknown vault command: {command}", file=sys.stderr)
        print_help()
        return 2
    if not script.exists():
        print(f"Vault command target does not exist: {script}", file=sys.stderr)
        return 2

    result = subprocess.run([sys.executable, str(script), *args], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
