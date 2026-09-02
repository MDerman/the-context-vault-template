#!/usr/bin/env python3
"""Small command dispatcher for common vault operations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

from vault_layout import VAULT_ROOT


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = VAULT_ROOT
def configured_repository(repository_id: str) -> Path | None:
    instance = ROOT / "_system/agents/_package/instance"
    workspaces_path = instance / "fleet/workspaces.json"
    machines_path = instance / "fleet/machines.json"
    if not workspaces_path.is_file() or not machines_path.is_file():
        return None
    workspaces = json.loads(workspaces_path.read_text(encoding="utf-8"))
    machines = json.loads(machines_path.read_text(encoding="utf-8"))
    identity = subprocess.run(
        ["git", "-C", str(ROOT), "config", "--get", "vault.machine-id"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    machine = next((item for item in machines.get("machines", []) if item.get("id") == identity), None)
    entry = workspaces.get("entries", {}).get(repository_id)
    if not isinstance(machine, dict) or not isinstance(entry, dict):
        return None
    home = str(machine.get("home") or "")
    roots = machine.get("roots")
    raw_code = roots.get("code") if isinstance(roots, dict) else None
    relative = entry.get("path")
    if not home.startswith("/") or not isinstance(raw_code, str) or not isinstance(relative, str):
        return None
    code_root = Path(home) / raw_code[2:] if raw_code.startswith("~/") else Path(raw_code)
    return code_root.joinpath(*Path(relative).parts).resolve()


CONTEXT_NINE_PLUGIN_ROOT = configured_repository("context-nine-obsidian-plugin") or Path("/__missing_context_nine_plugin__")
CONTEXT_NINE_TUI_ROOT = CONTEXT_NINE_PLUGIN_ROOT / "python"

COMMANDS = {
    "access": SCRIPT_DIR / "remote_access.py",
    "refresh": SCRIPT_DIR / "refresh.py",
    "refresh-schedule": SCRIPT_DIR / "refresh_schedule.py",
    "mac-startup": SCRIPT_DIR / "mac_startup.py",
    "sync": SCRIPT_DIR / "brain_dump.py",
    "inventory": SCRIPT_DIR / "inventory.py",
    "content": SCRIPT_DIR / "content.py",
    "periodic": SCRIPT_DIR / "periodic.py",
    "attachments": SCRIPT_DIR / "attachments.py",
    "backup": SCRIPT_DIR / "backup.py",
    "backup-sync": SCRIPT_DIR / "backup_sync.py",
    "bootstrap-export": SCRIPT_DIR / "bootstrap_export.py",
    "snippets": SCRIPT_DIR / "snippets.py",
    "epic": SCRIPT_DIR / "epic.py",
    "project": SCRIPT_DIR / "project.py",
    "task": SCRIPT_DIR / "task.py",
    "folder": SCRIPT_DIR / "folder.py",
    "business-toolkit": SCRIPT_DIR / "business_toolkit.py",
    "git-media": SCRIPT_DIR / "git_media.py",
    "git-maintenance": SCRIPT_DIR / "git_maintenance.py",
    "git-preflight": SCRIPT_DIR / "git_preflight.py",
    "mobile-profile": SCRIPT_DIR / "mobile_profile.py",
    "machine": SCRIPT_DIR / "machine.py",
    "worker-sync": SCRIPT_DIR / "worker_bootstrap.py",
    "profile": SCRIPT_DIR / "profile.py",
    "path-audit": SCRIPT_DIR / "path_audit.py",
    "release": SCRIPT_DIR / "release.py",
    "triage": SCRIPT_DIR / "brain_dump_triage.py",
    "upgrade": SCRIPT_DIR / "upgrade.py",
}


COMMAND_CAPABILITIES: dict[str, frozenset[str]] = {
    "root": frozenset({"content-read"}),
    "access": frozenset(),
    "refresh": frozenset({"git-owner"}),
    "refresh-schedule": frozenset({"git-owner"}),
    "mac-startup": frozenset({"fleet-owner"}),
    "sync": frozenset({"content-write"}),
    "inventory": frozenset({"content-read"}),
    "content": frozenset({"content-write"}),
    "periodic": frozenset({"content-write"}),
    "attachments": frozenset({"content-write"}),
    "backup": frozenset({"content-write"}),
    "backup-sync": frozenset({"content-write"}),
    "bootstrap-export": frozenset({"fleet-owner"}),
    "snippets": frozenset({"content-write"}),
    "epic": frozenset({"content-write"}),
    "project": frozenset({"content-write"}),
    "task": frozenset({"content-write"}),
    "folder": frozenset({"content-write"}),
    "business-toolkit": frozenset({"content-write"}),
    "git-media": frozenset({"git-owner"}),
    "git-maintenance": frozenset({"git-owner"}),
    "git-preflight": frozenset({"git-owner"}),
    "mobile-profile": frozenset({"content-write"}),
    "machine": frozenset({"fleet-owner"}),
    "worker-sync": frozenset({"fleet-owner"}),
    "profile": frozenset({"fleet-owner"}),
    "path-audit": frozenset({"content-read"}),
    "release": frozenset({"git-owner", "fleet-owner"}),
    "triage": frozenset({"content-write"}),
    "upgrade": frozenset({"fleet-owner"}),
    "tui": frozenset({"content-read"}),
}


def current_machine(registry: dict[str, object]) -> dict[str, object]:
    identity_path = Path.home() / ".config/vault/machine-id"
    identity = identity_path.read_text(encoding="utf-8").strip() if identity_path.is_file() else ""
    if not identity:
        identity = subprocess.run(
            ["git", "-C", str(ROOT), "config", "--get", "vault.machine-id"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout.strip()
    machines = registry.get("machines")
    machine = next(
        (
            item
            for item in machines
            if isinstance(item, dict) and item.get("id") == identity
        ),
        None,
    ) if isinstance(machines, list) else None
    if not isinstance(machine, dict) or not machine.get("enabled"):
        raise RuntimeError("Vault machine identity is unresolved or disabled")
    return machine


def access_status() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "remote_access.py"), "status", "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Vault access status is unavailable")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Vault access status returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Vault access status returned an invalid record")
    return value


def command_capabilities(command: str, args: list[str]) -> frozenset[str] | None:
    if command == "attachments" and "--verify-only" in args:
        return frozenset({"content-read"})
    return COMMAND_CAPABILITIES.get(command)


def enforce_command_policy(command: str, args: list[str]) -> None:
    capabilities = command_capabilities(command, args)
    if capabilities is None:
        raise RuntimeError(f"Vault command has no capability policy: {command}")
    if command == "access":
        return
    registry_path = ROOT / "_system/agents/_package/instance/fleet/machines.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != 7:
        raise RuntimeError("Vault command policy requires machine registry schema_version 7")
    machine = current_machine(registry)
    vault = machine.get("vault")
    if not isinstance(vault, dict) or not vault.get("enabled"):
        raise RuntimeError("this machine is not an enabled Vault participant")
    vault_git = registry.get("vault_git")
    if not isinstance(vault_git, dict):
        raise RuntimeError("Vault Git ownership is not configured")
    if "git-owner" in capabilities and vault_git.get("owner_machine_id") != machine.get("id"):
        raise RuntimeError("this command is restricted to the registered Vault Git owner")
    if "fleet-owner" in capabilities and registry.get("primary_machine_id") != machine.get("id"):
        raise RuntimeError("this command is restricted to the registered fleet primary")
    mode = vault.get("checkout_mode")
    if "content-read" in capabilities and mode == "remote-sshfs":
        state = access_status()
        if not state.get("ok") or not isinstance(state.get("mount"), dict) or not state["mount"].get("healthy"):
            raise RuntimeError("remote Vault access is unhealthy")
    if "content-write" in capabilities:
        state = access_status()
        active = state.get("active_session")
        host = state.get("host")
        lease = host.get("lease") if isinstance(host, dict) else None
        if (
            not state.get("ok")
            or not isinstance(active, dict)
            or not isinstance(lease, dict)
            or active.get("session_id") != lease.get("session_id")
            or machine.get("id") != lease.get("machine_id")
            or lease.get("expired")
        ):
            raise RuntimeError("content writes require an active owned vault access session")
    if capabilities & {"git-owner", "fleet-owner"}:
        try:
            state = access_status()
        except RuntimeError:
            state = {}
        host = state.get("host")
        lease = host.get("lease") if isinstance(host, dict) else None
        if isinstance(lease, dict) and lease.get("machine_id") != machine.get("id"):
            raise RuntimeError(
                f"primary operation blocked by active Vault writer {lease.get('machine_id')} "
                f"session {lease.get('session_id')}"
            )


DEFAULT_APPLY_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "attachments": ((),),
    "snippets": (("sync",),),
    "business-toolkit": (("sync",), ("unconfigure",)),
    "git-media": (("install-hook",),),
    "machine": (
        ("init",),
        ("setup",),
        ("register-worker",),
        ("identify",),
        ("access", "configure"),
        ("access", "switch"),
        ("access", "render"),
    ),
    "worker-sync": (("install-hooks",), ("bootstrap",)),
    "profile": (("upgrade",),),
    "folder": (("remove",),),
}


def with_default_apply(command: str, args: list[str]) -> list[str]:
    """Add the legacy apply flag when a mutating Vault command omits an explicit mode."""
    explicit_modes = {"--apply", "--dry-run", "--verify", "--verify-only", "-h", "--help"}
    if explicit_modes.intersection(args):
        return args
    if command == "upgrade":
        read_only = {"status", "doctor", "repair-prompt", "init-state"}
        return args if read_only.intersection(args) else [*args, "--apply"]
    prefixes = DEFAULT_APPLY_PREFIXES.get(command, ())
    if any(tuple(args[: len(prefix)]) == prefix for prefix in prefixes):
        return [*args, "--apply"]
    return args


def print_help() -> None:
    print(
        """usage: vault <command> [args...]

Common commands:
  root         Print the current vault root path.
  access       Mount, inspect, lease, finish, and hand off registered Vault access.
  refresh      Refresh integrations, schedules, periodic rollups, and Dashboard.
  refresh-schedule  Register, unregister, or inspect the daily refresh LaunchAgent.
  mac-startup  Manage opt-in, per-machine macOS login automation.
  sync         Import the configured Brain Dump Apple Note.
  inventory    Print live periods, contexts, tasks, epics, and projects for routing.
  content      Generate current content schedule notes.
  periodic     Generate source periodic notes and vault Sync Embed rollups.
  attachments  Apply attachment routing, or preview/verify it explicitly.
  backup       Back up root .obsidian.
  backup-sync  Configure and run optional rclone Google Drive backup/sync.
  bootstrap-export  Export the public bootstrap vault.
  snippets     Check or materialize canonical text blocks across repositories.
  epic         Create, rename, delete, list epics and sync epic task Bases.
  project      Create and list project notes.
  task         Create TaskNotes tasks with validated project/epic links.
  folder       Create, register, or rename a context folder.
  business-toolkit  Configure marker-owned business folders and templates for registered contexts.
  git-media    Manage pointer-only media manifests and no-upload Git hooks.
  git-maintenance  Keep local Git history shallow and prune local objects.
  git-preflight  Fetch and fast-forward a clean master checkout.
  mobile-profile  Create/update .obsidian-mobile with safe mobile plugins and theme settings.
  machine      Prepare, route, list, probe, SSH to, or open VNC for reviewed machines.
  worker-sync  Enforce Gitless iCloud Mac workers.
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
  vault mac-startup status
  vault mac-startup install --dry-run
  vault refresh --all
  vault refresh --sync-brain-dump
  vault inventory
  vault access status
  vault access begin --task-id TASK
  vault access finish
  vault task create business "Follow up with partner" --project "Partnerships" --epic "Growth"
  vault project create business "New Project" --epic "Growth"
  vault attachments --verify-only
  vault backup-sync setup
  vault backup-sync status
  vault backup-sync shared-drives
  vault bootstrap-export --dry-run
  vault snippets check
  vault snippets sync --dry-run
  vault folder register studio
  vault business-toolkit sync --context-folders business,studio
  vault business-toolkit status --configured
  vault folder unregister studio --dry-run
  vault folder remove studio --dry-run
  vault folder rename business studio --dry-run
  vault epic create business "New Epic"
  vault git-media status
  vault git-maintenance
  vault mobile-profile
  vault machine list
  vault machine setup
  vault machine access switch workermacair tailscale --dry-run
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
    if command not in COMMAND_CAPABILITIES:
        print(f"Unknown vault command: {command}", file=sys.stderr)
        print_help()
        return 2
    try:
        enforce_command_policy(command, args)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Vault access policy blocked {command}: {exc}", file=sys.stderr)
        return 2
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

    result = subprocess.run([sys.executable, str(script), *with_default_apply(command, args)], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
