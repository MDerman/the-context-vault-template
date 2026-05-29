#!/usr/bin/env python3
"""Back up the root Obsidian profile."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

from script_utils import resolve_vault_root


DEFAULT_BACKUP_ROOT = "master/system/backup/obsidian-profile"


def copy_backup(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] copy {source} -> {target}")
        return
    if target.exists():
        raise SystemExit(f"Backup already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, symlinks=False)


def write_manifest(path: Path, root: Path, source: Path, dry_run: bool) -> None:
    manifest = {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source": str(source.relative_to(root)),
        "note": "Local timestamped backup of the root Obsidian profile.",
    }
    if dry_run:
        print(f"[dry-run] write {path}")
        print(json.dumps(manifest, indent=2))
        return
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back up root .obsidian to master/system/backup."
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument(
        "--backup-root",
        default=DEFAULT_BACKUP_ROOT,
        help=f"Backup folder relative to the vault root. Defaults to {DEFAULT_BACKUP_ROOT}.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional backup folder name. Defaults to obsidian-profile-YYYYmmdd-HHMMSS.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview paths without copying files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    source = root / ".obsidian"
    if not source.is_dir():
        raise SystemExit(f"Missing root .obsidian folder: {source}")

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = args.name or f"obsidian-profile-{timestamp}"
    backup_root = root / args.backup_root
    backup_dir = backup_root / backup_name
    backup_profile = backup_dir / ".obsidian"

    copy_backup(source, backup_profile, args.dry_run)
    write_manifest(backup_dir / "manifest.json", root, source, args.dry_run)

    print(f"backup: {backup_profile.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
