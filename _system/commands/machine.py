#!/usr/bin/env python3
"""Operate reviewed development machines from one private vault registry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import socket
import subprocess
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from vault_layout import CONFIG_DIR, VAULT_ROOT

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = VAULT_ROOT
DEFAULT_REGISTRY = ROOT / CONFIG_DIR / "machines.private.json"
DEFAULT_RUNTIME_DIR = Path.home() / ".cache/vault-machine"


class MachineError(RuntimeError):
    pass


def machine_label(machine: dict[str, Any]) -> str:
    return str(machine["display_name"])


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MachineError(f"cannot read machine registry {path}: {exc}") from exc
    if data.get("schema_version") != 2:
        raise MachineError("machine registry schema_version must be 2")
    machines = data.get("machines")
    if not isinstance(machines, list) or not machines:
        raise MachineError("machine registry has no machines")
    seen: set[str] = set()
    for machine in machines:
        required = {"id", "display_name", "enabled", "transport", "home"}
        missing = sorted(required - set(machine))
        if missing:
            raise MachineError(
                f"machine {machine.get('id', '<unknown>')} missing: {', '.join(missing)}"
            )
        machine_id = machine["id"]
        if not isinstance(machine_id, str) or not machine_id or machine_id in seen:
            raise MachineError(f"invalid or duplicate machine id: {machine_id!r}")
        seen.add(machine_id)
        if machine["transport"] not in {"local", "ssh"}:
            raise MachineError(f"unsupported transport for {machine_id}")
        if machine["transport"] == "ssh" and not machine.get("ssh_alias"):
            raise MachineError(f"ssh_alias missing for {machine_id}")
        home = str(machine["home"])
        if not PurePosixPath(home).is_absolute() or any(char.isspace() for char in home):
            raise MachineError(f"unsafe home path for {machine_id}")
        validate_vnc(machine)
    return data


def validate_vnc(machine: dict[str, Any]) -> None:
    vnc = machine.get("vnc")
    if vnc is None:
        return
    kind = vnc.get("kind")
    if kind == "native-url":
        if not str(vnc.get("url", "")).startswith("vnc://"):
            raise MachineError(f"invalid native VNC URL for {machine['id']}")
        return
    if kind != "ssh-novnc":
        raise MachineError(f"unsupported VNC kind for {machine['id']}")
    required = {"remote_host", "remote_port", "default_local_port", "health_path", "open_path"}
    missing = sorted(required - set(vnc))
    if missing:
        raise MachineError(f"VNC for {machine['id']} missing: {', '.join(missing)}")
    for field in ("remote_port", "default_local_port"):
        value = vnc[field]
        if not isinstance(value, int) or not 1 <= value <= 65535:
            raise MachineError(f"invalid VNC {field} for {machine['id']}")


def resolve_machine(registry: dict[str, Any], requested: str, *, enabled: bool = True) -> dict[str, Any]:
    needle = requested.casefold()
    matches = [
        machine
        for machine in registry["machines"]
        if machine["id"].casefold() == needle
        or machine["display_name"].casefold() == needle
    ]
    if not matches:
        raise MachineError(f"unknown machine: {requested}")
    machine = matches[0]
    if enabled and not machine["enabled"]:
        raise MachineError(f"machine disabled: {machine['id']}")
    return machine


def ssh_base(machine: dict[str, Any]) -> list[str]:
    if machine["transport"] != "ssh":
        raise MachineError(f"machine does not use SSH transport: {machine['id']}")
    return ["ssh", "-o", "ConnectTimeout=10", str(machine["ssh_alias"])]


def probe(machine: dict[str, Any]) -> tuple[bool, str]:
    if machine["transport"] == "local":
        return True, "local"
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", str(machine["ssh_alias"]), "true"],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if result.returncode == 0:
        return True, "reachable"
    detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unreachable"
    return False, detail


def status_record(machine: dict[str, Any]) -> dict[str, Any]:
    reachable, detail = probe(machine)
    return {
        "id": machine["id"],
        "display_name": machine["display_name"],
        "enabled": machine["enabled"],
        "transport": machine["transport"],
        "reachable": reachable,
        "detail": detail,
        "vnc": machine.get("vnc", {}).get("kind"),
    }


def runtime_dir() -> Path:
    return Path(os.environ.get("VAULT_MACHINE_RUNTIME_DIR", DEFAULT_RUNTIME_DIR)).expanduser()


def runtime_paths(machine: dict[str, Any]) -> tuple[Path, Path]:
    base = runtime_dir()
    return base / f"{machine['id']}-vnc.sock", base / f"{machine['id']}-vnc.json"


def read_metadata(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def tunnel_active(machine: dict[str, Any], control: Path) -> bool:
    if not control.exists():
        return False
    result = subprocess.run(
        ["ssh", "-S", str(control), "-O", "check", str(machine["ssh_alias"])],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def choose_port(preferred: int) -> int:
    if port_available(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def wait_for_health(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    error = "no response"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return
        except (OSError, URLError) as exc:
            error = str(exc)
        time.sleep(0.25)
    raise MachineError(f"VNC tunnel health timeout: {error}")


def open_url(url: str) -> None:
    command = "open" if platform.system() == "Darwin" else "xdg-open"
    if not shutil.which(command):
        raise MachineError(f"browser opener unavailable: {command}")
    result = subprocess.run([command, url], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise MachineError(result.stderr.strip() or f"failed to open {url}")


def ensure_tunnel(machine: dict[str, Any], requested_port: int | None) -> tuple[int, str, bool]:
    vnc = machine["vnc"]
    control, metadata_path = runtime_paths(machine)
    metadata = read_metadata(metadata_path)
    if metadata and tunnel_active(machine, control):
        active_port = int(metadata["local_port"])
        if requested_port is not None and requested_port != active_port:
            raise MachineError(
                f"VNC tunnel already uses local port {active_port}; stop it before choosing {requested_port}"
            )
        return active_port, str(metadata["url"]), True

    base = runtime_dir()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        control.unlink()
    except FileNotFoundError:
        pass
    try:
        metadata_path.unlink()
    except FileNotFoundError:
        pass

    preferred = requested_port or int(vnc["default_local_port"])
    if requested_port is not None and not port_available(requested_port):
        raise MachineError(f"requested local port occupied: {requested_port}")
    local_port = requested_port or choose_port(preferred)
    forward = f"127.0.0.1:{local_port}:{vnc['remote_host']}:{vnc['remote_port']}"
    result = subprocess.run(
        [
            "ssh", "-M", "-S", str(control), "-fNT",
            "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=10",
            "-L", forward, str(machine["ssh_alias"]),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    if result.returncode != 0:
        raise MachineError(result.stderr.strip() or "failed to create VNC tunnel")
    health_url = f"http://127.0.0.1:{local_port}{vnc['health_path']}"
    url = f"http://127.0.0.1:{local_port}{vnc['open_path']}"
    try:
        wait_for_health(health_url)
    except Exception:
        subprocess.run(
            ["ssh", "-S", str(control), "-O", "exit", str(machine["ssh_alias"])],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        raise
    metadata_path.write_text(
        json.dumps(
            {"machine_id": machine["id"], "local_port": local_port, "url": url},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    metadata_path.chmod(0o600)
    return local_port, url, False


def stop_tunnel(machine: dict[str, Any]) -> bool:
    control, metadata_path = runtime_paths(machine)
    active = tunnel_active(machine, control)
    if active:
        result = subprocess.run(
            ["ssh", "-S", str(control), "-O", "exit", str(machine["ssh_alias"])],
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if result.returncode != 0:
            raise MachineError(result.stderr.strip() or "failed to stop VNC tunnel")
    for path in (metadata_path, control):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return active


def command_list(args: argparse.Namespace, registry: dict[str, Any]) -> int:
    records = [
        {
            "id": machine["id"],
            "display_name": machine["display_name"],
            "enabled": machine["enabled"],
            "transport": machine["transport"],
            "ssh_alias": machine.get("ssh_alias"),
            "vnc": machine.get("vnc", {}).get("kind"),
        }
        for machine in registry["machines"]
    ]
    if args.json:
        print(json.dumps(records, indent=2))
        return 0
    for record in records:
        state = "enabled" if record["enabled"] else "disabled"
        access = record["ssh_alias"] or "local"
        print(f"{record['id']:<12} {record['display_name']:<14} {state:<8} {access:<12} vnc={record['vnc'] or '-'}")
    return 0


def command_status(args: argparse.Namespace, registry: dict[str, Any]) -> int:
    machines = (
        [resolve_machine(registry, args.name, enabled=False)]
        if args.name
        else registry["machines"]
    )
    records = [status_record(machine) for machine in machines]
    if args.json:
        print(json.dumps(records[0] if args.name else records, indent=2))
    else:
        for record in records:
            state = "reachable" if record["reachable"] else "unreachable"
            enabled = "enabled" if record["enabled"] else "disabled"
            print(f"{record['id']}: {state}, {enabled}, {record['detail']}")
    return 0 if all(record["reachable"] for record in records if record["enabled"]) else 1


def command_ssh(args: argparse.Namespace, registry: dict[str, Any]) -> int:
    machine = resolve_machine(registry, args.name)
    command = list(args.remote_command)
    argv = ssh_base(machine)
    if command:
        argv.extend(["--", *command])
    return subprocess.run(argv).returncode


def command_vnc(args: argparse.Namespace, registry: dict[str, Any]) -> int:
    machine = resolve_machine(registry, args.name)
    vnc = machine.get("vnc")
    if not vnc:
        raise MachineError(f"VNC not configured for machine: {machine['id']}")
    if vnc["kind"] == "native-url":
        if args.stop:
            print(f"{machine['id']}: native VNC has no managed tunnel")
            return 0
        if args.status:
            print(f"{machine['id']}: native VNC available at {vnc['url']}")
            return 0
        if not args.no_open:
            open_url(vnc["url"])
        print(vnc["url"])
        return 0

    control, metadata_path = runtime_paths(machine)
    if args.stop:
        was_active = stop_tunnel(machine)
        print(f"{machine['id']}: {'stopped' if was_active else 'inactive'}")
        return 0
    if args.status:
        metadata = read_metadata(metadata_path)
        if metadata and tunnel_active(machine, control):
            print(f"{machine['id']}: active {metadata['url']}")
            return 0
        print(f"{machine['id']}: inactive")
        return 1
    local_port, url, reused = ensure_tunnel(machine, args.local_port)
    if not args.no_open:
        open_url(url)
    print(f"{machine['id']}: {'reused' if reused else 'started'} local port {local_port}")
    print(url)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY, help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="action", required=True)

    list_parser = subparsers.add_parser("list", help="list reviewed machines")
    list_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status", help="probe machine reachability")
    status_parser.add_argument("name", nargs="?")
    status_parser.add_argument("--json", action="store_true")

    ssh_parser = subparsers.add_parser("ssh", help="open SSH or forward a command")
    ssh_parser.add_argument("name")
    ssh_parser.add_argument("remote_command", nargs=argparse.REMAINDER)

    vnc_parser = subparsers.add_parser("vnc", help="open or manage VNC access")
    vnc_parser.add_argument("name")
    vnc_parser.add_argument("--no-open", action="store_true")
    vnc_parser.add_argument("--local-port", type=int)
    mode = vnc_parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--stop", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = load_registry(args.registry)
    return {
        "list": command_list,
        "status": command_status,
        "ssh": command_ssh,
        "vnc": command_vnc,
    }[args.action](args, registry)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MachineError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        raise SystemExit(2)
