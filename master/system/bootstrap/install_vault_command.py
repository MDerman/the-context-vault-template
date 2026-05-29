#!/usr/bin/env python3
"""Install the `vault` command into a user bin directory."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def same_target(link: Path, target: Path) -> bool:
    if not link.is_symlink():
        return False
    try:
        return link.resolve() == target.resolve()
    except FileNotFoundError:
        return False


def install_command(
    root: Path,
    bin_dir: Path,
    command_name: str,
    dry_run: bool,
    force: bool,
) -> int:
    target = root / "master/system/scripts/vault.py"
    link = bin_dir / command_name
    if not target.exists():
        print(f"missing vault dispatcher: {target}", file=sys.stderr)
        return 1

    if link.exists() or link.is_symlink():
        if same_target(link, target):
            print(f"{link} already points to {target}")
            return 0
        if not force:
            print(
                f"refusing to overwrite existing command: {link}\n"
                "Pass --force only if this command belongs to this vault setup.",
                file=sys.stderr,
            )
            return 1
        print(f"replace {link} -> {target}")
        if not dry_run:
            link.unlink()
    else:
        print(f"install {link} -> {target}")

    if dry_run:
        return 0

    bin_dir.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    os.chmod(target, target.stat().st_mode | 0o755)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the vault command.")
    parser.add_argument("--root", default=str(default_root()), help="Vault root.")
    parser.add_argument("--bin-dir", default=str(Path.home() / ".local/bin"), help="Directory to receive the command symlink.")
    parser.add_argument("--command-name", default="vault", help="Command name to install.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files.")
    parser.add_argument("--force", action="store_true", help="Replace an existing unrelated command symlink/file.")
    args = parser.parse_args(argv)

    return install_command(
        Path(args.root).expanduser().resolve(),
        Path(args.bin_dir).expanduser(),
        args.command_name,
        args.dry_run,
        args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
