#!/usr/bin/env python3
"""Enforce a Gitless iCloud Mac worker."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
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


def bootstrap_script(worker: dict[str, Any]) -> str:
    config = worker["vault_sync"]
    repo = str(config["repo_path"])
    checkout = str(config.get("checkout", "icloud"))
    if worker.get("platform") != "macos" or checkout != "icloud":
        raise WorkerBootstrapError(
            f"Vault worker bootstrap is Mac/iCloud-only: {worker['id']}"
        )
    return f"""set -eu
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
repo={shlex.quote(repo)}
if [ ! -d "$repo" ]; then
  echo "iCloud vault is missing: $repo" >&2
  echo "Sign in to iCloud Drive, mark the Vault Keep Downloaded, and choose Download Now before retrying." >&2
  exit 2
fi
if /usr/bin/find "$repo" -flags +dataless -print -quit 2>/dev/null | /usr/bin/grep -q .; then
  echo "iCloud vault still contains dataless placeholders: $repo" >&2
  echo "Choose Keep Downloaded and Download Now in Finder, then wait for every item to materialize before retrying." >&2
  exit 2
fi
if [ ! -f "$repo/.git" ]; then
  echo "shared iCloud vault Git pointer is missing: $repo/.git" >&2
  exit 2
fi
pointer_target="$(/usr/bin/sed -n 's/^gitdir: //p' "$repo/.git")"
case "$pointer_target" in
  /*) ;;
  *) echo "invalid shared iCloud vault Git pointer: $repo/.git" >&2; exit 2 ;;
esac
if [ -e "$pointer_target" ]; then
  expected_legacy="$HOME/.local/share/vault-git/Vault.git"
  if [ "$pointer_target" != "$expected_legacy" ]; then
    echo "refusing to move unexpected Git target: $pointer_target" >&2
    exit 2
  fi
  /bin/mkdir -p "$HOME/.Trash"
  archive="$HOME/.Trash/Vault.git-disabled-$(/bin/date +%Y%m%dT%H%M%S)-$$"
  /bin/mv "$pointer_target" "$archive"
  echo "moved worker Vault Git metadata recoverably to $archive"
fi
if git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "worker iCloud vault still resolves as a Git worktree: $repo" >&2
  exit 2
fi
if [ -e "$HOME/Code/vault" ]; then
  echo "legacy Mac Vault repository must be moved out of ~/Code before acceptance: $HOME/Code/vault" >&2
  exit 2
fi
/bin/mkdir -p "$HOME/.config/vault" "$HOME/.local/bin"
/bin/chmod 700 "$HOME/.config/vault"
identity_tmp="$HOME/.config/vault/.machine-id.$$"
/usr/bin/printf '%s\\n' {shlex.quote(str(worker['id']))} > "$identity_tmp"
/bin/chmod 600 "$identity_tmp"
/bin/mv "$identity_tmp" "$HOME/.config/vault/machine-id"
/bin/ln -sfn "$repo/_system/commands/vault.py" "$HOME/.local/bin/vault"
python3 "$repo/_system/commands/deps.py" --root "$repo" project-auto-skills --apply
python3 "$repo/_system/agents/sync_skills.py" sync --root "$repo" --home "$HOME" --apply
python3 "$repo/_system/commands/refresh_schedule.py" --root "$repo" block-worker --machine-id {shlex.quote(str(worker['id']))}
python3 "$repo/_system/commands/refresh_schedule.py" --root "$repo" unregister
"""


def bootstrap_worker(
    root: Path,
    registry: dict[str, Any],
    name: str,
    apply: bool,
    *,
    provision_disabled: bool = False,
) -> None:
    worker = machine_registry.resolve_machine(
        registry, name, enabled=not provision_disabled
    )
    if provision_disabled and worker.get("enabled") is True:
        raise WorkerBootstrapError(
            f"machine is already enabled; omit --provision-disabled: {worker['id']}"
        )
    config = worker.get("vault_sync", {})
    if worker.get("role") != "worker" or not config.get("enabled"):
        raise WorkerBootstrapError(f"vault worker bootstrap disabled: {worker['id']}")
    repo = str(config["repo_path"])
    checkout = str(config.get("checkout", "icloud"))
    if worker.get("platform") != "macos" or checkout != "icloud":
        raise WorkerBootstrapError(
            f"Vault worker bootstrap is Mac/iCloud-only: {worker['id']}"
        )
    mac_code_vault = PurePosixPath(str(worker["home"])) / "Code/vault"
    if worker.get("platform") == "macos" and PurePosixPath(repo) == mac_code_vault:
        raise WorkerBootstrapError(
            f"macOS workers must not use ~/Code/vault: {worker['id']}"
        )
    if not apply:
        print(f"DRY RUN: bootstrap {worker['id']} at {repo} through {worker['ssh_alias']}")
        return
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", str(worker["ssh_alias"]), "bash", "-s"],
        input=bootstrap_script(worker), text=True,
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
    bootstrap.add_argument(
        "--provision-disabled",
        action="store_true",
        help="explicitly provision one disabled worker without enabling fleet automation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    try:
        if args.command == "install-hooks":
            install_hooks(root, args.apply)
        elif args.command == "bootstrap":
            registry_path = root / "_system/local/skills/infra-code-folder-and-computer-topology/private/machines.json"
            bootstrap_worker(
                root,
                machine_registry.load_registry(registry_path),
                args.name,
                args.apply,
                provision_disabled=args.provision_disabled,
            )
        return 0
    except (WorkerBootstrapError, machine_registry.MachineError, OSError, subprocess.SubprocessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        print(f"Worker bootstrap failed: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
