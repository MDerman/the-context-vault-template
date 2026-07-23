#!/usr/bin/env python3
"""Queue committed master pushes and fast-forward registered vault workers."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import tempfile
from typing import Any

import machine as machine_registry
from script_utils import resolve_vault_root


class WorkerSyncError(RuntimeError):
    pass


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check,
    )


def git_output(root: Path, *args: str) -> str:
    return git(root, *args).stdout.strip()


def state_dir(root: Path) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    key = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return base / "vault-worker-sync" / key


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def machine_identity(root: Path, registry: dict[str, Any]) -> dict[str, Any]:
    result = git(root, "config", "--get", "vault.machine-id", check=False)
    machine_id = result.stdout.strip()
    if not machine_id:
        raise WorkerSyncError(
            "clone identity missing; run `vault machine identify ID --apply`"
        )
    return machine_registry.resolve_machine(registry, machine_id, enabled=False)


def sync_skills(root: Path) -> None:
    deps_script = root / "_system/commands/deps.py"
    if deps_script.is_file():
        subprocess.run(
            [sys.executable, str(deps_script), "--root", str(root), "project-auto-skills", "--apply"],
            cwd=root, check=True,
        )
    script = root / "_system/agents/sync_skills.py"
    subprocess.run(
        [sys.executable, str(script), "sync", "--root", str(root), "--apply"],
        cwd=root, check=True,
    )


def clean_tree(root: Path) -> bool:
    return not git_output(root, "status", "--porcelain", "--untracked-files=normal")


def ensure_master(root: Path, branch: str = "master") -> str:
    current = git_output(root, "branch", "--show-current")
    if current != branch:
        raise WorkerSyncError(f"expected {branch}; current branch is {current or 'detached HEAD'}")
    return git_output(root, "rev-parse", "HEAD")


def apply_local(root: Path, expected_head: str | None = None) -> str:
    registry = machine_registry.load_registry(root / "_system/config/code-folder-and-computer-topology/private/machines.json")
    local_machine = machine_identity(root, registry)
    sync_config = local_machine.get("vault_sync", {})
    if local_machine.get("role") == "worker" and (
        not local_machine.get("enabled") or not sync_config.get("enabled")
    ):
        raise WorkerSyncError(f"worker vault sync disabled: {local_machine['id']}")
    if not clean_tree(root):
        raise WorkerSyncError("worker working tree is dirty; skipped")
    ensure_master(root)
    git(root, "fetch", "origin", "--prune")
    local = git_output(root, "rev-parse", "master")
    remote = git_output(root, "rev-parse", "origin/master")
    if local != remote:
        if git(root, "merge-base", "--is-ancestor", local, remote, check=False).returncode != 0:
            raise WorkerSyncError("worker master diverged from origin/master; skipped")
        git(root, "merge", "--ff-only", "origin/master")
    head = git_output(root, "rev-parse", "HEAD")
    if expected_head and head != expected_head:
        raise WorkerSyncError(f"worker stopped at {head[:12]}, expected {expected_head[:12]}")
    sync_skills(root)
    print(f"worker current at {head[:12]}")
    return head


def fan_out(root: Path, registry: dict[str, Any], head: str) -> None:
    for worker in registry["machines"]:
        config = worker.get("vault_sync", {})
        if worker.get("role") != "worker" or not worker.get("enabled") or not config.get("enabled"):
            continue
        repo_path = str(config["repo_path"])
        script = f"{repo_path}/_system/commands/post_commit_worker_sync.py"
        remote_command = " ".join(
            shlex.quote(value)
            for value in ["python3", script, "--root", repo_path, "apply-local", "--expected-head", head]
        )
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", str(worker["ssh_alias"]), remote_command],
            cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            print(f"{worker['id']}: {result.stdout.strip() or 'updated'}")
        else:
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unreachable"
            print(f"{worker['id']}: skipped ({detail})", file=sys.stderr)


def process_commit(root: Path, registry: dict[str, Any], queued_head: str) -> None:
    machine = machine_identity(root, registry)
    if not machine.get("enabled") or not machine.get("vault_sync", {}).get("enabled"):
        raise WorkerSyncError(f"vault sync disabled: {machine['id']}")
    head = ensure_master(root)
    if not git(root, "merge-base", "--is-ancestor", queued_head, head, check=False).returncode == 0:
        raise WorkerSyncError("queued commit is not on current master")
    sync_skills(root)
    if machine["role"] == "worker" and not clean_tree(root):
        raise WorkerSyncError("worker working tree changed or is dirty; push skipped")
    result = git(root, "push", "origin", "master", check=False)
    if result.returncode != 0:
        raise WorkerSyncError(result.stderr.strip() or "push rejected")
    print(f"pushed master at {head[:12]}")
    if machine["role"] == "primary":
        fan_out(root, registry, head)


def enqueue(root: Path) -> None:
    ensure_master(root)
    head = git_output(root, "rev-parse", "HEAD")
    state = state_dir(root)
    atomic_write(state / "pending", head + "\n")
    log = state / "sync.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as handle:
        spawn_background(root, handle)
    print(f"queued {head[:12]}")


def spawn_background(root: Path, log_handle: Any) -> None:
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--root", str(root), "run"],
        cwd=root, stdin=subprocess.DEVNULL, stdout=log_handle, stderr=subprocess.STDOUT,
        start_new_session=True, close_fds=True,
    )


def run_queue(root: Path) -> None:
    state = state_dir(root)
    state.mkdir(parents=True, exist_ok=True)
    with (state / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        registry = machine_registry.load_registry(root / "_system/config/code-folder-and-computer-topology/private/machines.json")
        while (state / "pending").exists():
            queued = (state / "pending").read_text(encoding="utf-8").strip()
            try:
                process_commit(root, registry, queued)
            except (WorkerSyncError, subprocess.CalledProcessError) as exc:
                detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
                atomic_write(state / "last-error", detail + "\n")
                print(f"worker sync failed: {detail}", file=sys.stderr)
                return
            current = (state / "pending").read_text(encoding="utf-8").strip()
            if current == queued:
                (state / "pending").unlink()
            (state / "last-error").unlink(missing_ok=True)


def install_hooks(root: Path, apply: bool) -> None:
    command = ["git", "config", "--local", "core.hooksPath", ".githooks"]
    if not apply:
        print("DRY RUN: " + " ".join(command))
        return
    for name in ("post-commit", "post-checkout", "post-merge", "post-rewrite", "pre-push"):
        path = root / ".githooks" / name
        if not path.is_file():
            raise WorkerSyncError(f"versioned hook missing: {path}")
        path.chmod(0o755)
    subprocess.run(command, cwd=root, check=True)
    print("configured core.hooksPath=.githooks")


def linux_units(root: Path) -> tuple[str, str]:
    script = root / "_system/commands/post_commit_worker_sync.py"
    service = f"""[Unit]
Description=Fast-forward vault worker and sync skills
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={shlex.quote(sys.executable)} {shlex.quote(str(script))} --root {shlex.quote(str(root))} apply-local
"""
    timer = """[Unit]
Description=Poll canonical vault branch every five minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
"""
    return service, timer


def install_service(root: Path, platform_name: str, apply: bool) -> None:
    if platform_name == "linux":
        base = Path.home() / ".config/systemd/user"
        service_path = base / "vault-worker-sync.service"
        timer_path = base / "vault-worker-sync.timer"
        service, timer = linux_units(root)
        if not apply:
            print(f"DRY RUN: write {service_path} and {timer_path}; enable timer")
            return
        base.mkdir(parents=True, exist_ok=True)
        service_path.write_text(service, encoding="utf-8")
        timer_path.write_text(timer, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "vault-worker-sync.timer"], check=True)
        subprocess.run(["systemctl", "--user", "start", "vault-worker-sync.service"], check=True)
        print("installed systemd user worker service and timer")
        return
    if platform_name != "macos":
        raise WorkerSyncError(f"unsupported service platform: {platform_name}")
    label = "com.vault.worker-sync"
    target = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
    payload = {
        "Label": label,
        "ProgramArguments": [sys.executable, str(root / "_system/commands/post_commit_worker_sync.py"), "--root", str(root), "apply-local"],
        "RunAtLoad": True,
        "StartInterval": 300,
        "StandardOutPath": str(state_dir(root) / "launchd.log"),
        "StandardErrorPath": str(state_dir(root) / "launchd.log"),
    }
    if not apply:
        print(f"DRY RUN: write and bootstrap {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    state_dir(root).mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps(payload))
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(target)], check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    print("installed LaunchAgent worker refresh")


def bootstrap_worker(root: Path, registry: dict[str, Any], name: str, apply: bool) -> None:
    worker = machine_registry.resolve_machine(registry, name)
    config = worker.get("vault_sync", {})
    if worker.get("role") != "worker" or not config.get("enabled"):
        raise WorkerSyncError(f"worker vault sync disabled: {worker['id']}")
    repo = str(config["repo_path"])
    remote = git_output(root, "remote", "get-url", "origin")
    sparse = " ".join(shlex.quote(str(path)) for path in config["sparse_paths"])
    script = f"""set -eu
repo={shlex.quote(repo)}
if [ -e \"$repo\" ]; then
  git -C \"$repo\" rev-parse --git-dir >/dev/null 2>&1 || {{ echo \"non-Git target exists: $repo\" >&2; exit 2; }}
  echo \"resuming existing vault clone: $repo\"
else
  mkdir -p \"$(dirname \"$repo\")\"
  GIT_LFS_SKIP_SMUDGE=1 GIT_TERMINAL_PROMPT=0 git clone --depth=100 --filter=blob:none --sparse --branch master {shlex.quote(remote)} \"$repo\"
fi
cd \"$repo\"
git lfs install --local --skip-smudge --skip-repo
GIT_LFS_SKIP_SMUDGE=1 git sparse-checkout set --cone {sparse}
git config --local vault.machine-id {shlex.quote(str(worker['id']))}
git config --local vault.media-mode pointer-only
mkdir -p \"$HOME/.local/bin\"
ln -sfn \"$repo/_system/commands/vault.py\" \"$HOME/.local/bin/vault\"
python3 \"$repo/_system/commands/post_commit_worker_sync.py\" --root \"$repo\" install-hooks --apply
python3 \"$repo/_system/commands/deps.py\" --root \"$repo\" project-auto-skills --apply
python3 \"$repo/_system/agents/sync_skills.py\" sync --root \"$repo\" --home \"$HOME\" --apply
python3 \"$repo/_system/commands/post_commit_worker_sync.py\" --root \"$repo\" install-service --platform {shlex.quote(str(worker['platform']))} --apply
"""
    if not apply:
        print(f"DRY RUN: bootstrap {worker['id']} at {repo} through {worker['ssh_alias']}")
        return
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", str(worker["ssh_alias"]), "bash", "-s"],
        input=script, text=True,
    )
    if result.returncode != 0:
        raise WorkerSyncError(f"bootstrap failed on {worker['id']}")


def show_status(root: Path) -> None:
    state = state_dir(root)
    payload = {
        "machine_id": git(root, "config", "--get", "vault.machine-id", check=False).stdout.strip() or None,
        "head": git(root, "rev-parse", "HEAD", check=False).stdout.strip() or None,
        "pending": (state / "pending").read_text().strip() if (state / "pending").exists() else None,
        "last_error": (state / "last-error").read_text().strip() if (state / "last-error").exists() else None,
        "hooks_path": git(root, "config", "--get", "core.hooksPath", check=False).stdout.strip() or None,
    }
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("enqueue")
    sub.add_parser("run")
    local = sub.add_parser("apply-local")
    local.add_argument("--expected-head")
    sub.add_parser("sync-skills")
    hooks = sub.add_parser("install-hooks")
    hooks.add_argument("--apply", action="store_true")
    service = sub.add_parser("install-service")
    service.add_argument("--platform", choices=("linux", "macos"), required=True)
    service.add_argument("--apply", action="store_true")
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("name")
    bootstrap.add_argument("--apply", action="store_true")
    sub.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    try:
        if args.command == "enqueue": enqueue(root)
        elif args.command == "run": run_queue(root)
        elif args.command == "apply-local": apply_local(root, args.expected_head)
        elif args.command == "sync-skills": sync_skills(root)
        elif args.command == "install-hooks": install_hooks(root, args.apply)
        elif args.command == "install-service": install_service(root, args.platform, args.apply)
        elif args.command == "bootstrap":
            bootstrap_worker(root, machine_registry.load_registry(root / "_system/config/code-folder-and-computer-topology/private/machines.json"), args.name, args.apply)
        elif args.command == "status": show_status(root)
        return 0
    except (WorkerSyncError, machine_registry.MachineError, OSError, subprocess.SubprocessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        print(f"Worker sync failed: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
