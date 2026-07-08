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
CONTROL_ROOM = BACKUP_SYNC_DIR / "scripts" / "control-room.py"
CONTROL_COMMANDS = {"overview", "health", "watch", "progress", "logs", "start", "stop", "restart"}


def print_help() -> None:
    print(
        """usage: vault backup-sync <command> [args...]

Commands:
  setup        Run interactive backup/sync setup wizard.
  validate     Validate backup/sync config.
  doctor       Check tools, sources, remotes, and mount folders.
  status       Show remotes, sources, mounts, LaunchAgents, logs, and locks.
  status --json  Show machine-readable backup/sync state.
  shared-drives  Add/remove Shared Drive remotes and read-only mounts.
  overview     Show one-screen state for automation, jobs, mounts, progress.
  health       Show concise health, failure state, and next actions.
  watch        Refresh overview repeatedly.
  progress     Parse latest rclone transfer stats from logs.
  logs         Tail a configured latest.log by job/mount name.
  start        Start one sync, external sync, or mount.
  stop         Stop one sync, external sync, or mount.
  restart      Restart one mount.
  sync         Pass through to backup-sync.sh sync.
  mount        Pass through to backup-sync.sh mount.
  external     Pass through to backup-sync.sh external.
  pause        Stop managed syncs/mounts and pause future starts.
  resume       Clear global pause flags; `resume sync|external <job>` reruns one sync.
  stop-syncs   Stop managed sync/external jobs and pause sync starts.
  stop-mounts  Stop managed mounts and pause auto-remount.
  install-launchd    Write and load schedules/auto-remount LaunchAgents.
  uninstall-launchd  Unload and remove backup/sync LaunchAgents.
  clean-uninstall    Remove automation, runtime, locks, and managed mounts.

Examples:
  vault backup-sync setup
  vault backup-sync overview
  vault backup-sync health
  vault backup-sync watch
  vault backup-sync progress external-2tb-sandisk-extreme-videos
  vault backup-sync logs external-2tb-sandisk-extreme-videos --follow
  vault backup-sync start external 2tb-sandisk-extreme-videos
  vault backup-sync stop external 2tb-sandisk-extreme-videos
  vault backup-sync resume sync drive
  vault backup-sync resume external 2tb-sandisk-extreme-videos
  vault backup-sync status
  vault backup-sync shared-drives
  vault backup-sync sync drive --dry-run
  vault backup-sync external 2tb-sandisk-extreme-videos --dry-run
  vault backup-sync pause
  vault backup-sync resume
  vault backup-sync install-launchd

All non-setup commands pass through to _master/backup-and-sync/scripts/backup-sync.sh."""
    )


def run_script(script: Path, args: list[str]) -> int:
    if not script.exists():
        print(f"Backup sync script missing: {script}", file=sys.stderr)
        return 2
    command = [sys.executable, str(script), *args] if script.suffix == ".py" else [str(script), *args]
    result = subprocess.run(command, cwd=BACKUP_SYNC_DIR)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print_help()
        return 0

    command = args.pop(0)
    if command == "setup":
        return run_script(WIZARD, args)
    if command == "status" and "--json" in args:
        filtered_args = [arg for arg in args if arg != "--json"]
        return run_script(CONTROL_ROOM, ["overview", "--json", *filtered_args])
    if args[:1] and args[0] in {"-h", "--help", "help"}:
        if command in CONTROL_COMMANDS or command == "resume":
            return run_script(CONTROL_ROOM, [command, *args])
        print_help()
        return 0
    if command in CONTROL_COMMANDS:
        return run_script(CONTROL_ROOM, [command, *args])
    if command == "resume" and args[:1] in (["sync"], ["external"]):
        return run_script(CONTROL_ROOM, [command, *args])
    return run_script(MANAGER, [command, *args])


if __name__ == "__main__":
    raise SystemExit(main())
