#!/usr/bin/env python3
"""Operate the registered Vault writer lease and iCloud handoff on local Macs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

from vault_layout import VAULT_ROOT


ROOT = VAULT_ROOT
REGISTRY = ROOT / "_system/agents/_package/instance/fleet/machines.json"
HELPER = (
    ROOT
    / "_system/agents/skills/auto/_infrastructure/infra-onboard-machine/"
    "scripts/remote_vault_access.py"
)
STATE = Path.home() / ".local/state/vault-remote"
ACTIVE = STATE / "active-session.json"
HEARTBEAT = STATE / "local-heartbeat.json"


def load_helper() -> Any:
    specification = importlib.util.spec_from_file_location("remote_vault_access", HELPER)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load remote Vault helper: {HELPER}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ACCESS = load_helper()


def current_machine_id() -> str:
    identity = Path.home() / ".config/vault/machine-id"
    if identity.is_file():
        value = identity.read_text(encoding="utf-8").strip()
        if value:
            return value
    result = subprocess.run(
        ["git", "-C", str(ROOT), "config", "--get", "vault.machine-id"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.stdout.strip():
        return result.stdout.strip()
    raise ACCESS.AccessError("machine identity is unresolved")


def topology() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    registry, machines = ACCESS.load_registry(REGISTRY)
    machine_id = current_machine_id()
    machine = machines.get(machine_id)
    if not machine or not machine.get("enabled") or not machine.get("vault", {}).get("enabled"):
        raise ACCESS.AccessError(f"machine is not an enabled Vault participant: {machine_id}")
    return registry, machines, machine


def authoritative_host(
    registry: dict[str, Any], machines: dict[str, dict[str, Any]], machine: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    remote = machine.get("vault", {}).get("remote_access")
    if isinstance(remote, dict) and remote.get("host_enabled") is True:
        return "local", machine, ACCESS.generated_host_config(registry, machines, machine)
    sources = {
        str(candidate.get("vault", {}).get("remote_access", {}).get("source_machine_id"))
        for candidate in machines.values()
        if candidate.get("enabled") and candidate.get("vault", {}).get("checkout_mode") == "remote-sshfs"
    }
    sources.discard("None")
    if len(sources) != 1:
        raise ACCESS.AccessError("registry does not identify one authoritative remote Vault host")
    source = machines[next(iter(sources))]
    source_helper = str(Path(str(source["home"])) / ".local/share/vault-access/remote_vault_access.py")
    channel = {
        "source_alias": source["ssh_alias"],
        "source_helper": source_helper,
        "source_machine_id": source["id"],
    }
    return "ssh", source, channel


def call_host(kind: str, host: dict[str, Any], channel: dict[str, Any], argv: list[str], timeout: int = 720) -> dict[str, Any]:
    if kind == "ssh":
        return ACCESS.host_call(channel, argv, timeout=timeout)
    config = ACCESS.host_config(Path.home() / ".config/vault/remote-access-host.json")
    action = argv[0]
    values = argv[1:]

    def option(name: str, default: str | None = None) -> str | None:
        try:
            return values[values.index(name) + 1]
        except (ValueError, IndexError):
            return default

    if action == "status":
        return ACCESS.host_status(config)
    if action == "begin":
        return ACCESS.host_begin(
            config,
            str(option("--client")),
            str(option("--session")),
            int(option("--owner-pid") or 0),
        )
    if action == "heartbeat":
        paths = ACCESS.host_paths(config)
        lease = ACCESS.require_lease(paths, str(option("--client")), str(option("--session")))
        return {"ok": True, "lease": ACCESS.update_lease(paths, lease)}
    if action == "finish":
        return ACCESS.host_finish(
            config,
            str(option("--client")),
            str(option("--session")),
            int(option("--timeout", "300") or 300),
        )
    if action == "recover":
        return ACCESS.recover_lease(config, str(option("--reason")))
    raise ACCESS.AccessError(f"unsupported local host action: {action}")


def read_active() -> dict[str, Any] | None:
    return ACCESS.read_optional_json(ACTIVE)


def start_heartbeat(session_id: str) -> int:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = (STATE / "local-heartbeat.log").open("ab")
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "_heartbeat", session_id],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
        close_fds=True,
    )
    ACCESS.atomic_write(HEARTBEAT, {"session_id": session_id, "pid": process.pid})
    return process.pid


def stop_heartbeat(session_id: str) -> None:
    state = ACCESS.read_optional_json(HEARTBEAT)
    if state and state.get("session_id") == session_id and isinstance(state.get("pid"), int):
        try:
            os.kill(int(state["pid"]), signal.SIGTERM)
        except ProcessLookupError:
            pass
    HEARTBEAT.unlink(missing_ok=True)


def heartbeat_loop(session_id: str) -> int:
    registry, machines, machine = topology()
    kind, host, channel = authoritative_host(registry, machines, machine)
    while True:
        active = read_active()
        if not active or active.get("session_id") != session_id:
            return 0
        try:
            call_host(
                kind,
                host,
                channel,
                ["heartbeat", "--client", machine["id"], "--session", session_id],
                timeout=60,
            )
        except Exception:
            pass
        time.sleep(ACCESS.HEARTBEAT_SECONDS)


def status() -> dict[str, Any]:
    registry, machines, machine = topology()
    mode = machine["vault"]["checkout_mode"]
    if mode == "remote-sshfs":
        return ACCESS.client_status(ACCESS.client_config())
    kind, host, channel = authoritative_host(registry, machines, machine)
    host_state = call_host(kind, host, channel, ["status"])
    latest = host_state.get("latest_receipt") or {}
    return {
        "ok": bool(host_state.get("icloud", {}).get("access_ready")),
        "machine_id": machine["id"],
        "mode": mode,
        "mount": {
            "mounted": True,
            "healthy": ROOT.is_dir() and (ROOT / "AGENTS.md").is_file(),
            "read_write": os.access(ROOT, os.R_OK | os.W_OK | os.X_OK),
            "target": str(ROOT),
            "source": "local-icloud",
        },
        "host": host_state,
        "active_session": read_active(),
        "git_owner": registry["vault_git"].get("owner_machine_id") == machine["id"],
        "states": latest.get("states", {}),
    }


def begin(task_id: str | None) -> dict[str, Any]:
    registry, machines, machine = topology()
    if machine["vault"]["checkout_mode"] == "remote-sshfs":
        return ACCESS.access_begin(ACCESS.client_config(), task_id)
    if read_active():
        raise ACCESS.AccessError("this machine already has an active Vault session")
    kind, host, channel = authoritative_host(registry, machines, machine)
    suffix = ACCESS.re.sub(r"[^a-z0-9-]+", "-", (task_id or "session").casefold()).strip("-")[:24] or "session"
    session_id = f"{suffix}-{ACCESS.utc_now().strftime('%Y%m%d%H%M%S')}-{ACCESS.uuid.uuid4().hex[:8]}"
    result = call_host(
        kind,
        host,
        channel,
        ["begin", "--client", machine["id"], "--session", session_id, "--owner-pid", str(os.getppid())],
    )
    active = {"schema_version": 1, "session_id": session_id, "task_id": task_id, "started_at": ACCESS.utc_stamp()}
    ACCESS.atomic_write(ACTIVE, active)
    heartbeat_pid = start_heartbeat(session_id)
    return {"ok": True, "session": active, "heartbeat_pid": heartbeat_pid, "host": result}


def finish(timeout: int) -> dict[str, Any]:
    registry, machines, machine = topology()
    if machine["vault"]["checkout_mode"] == "remote-sshfs":
        return ACCESS.access_finish(ACCESS.client_config(), timeout)
    active = read_active()
    if not active or not isinstance(active.get("session_id"), str):
        raise ACCESS.AccessError("there is no active Vault session to finish")
    session_id = active["session_id"]
    kind, host, channel = authoritative_host(registry, machines, machine)
    stop_heartbeat(session_id)
    try:
        result = call_host(
            kind,
            host,
            channel,
            ["finish", "--client", machine["id"], "--session", session_id, "--timeout", str(timeout)],
            timeout=timeout * 2 + 120,
        )
    except Exception:
        start_heartbeat(session_id)
        raise
    ACTIVE.unlink(missing_ok=True)
    ACCESS.atomic_write(STATE / "last-finished-session.json", result)
    return result


def hash_file(path: Path) -> str:
    digest = ACCESS.hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def receipt_path(session_id: str) -> Path:
    if not ACCESS.SESSION_RE.fullmatch(session_id):
        raise ACCESS.AccessError("unsafe receipt session ID")
    return ROOT / "_system/local/state/remote-vault-receipts" / f"{session_id}.json"


def observe_receipt(session_id: str, timeout: int) -> dict[str, Any]:
    registry, _, machine = topology()
    if registry["vault_git"].get("owner_machine_id") != machine["id"]:
        raise ACCESS.AccessError("only the registered Vault Git owner may observe receipts")
    path = receipt_path(session_id)
    deadline = time.monotonic() + timeout
    while not path.is_file() and time.monotonic() < deadline:
        time.sleep(2)
    receipt = ACCESS.read_json(path, "remote Vault receipt")
    if receipt.get("session_id") != session_id or not receipt.get("states", {}).get("icloud_uploaded"):
        raise ACCESS.AccessError("receipt identity or iCloud-uploaded state is invalid")
    failures: list[str] = []
    for entry in receipt.get("files", []):
        target = ROOT / str(entry.get("path"))
        if not target.is_file() or target.is_symlink() or hash_file(target) != entry.get("sha256"):
            failures.append(str(entry.get("path")))
    for entry in receipt.get("symlinks", []):
        target = ROOT / str(entry.get("path"))
        if not target.is_symlink() or os.readlink(target) != entry.get("target"):
            failures.append(str(entry.get("path")))
    for relative in receipt.get("deleted", []):
        if (ROOT / str(relative)).exists() or (ROOT / str(relative)).is_symlink():
            failures.append(str(relative))
    if failures:
        raise ACCESS.AccessError(f"receipt verification failed for {len(failures)} path(s): {failures[:5]}")
    health = ACCESS.icloud_health(ROOT, [path])
    if not health["healthy"]:
        raise ACCESS.AccessError(f"Mattbook iCloud state is not healthy: {health['state']}")
    receipt["states"]["peer_observed"] = True
    receipt["peer_observed_at"] = ACCESS.utc_stamp()
    receipt["peer_machine_id"] = machine["id"]
    ACCESS.atomic_write(path, receipt)
    return {"ok": True, "peer_observed": True, "receipt": receipt, "icloud": health}


def acknowledge_git(session_id: str, commit: str) -> dict[str, Any]:
    registry, _, machine = topology()
    if registry["vault_git"].get("owner_machine_id") != machine["id"]:
        raise ACCESS.AccessError("only the registered Vault Git owner may acknowledge a push")
    path = receipt_path(session_id)
    receipt = ACCESS.read_json(path, "remote Vault receipt")
    if not receipt.get("states", {}).get("peer_observed"):
        raise ACCESS.AccessError("receipt must be peer-observed before Git acknowledgement")
    branch = str(registry["vault_git"]["branch"])
    remote = str(registry["vault_git"]["remote"])
    verify = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, f"{remote}/{branch}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if verify.returncode != 0:
        raise ACCESS.AccessError(f"commit is not present on {remote}/{branch}: {commit}")
    receipt["states"]["git_pushed"] = True
    receipt["git_pushed_at"] = ACCESS.utc_stamp()
    receipt["git_commit"] = commit
    ACCESS.atomic_write(path, receipt)
    return {"ok": True, "git_pushed": True, "receipt": receipt}


def recover(reason: str) -> dict[str, Any]:
    registry, machines, machine = topology()
    if machine["vault"]["checkout_mode"] == "remote-sshfs":
        return ACCESS.host_call(ACCESS.client_config(), ["recover", "--reason", reason])
    kind, host, channel = authoritative_host(registry, machines, machine)
    return call_host(kind, host, channel, ["recover", "--reason", reason])


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "_heartbeat":
        return heartbeat_loop(arguments[1])
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("mount")
    sub.add_parser("unmount")
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    wait = sub.add_parser("wait")
    group = wait.add_mutually_exclusive_group(required=True)
    group.add_argument("--download", action="store_true")
    group.add_argument("--upload", action="store_true")
    group.add_argument("--receipt")
    wait.add_argument("--timeout", type=int, default=300)
    begin_parser = sub.add_parser("begin")
    begin_parser.add_argument("--task-id")
    finish_parser = sub.add_parser("finish")
    finish_parser.add_argument("--timeout", type=int, default=300)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    recover_parser = sub.add_parser("recover")
    recover_parser.add_argument("--reason", required=True)
    acknowledge = sub.add_parser("ack-git")
    acknowledge.add_argument("--receipt", required=True)
    acknowledge.add_argument("--commit", required=True)
    args = parser.parse_args(arguments)
    if args.action in {"mount", "unmount"}:
        result = {"ok": True, "detail": "local iCloud Vault is not mounted through SSHFS", "mount": status()["mount"]}
    elif args.action in {"status", "doctor"}:
        result = status()
    elif args.action == "begin":
        result = begin(args.task_id)
    elif args.action == "finish":
        result = finish(args.timeout)
    elif args.action == "wait":
        if args.receipt:
            result = observe_receipt(args.receipt, args.timeout)
        else:
            deadline = time.monotonic() + args.timeout
            result = status()
            while not result["ok"] and time.monotonic() < deadline:
                time.sleep(2)
                result = status()
            if not result["ok"]:
                raise ACCESS.AccessError(f"Vault access did not become healthy within {args.timeout}s")
    elif args.action == "recover":
        result = recover(args.reason)
    elif args.action == "ack-git":
        result = acknowledge_git(args.receipt, args.commit)
    else:
        raise ACCESS.AccessError(f"unsupported action: {args.action}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ACCESS.AccessError, OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        print(f"Vault access failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
