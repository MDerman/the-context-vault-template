#!/usr/bin/env python3
"""Fast-forward a clean vault clone before generated files change."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from script_utils import resolve_vault_root


class PreflightError(RuntimeError):
    pass


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check,
    )


def output(root: Path, *args: str) -> str:
    return git(root, *args).stdout.strip()


def run_skill_sync(root: Path) -> None:
    script = root / "_system/agents/sync_skills.py"
    if not script.is_file():
        raise PreflightError(f"skill sync script missing: {script}")
    subprocess.run(
        [sys.executable, str(script), "sync", "--root", str(root), "--apply"],
        cwd=root,
        check=True,
    )


def preflight(root: Path, remote: str, branch: str, *, sync_skills: bool = True) -> str:
    if not (root / ".git").exists():
        print("Git preflight inactive: vault is not a Git checkout.")
        return "inactive"
    if git(root, "remote", "get-url", remote, check=False).returncode != 0:
        print(f"Git preflight inactive: remote {remote!r} is not configured.")
        return "inactive"

    git(root, "fetch", remote, "--prune")
    current = output(root, "branch", "--show-current")
    if current != branch:
        raise PreflightError(f"expected branch {branch!r}; current branch is {current or 'detached HEAD'}")
    dirty = output(root, "status", "--porcelain", "--untracked-files=normal")
    if dirty:
        raise PreflightError("working tree is dirty; commit or clean changes before refresh")

    local = output(root, "rev-parse", branch)
    remote_ref = f"{remote}/{branch}"
    if git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/{remote_ref}", check=False).returncode != 0:
        raise PreflightError(f"remote branch missing: {remote_ref}")
    upstream = output(root, "rev-parse", remote_ref)
    state = "current"
    if local != upstream:
        local_is_base = git(root, "merge-base", "--is-ancestor", local, upstream, check=False).returncode == 0
        upstream_is_base = git(root, "merge-base", "--is-ancestor", upstream, local, check=False).returncode == 0
        if local_is_base:
            git(root, "merge", "--ff-only", remote_ref)
            state = "updated"
        elif upstream_is_base:
            state = "ahead"
        else:
            raise PreflightError(f"{branch} diverged from {remote_ref}; manual repair required")
    if sync_skills:
        run_skill_sync(root)
    print(f"Git preflight: {state} ({branch}).")
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="master")
    parser.add_argument("--skip-skills", action="store_true")
    args = parser.parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    try:
        preflight(root, args.remote, args.branch, sync_skills=not args.skip_skills)
        return 0
    except (PreflightError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        print(f"Git preflight failed: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
