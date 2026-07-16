#!/usr/bin/env python3
"""Ensure root coding-agent file and local skill symlinks exist."""

from __future__ import annotations

import argparse
from pathlib import Path


OLD_MANAGED_MARKERS = (
    "managed-by: _master/system/bootstrap/" + "generate_" + "agents.py",
    "managed-by: _master/system/bootstrap/bootstrap_vault.py",
    "managed-by: _master/system/bootstrap/setup/bootstrap_vault.py",
    "managed-by: _master/bootstrap/setup/bootstrap_vault.py",
)


def can_replace_legacy_agent_file(path: Path) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(marker in text for marker in OLD_MANAGED_MARKERS)


def ensure_symlink(root: Path, link: Path, target: str, dry_run: bool, directory: bool = False) -> None:
    path = root / link
    if path.is_symlink():
        if str(path.readlink()) == target:
            return
        if dry_run:
            print(f"[dry-run] replace symlink {path} -> {target}")
            return
        path.unlink()
    elif path.exists():
        if path.is_file() and can_replace_legacy_agent_file(path):
            if dry_run:
                print(f"[dry-run] remove legacy generated file {path}")
                print(f"[dry-run] symlink {path} -> {target}")
                return
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            if dry_run:
                print(f"[dry-run] remove empty directory {path}")
                print(f"[dry-run] symlink {path} -> {target}")
                return
            path.rmdir()
        else:
            raise SystemExit(f"Refusing to replace existing non-symlink path: {path}")
    else:
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"[dry-run] symlink {path} -> {target}")
        return
    path.symlink_to(target, target_is_directory=directory)
    print(f"symlink {path} -> {target}")


def ensure_real_directory(root: Path, directory: Path, dry_run: bool) -> None:
    path = root / directory
    if path.is_symlink():
        if dry_run:
            print(f"[dry-run] remove legacy symlink {path}")
            print(f"[dry-run] mkdir {path}")
            return
        path.unlink()
        print(f"removed legacy symlink {path}")
    elif path.exists() and not path.is_dir():
        raise SystemExit(f"Refusing to replace existing non-directory path: {path}")
    elif path.exists():
        return

    if dry_run:
        print(f"[dry-run] mkdir {path}")
        return
    path.mkdir(parents=True, exist_ok=True)
    print(f"mkdir {path}")


def ensure_agent_paths(root: Path, dry_run: bool) -> None:
    for directory in [
        Path("_master/agents/skills"),
        Path("_master/agents/auto-skills"),
        Path("_master/agents/manual-skills"),
        Path("_master/agents/gh-skills"),
        Path("_master/agents/skills-dump"),
        Path(".agents"),
        Path(".claude"),
    ]:
        path = root / directory
        if path.exists():
            continue
        if dry_run:
            print(f"[dry-run] mkdir {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            print(f"mkdir {path}")

    ensure_symlink(root, Path("CLAUDE.md"), "AGENTS.md", dry_run)
    ensure_real_directory(root, Path(".agents/skills"), dry_run)
    ensure_symlink(root, Path(".claude/skills"), "../.agents/skills", dry_run, directory=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ensure root agent symlinks and local skill folders.")
    parser.add_argument("--root", default=".", help="Vault root.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    ensure_agent_paths(Path(args.root).expanduser().resolve(), args.dry_run)


if __name__ == "__main__":
    main()
