#!/usr/bin/env python3
"""Small command dispatcher for common vault operations."""

from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path

from vault_layout import AGENTS_DIR, VAULT_ROOT


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = VAULT_ROOT
CONTEXT_NINE_PLUGIN_ROOT = Path.home() / "Code/ctx9/context_nine_obsidian_plugin"
CONTEXT_NINE_TUI_ROOT = CONTEXT_NINE_PLUGIN_ROOT / "python"

COMMANDS = {
    "refresh": SCRIPT_DIR / "refresh.py",
    "refresh-schedule": SCRIPT_DIR / "refresh_schedule.py",
    "sync": SCRIPT_DIR / "brain_dump.py",
    "inventory": SCRIPT_DIR / "inventory.py",
    "content": SCRIPT_DIR / "content.py",
    "periodic": SCRIPT_DIR / "periodic.py",
    "attachments": SCRIPT_DIR / "attachments.py",
    "backup": SCRIPT_DIR / "backup.py",
    "backup-sync": SCRIPT_DIR / "backup_sync.py",
    "bootstrap-export": SCRIPT_DIR / "bootstrap_export.py",
    "deps": SCRIPT_DIR / "deps.py",
    "skills": ROOT / AGENTS_DIR / "sync_skills.py",
    "epic": SCRIPT_DIR / "epic.py",
    "project": SCRIPT_DIR / "project.py",
    "task": SCRIPT_DIR / "task.py",
    "folder": SCRIPT_DIR / "folder.py",
    "gcal": SCRIPT_DIR / "gcal.py",
    "git-maintenance": SCRIPT_DIR / "git_maintenance.py",
    "mobile-profile": SCRIPT_DIR / "mobile_profile.py",
    "machine": SCRIPT_DIR / "machine.py",
    "profile": SCRIPT_DIR / "profile.py",
    "path-audit": SCRIPT_DIR / "path_audit.py",
    "release": SCRIPT_DIR / "release.py",
    "triage": SCRIPT_DIR / "brain_dump_triage.py",
    "upgrade": SCRIPT_DIR / "upgrade.py",
}


def print_help() -> None:
    print(
        """usage: vault <command> [args...]

Common commands:
  root         Print the current vault root path.
  refresh      Refresh integrations, schedules, periodic rollups, and Dashboard.
  refresh-schedule  Register, unregister, or inspect the daily refresh LaunchAgent.
  sync         Import the configured Brain Dump Apple Note.
  inventory    Print live periods, contexts, tasks, epics, and projects for routing.
  content      Generate current content schedule notes.
  periodic     Generate source periodic notes and vault Sync Embed rollups.
  attachments  Dry-run, apply, or verify attachment routing.
  backup       Back up root .obsidian.
  backup-sync  Configure and run optional rclone Google Drive backup/sync.
  bootstrap-export  Export the public bootstrap vault.
  deps         Clone/pull external dependency repos and rebuild managed projections.
  skills       Validate skill sources and rebuild active/global discovery links.
  epic         Create, rename, delete, list epics and sync epic task Bases.
  project      Create and list project notes.
  task         Create TaskNotes tasks with validated project/epic links.
  folder       Create, register, or rename a context folder.
  gcal         Read/write Google Calendar events, time blocks, and task date mirrors.
  git-maintenance  Keep local Git history shallow and prune local objects.
  mobile-profile  Create/update .obsidian-mobile with safe mobile plugins and theme settings.
  machine      List, probe, SSH to, or open VNC for reviewed development machines.
  profile      Preview/apply Obsidian profile, theme, hotkey, and plugin upgrades.
  path-audit   Find persisted vault-root paths that make the vault non-portable.
  release      Publish SemVer public vault releases.
  triage       Prepare/apply Brain Dump organizer proposals.
  upgrade      Preview/apply public bootstrap vault upgrades.
  tui          Open the Textual vault command control room.

Examples:
  cd "$(vault root)"
  vault refresh
  vault refresh-schedule register
  vault refresh-schedule unregister
  vault refresh --all
  vault refresh --sync-brain-dump
  vault inventory
  vault task create business "Follow up with partner" --project "Partnerships" --epic "Growth"
  vault project create business "New Project" --epic "Growth"
  vault attachments --verify-only
  vault backup-sync setup
  vault backup-sync status
  vault backup-sync shared-drives
  vault bootstrap-export --dry-run
  vault deps status
  vault deps sync --dry-run
  vault skills sync --dry-run
  vault skills sync --apply
  vault folder register business
  vault folder unregister business --dry-run
  vault folder remove business --dry-run
  vault folder rename business studio --dry-run
  vault epic create business "New Epic"
  vault gcal list --days 7 --calendar all --json
  vault git-maintenance
  vault mobile-profile
  vault machine list
  vault machine status wootbook
  vault machine ssh wootbook
  vault machine vnc wootbook
  vault profile upgrade --dry-run
  vault path-audit
  vault release publish --dry-run
  vault triage prepare
  vault upgrade --dry-run
  vault tui

Run `vault <command> --help` for command-specific flags."""
    )


def run_tui(args: list[str]) -> int:
    tui_args = ["--vault-root", str(ROOT), *args]
    uv = shutil.which("uv")
    if uv and (CONTEXT_NINE_TUI_ROOT / "pyproject.toml").exists():
        return subprocess.run([uv, "run", "vault-tui", *tui_args], cwd=CONTEXT_NINE_TUI_ROOT).returncode
    installed = shutil.which("vault-tui")
    if installed:
        return subprocess.run([installed, *tui_args], cwd=ROOT).returncode
    print(
        "Vault TUI not available. Install uv (`brew install uv`) or install context-nine-vault-tui.",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print_help()
        return 0

    command = args.pop(0)
    if command == "root":
        print(ROOT)
        return 0
    if command == "tui":
        return run_tui(args)

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
