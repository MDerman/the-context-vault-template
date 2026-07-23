#!/usr/bin/env python3
"""Operate reviewed development machines from one private vault registry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
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
DEFAULT_REGISTRY = ROOT / CONFIG_DIR / "code-folder-and-computer-topology/private/machines.json"
DEFAULT_RUNTIME_DIR = Path.home() / ".cache/vault-machine"
MACHINE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class MachineError(RuntimeError):
    pass


def machine_label(machine: dict[str, Any]) -> str:
    return str(machine["display_name"])


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MachineError(
            f"machine registry missing: {path}; initialize with `vault machine init --id ID "
            "--display-name NAME --platform macos|linux --apply`"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MachineError(f"cannot read machine registry {path}: {exc}") from exc
    validate_registry(data)
    return data


def validate_registry(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 3:
        raise MachineError("machine registry schema_version must be 3; run the documented registry migration")
    machines = data.get("machines")
    if not isinstance(machines, list) or not machines:
        raise MachineError("machine registry has no machines")
    primary_machine_id = data.get("primary_machine_id")
    if not isinstance(primary_machine_id, str) or not primary_machine_id:
        raise MachineError("machine registry primary_machine_id is missing")
    seen: set[str] = set()
    for machine in machines:
        required = {"id", "display_name", "enabled", "transport", "home", "role", "platform"}
        missing = sorted(required - set(machine))
        if missing:
            raise MachineError(
                f"machine {machine.get('id', '<unknown>')} missing: {', '.join(missing)}"
            )
        machine_id = machine["id"]
        if not isinstance(machine_id, str) or not MACHINE_ID_RE.fullmatch(machine_id) or machine_id in seen:
            raise MachineError(f"invalid or duplicate machine id: {machine_id!r}")
        seen.add(machine_id)
        if machine["role"] not in {"primary", "worker"}:
            raise MachineError(f"unsupported role for {machine_id}")
        if machine["platform"] not in {"macos", "linux"}:
            raise MachineError(f"unsupported platform for {machine_id}")
        if machine["transport"] not in {"local", "ssh"}:
            raise MachineError(f"unsupported transport for {machine_id}")
        if machine["transport"] == "ssh" and not machine.get("ssh_alias"):
            raise MachineError(f"ssh_alias missing for {machine_id}")
        home = str(machine["home"])
        if not PurePosixPath(home).is_absolute() or any(char.isspace() for char in home):
            raise MachineError(f"unsafe home path for {machine_id}")
        validate_vault_sync(machine)
        validate_vnc(machine)
    if primary_machine_id not in seen:
        raise MachineError("primary_machine_id does not match a registered machine")
    primary = next(machine for machine in machines if machine["id"] == primary_machine_id)
    if primary["role"] != "primary":
        raise MachineError("primary_machine_id must reference a primary machine")
    if sum(machine["role"] == "primary" for machine in machines) != 1:
        raise MachineError("machine registry must contain exactly one primary machine")


def validate_vault_sync(machine: dict[str, Any]) -> None:
    config = machine.get("vault_sync")
    if config is None:
        return
    if not isinstance(config, dict) or not isinstance(config.get("enabled"), bool):
        raise MachineError(f"invalid vault_sync for {machine['id']}")
    checkout = config.get("checkout", "full" if machine["role"] == "primary" else "sparse")
    if checkout not in {"full", "sparse"}:
        raise MachineError(f"unsupported vault checkout for {machine['id']}")
    paths = config.get("sparse_paths", [])
    if checkout == "sparse" and (not isinstance(paths, list) or not paths):
        raise MachineError(f"sparse vault_sync requires sparse_paths for {machine['id']}")
    repo_path = config.get("repo_path")
    if machine["role"] == "worker" and config.get("enabled"):
        if not isinstance(repo_path, str) or not PurePosixPath(repo_path).is_absolute():
            raise MachineError(f"enabled worker vault_sync requires absolute repo_path for {machine['id']}")


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
        "role": machine["role"],
        "platform": machine["platform"],
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
            "role": machine["role"],
            "platform": machine["platform"],
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
        print(
            f"{record['id']:<12} {record['display_name']:<14} {record['role']:<7} "
            f"{record['platform']:<6} {state:<8} {access:<12} vnc={record['vnc'] or '-'}"
        )
    return 0


def write_registry(path: Path, payload: dict[str, Any], apply: bool) -> int:
    rendered = json.dumps(payload, indent=2) + "\n"
    if not apply:
        print(f"DRY RUN: write {path}")
        print(rendered, end="")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(f"wrote {path}")
    return 0


def command_init(args: argparse.Namespace) -> int:
    if args.registry.exists():
        raise MachineError(f"machine registry already exists: {args.registry}")
    payload = {
        "schema_version": 3,
        "primary_machine_id": args.id,
        "vault_sync": {
            "remote": "origin",
            "branch": "master",
            "default_sparse_paths": ["_system", ".githooks"],
            "worker_poll_seconds": 300,
        },
        "machines": [
            {
                "id": args.id,
                "display_name": args.display_name,
                "enabled": True,
                "role": "primary",
                "platform": args.platform,
                "transport": "local",
                "home": str(Path.home()),
                "global_agents_eligible": True,
                "vault_sync": {"enabled": True, "checkout": "full", "required": True},
            }
        ],
    }
    return write_registry(args.registry, payload, args.apply)


def command_register_worker(args: argparse.Namespace, registry: dict[str, Any]) -> int:
    if any(machine["id"] == args.id for machine in registry["machines"]):
        raise MachineError(f"machine already registered: {args.id}")
    registry["machines"].append(
        {
            "id": args.id,
            "display_name": args.display_name,
            "enabled": True,
            "role": "worker",
            "platform": args.platform,
            "transport": "ssh",
            "ssh_alias": args.ssh_alias,
            "home": args.home,
            "global_agents_eligible": False,
            "vault_sync": {
                "enabled": True,
                "checkout": "sparse",
                "repo_path": args.repo_path,
                "sparse_paths": ["_system", ".githooks"],
                "required": False,
            },
        }
    )
    payload = json.loads(json.dumps(registry))
    validate_registry(payload)
    return write_registry(args.registry, payload, args.apply)


def command_identify(args: argparse.Namespace, registry: dict[str, Any]) -> int:
    machine = resolve_machine(registry, args.name, enabled=False)
    root = Path(args.root).expanduser().resolve()
    command = ["git", "config", "--local", "vault.machine-id", str(machine["id"])]
    if not args.apply:
        print("DRY RUN: " + " ".join(command))
        return 0
    subprocess.run(command, cwd=root, check=True)
    print(f"identified this clone as {machine['id']}")
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

    init_parser = subparsers.add_parser("init", help="create a private registry with this machine as primary")
    init_parser.add_argument("--id", required=True)
    init_parser.add_argument("--display-name", required=True)
    init_parser.add_argument("--platform", choices=("macos", "linux"), required=True)
    init_parser.add_argument("--apply", action="store_true")

    worker_parser = subparsers.add_parser("register-worker", help="register an SSH worker")
    worker_parser.add_argument("--id", required=True)
    worker_parser.add_argument("--display-name", required=True)
    worker_parser.add_argument("--platform", choices=("macos", "linux"), required=True)
    worker_parser.add_argument("--ssh-alias", required=True)
    worker_parser.add_argument("--home", required=True)
    worker_parser.add_argument("--repo-path", required=True)
    worker_parser.add_argument("--apply", action="store_true")

    identify_parser = subparsers.add_parser("identify", help="store clone-local machine identity")
    identify_parser.add_argument("name")
    identify_parser.add_argument("--root", default=str(ROOT))
    identify_parser.add_argument("--apply", action="store_true")

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
    if args.action == "init":
        return command_init(args)
    registry = load_registry(args.registry)
    if args.action == "register-worker":
        return command_register_worker(args, registry)
    if args.action == "identify":
        return command_identify(args, registry)
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
