#!/usr/bin/env python3
"""Dispatch backup/sync helper commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
BACKUP_SYNC_DIR = ROOT / "_master" / "backup-and-sync"
MANAGER = BACKUP_SYNC_DIR / "scripts" / "backup-sync.sh"
WIZARD = BACKUP_SYNC_DIR / "scripts" / "setup-wizard.sh"


def print_help() -> None:
    print(
        """usage: vault backup-sync <command> [args...]

Commands:
  setup        Run interactive backup/sync setup wizard.
  validate     Validate backup/sync config.
  doctor       Check tools, sources, remotes, and mount folders.
  status       Show remotes, sources, mounts, LaunchAgents, logs, and locks.
  shared-drives  Add/remove Shared Drive remotes and read-only mounts.
  sync         Pass through to backup-sync.sh sync.
  mount        Pass through to backup-sync.sh mount.
  install-launchd    Write and load schedules/auto-remount LaunchAgents.
  uninstall-launchd  Unload and remove backup/sync LaunchAgents.

Examples:
  vault backup-sync setup
  vault backup-sync status
  vault backup-sync shared-drives
  vault backup-sync sync drive --dry-run
  vault backup-sync install-launchd

All non-setup commands pass through to _master/backup-and-sync/scripts/backup-sync.sh."""
    )


def run_script(script: Path, args: list[str]) -> int:
    if not script.exists():
        print(f"Backup sync script missing: {script}", file=sys.stderr)
        return 2
    result = subprocess.run([str(script), *args], cwd=BACKUP_SYNC_DIR)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print_help()
        return 0

    command = args.pop(0)
    if command == "setup":
        return run_script(WIZARD, args)
    return run_script(MANAGER, [command, *args])


if __name__ == "__main__":
    raise SystemExit(main())
