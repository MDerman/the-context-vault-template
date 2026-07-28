#!/usr/bin/env python3
"""Configure or repair an explicit sparse vault worker checkout."""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any

import machine as machine_registry
from script_utils import resolve_vault_root


class WorkerBootstrapError(RuntimeError):
    pass


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check,
    )


def git_output(root: Path, *args: str) -> str:
    return git(root, *args).stdout.strip()


def install_hooks(root: Path, apply: bool) -> None:
    command = ["git", "config", "--local", "core.hooksPath", ".githooks"]
    if not apply:
        print("DRY RUN: " + " ".join(command))
        return
    for name in ("post-commit", "post-checkout", "post-merge", "post-rewrite", "pre-push"):
        path = root / ".githooks" / name
        if not path.is_file():
            raise WorkerBootstrapError(f"versioned hook missing: {path}")
        path.chmod(0o755)
    subprocess.run(command, cwd=root, check=True)
    print("configured core.hooksPath=.githooks")


def bootstrap_script(worker: dict[str, Any], remote: str) -> str:
    config = worker["vault_sync"]
    repo = str(config["repo_path"])
    sparse = " ".join(shlex.quote(str(path)) for path in config["sparse_paths"])
    return f"""set -eu
repo={shlex.quote(repo)}
if [ -e "$repo" ]; then
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || {{ echo "non-Git target exists: $repo" >&2; exit 2; }}
  echo "resuming existing vault clone: $repo"
else
  mkdir -p "$(dirname "$repo")"
  GIT_LFS_SKIP_SMUDGE=1 GIT_TERMINAL_PROMPT=0 git clone --depth=100 --filter=blob:none --sparse --branch master {shlex.quote(remote)} "$repo"
fi
cd "$repo"
git lfs install --local --skip-smudge --skip-repo
GIT_LFS_SKIP_SMUDGE=1 git sparse-checkout set --cone {sparse}
git config --local vault.machine-id {shlex.quote(str(worker['id']))}
git config --local vault.media-mode pointer-only
mkdir -p "$HOME/.local/bin"
ln -sfn "$repo/_system/commands/vault.py" "$HOME/.local/bin/vault"
python3 "$repo/_system/commands/worker_bootstrap.py" --root "$repo" install-hooks --apply
python3 "$repo/_system/commands/deps.py" --root "$repo" project-auto-skills --apply
python3 "$repo/_system/agents/sync_skills.py" sync --root "$repo" --home "$HOME" --apply
"""


def bootstrap_worker(root: Path, registry: dict[str, Any], name: str, apply: bool) -> None:
    worker = machine_registry.resolve_machine(registry, name)
    config = worker.get("vault_sync", {})
    if worker.get("role") != "worker" or not config.get("enabled"):
        raise WorkerBootstrapError(f"vault worker bootstrap disabled: {worker['id']}")
    repo = str(config["repo_path"])
    if not apply:
        print(f"DRY RUN: bootstrap {worker['id']} at {repo} through {worker['ssh_alias']}")
        return
    remote = git_output(root, "remote", "get-url", "origin")
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", str(worker["ssh_alias"]), "bash", "-s"],
        input=bootstrap_script(worker, remote), text=True,
    )
    if result.returncode != 0:
        raise WorkerBootstrapError(f"bootstrap failed on {worker['id']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    hooks = sub.add_parser("install-hooks")
    hooks.add_argument("--apply", action="store_true")
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("name")
    bootstrap.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    try:
        if args.command == "install-hooks":
            install_hooks(root, args.apply)
        elif args.command == "bootstrap":
            registry_path = root / "_system/config/code-folder-and-computer-topology/private/machines.json"
            bootstrap_worker(root, machine_registry.load_registry(registry_path), args.name, args.apply)
        return 0
    except (WorkerBootstrapError, machine_registry.MachineError, OSError, subprocess.SubprocessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        print(f"Worker bootstrap failed: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
