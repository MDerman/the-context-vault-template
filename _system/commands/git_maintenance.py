#!/usr/bin/env python3
"""Trim local Git history and prune unreachable objects for this vault."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from script_utils import resolve_vault_root


def run(
    command: list[str],
    root: Path,
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def git_output(root: Path, *args: str) -> str:
    return run(["git", *args], root, capture=True).stdout.strip()


def remove_commit_graph(root: Path) -> None:
    graph = Path(git_output(root, "rev-parse", "--git-path", "objects/info/commit-graph"))
    graph_dir = Path(git_output(root, "rev-parse", "--git-path", "objects/info/commit-graphs"))
    if not graph.is_absolute():
        graph = root / graph
    if not graph_dir.is_absolute():
        graph_dir = root / graph_dir
    graph.unlink(missing_ok=True)
    if graph_dir.exists():
        shutil.rmtree(graph_dir)


def trim_shallow_boundary(root: Path, depth: int) -> bool:
    refs = git_output(
        root,
        "for-each-ref",
        "--format=%(refname)",
        "refs/heads",
        "refs/remotes",
        "refs/tags",
    ).splitlines()
    boundaries: set[str] = set()
    for ref in refs or ["HEAD"]:
        boundary = git_output(root, "rev-list", "--max-count=1", f"--skip={depth - 1}", ref)
        if boundary:
            boundaries.add(boundary)
    if not boundaries:
        return False
    shallow_path = Path(git_output(root, "rev-parse", "--git-path", "shallow"))
    if not shallow_path.is_absolute():
        shallow_path = root / shallow_path
    shallow_path.write_text("".join(f"{boundary}\n" for boundary in sorted(boundaries)), encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep local Git history shallow and compact.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--depth", type=int, default=100, help="Number of commits to keep locally.")
    parser.add_argument("--remote", default="origin", help="Remote used for shallow fetch.")
    parser.add_argument("--branch", default=None, help="Branch to fetch. Defaults to current branch.")
    parser.add_argument("--no-fetch", action="store_true", help="Skip remote fetch and trim local shallow boundary only.")
    parser.add_argument("--aggressive", action="store_true", help="Run aggressive garbage collection.")
    args = parser.parse_args(argv)

    if args.depth < 1:
        raise SystemExit("--depth must be >= 1")

    root = resolve_vault_root(args.root, __file__)
    if not (root / ".git").exists():
        print("Git maintenance skipped: no .git directory.")
        return 0

    branch = args.branch or git_output(root, "branch", "--show-current")
    if not branch:
        print("Git maintenance skipped: detached HEAD.")
        return 0

    if not args.no_fetch:
        fetch = run(
            ["git", "fetch", f"--depth={args.depth}", "--update-shallow", args.remote, branch],
            root,
            check=False,
            capture=True,
        )
        if fetch.returncode != 0:
            message = (fetch.stderr or fetch.stdout or "").strip()
            print(f"Warning: shallow fetch failed; continuing local prune. {message}", file=sys.stderr)

    trim_shallow_boundary(root, args.depth)
    remove_commit_graph(root)
    run(["git", "reflog", "expire", "--expire=now", "--expire-unreachable=now", "--all"], root)
    gc_command = ["git", "gc", "--prune=now"]
    if args.aggressive:
        gc_command.append("--aggressive")
    run(gc_command, root)

    commit_count = git_output(root, "rev-list", "--count", "HEAD")
    size = git_output(root, "count-objects", "-vH")
    print(f"Git maintenance complete: HEAD history count {commit_count}.")
    print(size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
