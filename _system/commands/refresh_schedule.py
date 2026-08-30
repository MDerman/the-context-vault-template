#!/usr/bin/env python3
"""Register a macOS LaunchAgent for the daily vault refresh."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from script_utils import resolve_vault_root
from vault_layout import VAULT_CONFIG_PATH


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LABEL = "com.obsidian-context-vault.refresh"
STATE_DIR = Path.home() / "Library/Application Support/obsidian-context-vault"
WORKER_BLOCK_NAME = "worker-refresh-block.json"
LOG_DIR = Path.home() / "Library/Logs"
MACHINE_ID_PATH = Path.home() / ".config/vault/machine-id"


def system_timezone() -> str:
    try:
        localtime = Path("/etc/localtime").resolve()
        parts = localtime.parts
        if "zoneinfo" in parts:
            index = parts.index("zoneinfo")
            zone = "/".join(parts[index + 1 :])
            if zone:
                return zone
    except OSError:
        pass
    return "UTC"


def load_refresh_config(root: Path) -> dict[str, object]:
    config: dict[str, object] = {
        "enabled": True,
        "label": DEFAULT_LABEL,
        "timezone": system_timezone(),
        "hour": 2,
        "minute": 0,
        "catchup_interval_seconds": 60,
        "retry_attempts": 3,
        "retry_delay_seconds": 60,
    }
    path = root / VAULT_CONFIG_PATH
    if not path.exists():
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return config
    raw = data.get("refresh_schedule", {})
    if isinstance(raw, dict):
        config.update(raw)
    return config


def config_int(config: dict[str, object], key: str, default: int) -> int:
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def label_from_config(config: dict[str, object]) -> str:
    value = str(config.get("label") or DEFAULT_LABEL).strip()
    return value or DEFAULT_LABEL


def timezone_from_config(config: dict[str, object]) -> ZoneInfo:
    name = str(config.get("timezone") or system_timezone()).strip()
    if name.lower() in {"local", "system"}:
        name = system_timezone()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def plist_path(label: str) -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{label}.plist"


def launch_domain() -> str:
    return f"gui/{os.getuid()}"


def launch_service(label: str) -> str:
    return f"{launch_domain()}/{label}"


def machine_schedule_policy(root: Path) -> dict[str, object]:
    block_path = STATE_DIR / WORKER_BLOCK_NAME
    if block_path.is_file():
        try:
            block = json.loads(block_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            block = {}
        if not isinstance(block, dict):
            block = {}
        return {
            "eligible": False,
            "machineId": block.get("machineId"),
            "role": "worker",
            "blockedReason": "persistent machine-local worker block prohibits scheduled vault refresh",
        }
    role_result = subprocess.run(
        ["git", "config", "--local", "--get", "vault.machine-role"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    configured_role = role_result.stdout.strip()
    result = subprocess.run(
        ["git", "config", "--local", "--get", "vault.machine-id"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    machine_id = result.stdout.strip()
    if not machine_id:
        try:
            machine_id = MACHINE_ID_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            machine_id = ""
    if configured_role == "worker":
        return {
            "eligible": False,
            "machineId": machine_id or None,
            "role": "worker",
            "blockedReason": "scheduled vault refresh is primary-only and cannot run on a worker",
        }
    registry_path = (
        root
        / "_system/agents/_package/instance/fleet/machines.json"
    )
    if not machine_id or not registry_path.is_file():
        return {"eligible": True, "machineId": machine_id or None, "role": None}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"eligible": True, "machineId": machine_id, "role": None}
    machine = next(
        (item for item in registry.get("machines", []) if item.get("id") == machine_id),
        None,
    )
    role = machine.get("role") if isinstance(machine, dict) else None
    eligible = role != "worker"
    return {
        "eligible": eligible,
        "machineId": machine_id,
        "role": role,
        "blockedReason": (
            "scheduled vault refresh is primary-only and cannot run on a worker"
            if not eligible
            else None
        ),
    }


def block_worker(machine_id: str, dry_run: bool) -> int:
    path = STATE_DIR / WORKER_BLOCK_NAME
    if dry_run:
        print(f"would write persistent worker refresh block: {path}")
        return 0
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps({"machineId": machine_id, "role": "worker"}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"blocked scheduled vault refresh on worker {machine_id}")
    return 0


def refresh_command(root: Path) -> list[str]:
    return [sys.executable, str(SCRIPT_DIR / "refresh_schedule.py"), "--root", str(root), "run-due"]


def launch_agent_plist(root: Path, config: dict[str, object]) -> dict[str, object]:
    label = label_from_config(config)
    plist = {
        "Label": label,
        "ProgramArguments": refresh_command(root),
        "WorkingDirectory": str(root),
        "StartCalendarInterval": {
            "Hour": config_int(config, "hour", 2),
            "Minute": config_int(config, "minute", 0),
        },
        "RunAtLoad": True,
        "StandardOutPath": str(LOG_DIR / "obsidian-context-vault-refresh.out.log"),
        "StandardErrorPath": str(LOG_DIR / "obsidian-context-vault-refresh.err.log"),
    }
    catchup_interval = config_int(config, "catchup_interval_seconds", 60)
    if catchup_interval > 0:
        plist["StartInterval"] = catchup_interval
    return plist


def run_launchctl(args: list[str], *, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    stdout = subprocess.DEVNULL if quiet else None
    stderr = subprocess.DEVNULL if quiet else None
    return subprocess.run(["launchctl", *args], text=True, check=check, stdout=stdout, stderr=stderr)


def register(root: Path, dry_run: bool) -> int:
    if sys.platform != "darwin":
        print("refresh schedule requires macOS launchd", file=sys.stderr)
        return 2
    policy = machine_schedule_policy(root)
    if not policy["eligible"]:
        print(
            f"refresh schedule refused for worker {policy['machineId']}: {policy['blockedReason']}",
            file=sys.stderr,
        )
        return 3
    config = load_refresh_config(root)
    label = label_from_config(config)
    path = plist_path(label)
    plist = launch_agent_plist(root, config)
    if dry_run:
        print(f"would write {path}")
        print(f"would bootstrap {launch_domain()} {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(plist, sort_keys=False))
    run_launchctl(["bootout", launch_domain(), str(path)], check=False, quiet=True)
    run_launchctl(["bootstrap", launch_domain(), str(path)])
    run_launchctl(["enable", launch_service(label)], check=False)
    print(f"registered {label}: {path}")
    return run_due(root)


def unregister(root: Path, dry_run: bool) -> int:
    if sys.platform != "darwin":
        print("refresh schedule requires macOS launchd", file=sys.stderr)
        return 2
    config = load_refresh_config(root)
    label = label_from_config(config)
    path = plist_path(label)
    if dry_run:
        print(f"would bootout {launch_domain()} {path}")
        print(f"would remove {path}")
        return 0
    run_launchctl(["bootout", launch_domain(), str(path)], check=False, quiet=True)
    if path.exists():
        path.unlink()
    print(f"unregistered {label}")
    return 0


def status_payload(root: Path) -> dict[str, object]:
    config = load_refresh_config(root)
    label = label_from_config(config)
    path = plist_path(label)
    result = run_launchctl(["print", launch_service(label)], check=False, quiet=True)
    loaded = result.returncode == 0
    stamp = STATE_DIR / "last-refresh-date.txt"
    timezone_value = str(config.get("timezone") or "local")
    timezone_label = system_timezone() if timezone_value.lower() in {"local", "system"} else timezone_value
    return {
        "label": label,
        "plist": str(path),
        "loaded": loaded,
        "timezone": timezone_value,
        "timezoneLabel": timezone_label,
        "time": f"{config_int(config, 'hour', 2):02d}:{config_int(config, 'minute', 0):02d}",
        "catchupIntervalSeconds": config_int(config, "catchup_interval_seconds", 60),
        "retryAttempts": config_int(config, "retry_attempts", 3),
        "retryDelaySeconds": config_int(config, "retry_delay_seconds", 60),
        "lastRefreshDate": stamp.read_text(encoding="utf-8").strip() if stamp.exists() else None,
        **machine_schedule_policy(root),
    }


def status(root: Path, json_output: bool = False) -> int:
    payload = status_payload(root)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"label: {payload['label']}")
    print(f"plist: {payload['plist']}")
    print(f"loaded: {'yes' if payload['loaded'] else 'no'}")
    print(f"timezone: {payload['timezone']} ({payload['timezoneLabel']})")
    print(f"time: {payload['time']}")
    print(f"catchup_interval_seconds: {payload['catchupIntervalSeconds']}")
    print(f"retry_attempts: {payload['retryAttempts']}")
    print(f"retry_delay_seconds: {payload['retryDelaySeconds']}")
    print(f"last_refresh_date: {payload['lastRefreshDate'] or 'none'}")
    print(f"eligible: {'yes' if payload['eligible'] else 'no'}")
    if payload.get("blockedReason"):
        print(f"blocked_reason: {payload['blockedReason']}")
    return 0


def run_refresh_with_retries(root: Path, today: str, config: dict[str, object]) -> int:
    attempts = max(1, config_int(config, "retry_attempts", 3))
    retry_delay = max(0, config_int(config, "retry_delay_seconds", 60))
    command = [
        sys.executable,
        str(SCRIPT_DIR / "refresh.py"),
        "--root",
        str(root),
        "--date",
        today,
        "--best-effort-git-preflight",
    ]
    for attempt in range(1, attempts + 1):
        print(f"refresh attempt {attempt}/{attempts} for {today}")
        result = subprocess.run(command, cwd=root)
        if result.returncode == 0:
            return 0
        if attempt < attempts and retry_delay:
            print(f"refresh attempt {attempt}/{attempts} failed with exit code {result.returncode}; retrying in {retry_delay}s", file=sys.stderr)
            time.sleep(retry_delay)
        elif attempt < attempts:
            print(f"refresh attempt {attempt}/{attempts} failed with exit code {result.returncode}; retrying", file=sys.stderr)
    print(f"refresh failed after {attempts} attempts for {today}", file=sys.stderr)
    return result.returncode


def run_due(root: Path) -> int:
    policy = machine_schedule_policy(root)
    if not policy["eligible"]:
        print(
            f"refresh schedule skipped for worker {policy['machineId']}: {policy['blockedReason']}"
        )
        return 0
    config = load_refresh_config(root)
    if not bool(config.get("enabled", True)):
        print("refresh schedule disabled in config")
        return 0
    zone = timezone_from_config(config)
    today = dt.datetime.now(zone).date().isoformat()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_DIR / "refresh.lock"
    stamp_path = STATE_DIR / "last-refresh-date.txt"
    with lock_path.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if stamp_path.exists() and stamp_path.read_text(encoding="utf-8").strip() == today:
            return 0
        result = run_refresh_with_retries(root, today, config)
        if result == 0:
            stamp_path.write_text(today + "\n", encoding="utf-8")
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register or run the daily vault refresh LaunchAgent.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("register", "unregister"):
        command = subparsers.add_parser(name)
        command.add_argument("--dry-run", action="store_true")
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable status JSON.")
    block_parser = subparsers.add_parser("block-worker")
    block_parser.add_argument("--machine-id", required=True)
    block_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("run-due")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    if args.command == "register":
        return register(root, args.dry_run)
    if args.command == "unregister":
        return unregister(root, args.dry_run)
    if args.command == "status":
        return status(root, json_output=args.json)
    if args.command == "block-worker":
        return block_worker(args.machine_id, args.dry_run)
    if args.command == "run-due":
        return run_due(root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
