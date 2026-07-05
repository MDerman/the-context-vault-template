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


CONFIG_PATH = Path("_master/system/config.json")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LABEL = "com.obsidian-context-vault.refresh"
STATE_DIR = Path.home() / "Library/Application Support/obsidian-context-vault"
LOG_DIR = Path.home() / "Library/Logs"


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
    path = root / CONFIG_PATH
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


def status(root: Path) -> int:
    config = load_refresh_config(root)
    label = label_from_config(config)
    path = plist_path(label)
    result = run_launchctl(["print", launch_service(label)], check=False, quiet=True)
    loaded = result.returncode == 0
    stamp = STATE_DIR / "last-refresh-date.txt"
    timezone_value = str(config.get("timezone") or "local")
    timezone_label = system_timezone() if timezone_value.lower() in {"local", "system"} else timezone_value
    print(f"label: {label}")
    print(f"plist: {path}")
    print(f"loaded: {'yes' if loaded else 'no'}")
    print(f"timezone: {timezone_value} ({timezone_label})")
    print(f"time: {config_int(config, 'hour', 2):02d}:{config_int(config, 'minute', 0):02d}")
    print(f"catchup_interval_seconds: {config_int(config, 'catchup_interval_seconds', 60)}")
    print(f"retry_attempts: {config_int(config, 'retry_attempts', 3)}")
    print(f"retry_delay_seconds: {config_int(config, 'retry_delay_seconds', 60)}")
    print(f"last_refresh_date: {stamp.read_text(encoding='utf-8').strip() if stamp.exists() else 'none'}")
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
        "--skip-brain-dump",
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
    subparsers.add_parser("status")
    subparsers.add_parser("run-due")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    if args.command == "register":
        return register(root, args.dry_run)
    if args.command == "unregister":
        return unregister(root, args.dry_run)
    if args.command == "status":
        return status(root)
    if args.command == "run-due":
        return run_due(root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
