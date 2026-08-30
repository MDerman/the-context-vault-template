#!/usr/bin/env python3
"""Install a sanitized public `_system/agents` tree into a Context Vault."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


class SkillSystemInstallError(RuntimeError):
    pass


def install_tree(
    source_repo: Path,
    vault_root: Path,
    *,
    source_url: str,
    release_version: str,
    commit: str,
) -> Path:
    source = source_repo.resolve() / "_system/agents"
    target = vault_root.resolve() / "_system/agents"
    if not (source / "_package/defaults/instance").is_dir():
        raise SkillSystemInstallError(f"public skill system source is incomplete: {source}")
    if target.exists() or target.is_symlink():
        raise SkillSystemInstallError(f"refusing to overwrite an existing agents tree: {target}")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise SkillSystemInstallError(f"public skill system contains a symlink: {path}")
    shutil.copytree(source, target)
    shutil.copytree(target / "_package/defaults/instance", target / "_package/instance")
    state = vault_root / "_system/local/state/skill-system-install.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "installed": True,
                "source_url": source_url,
                "release_version": release_version,
                "commit": commit,
                "selected_integrations": ["global-public-skills"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--vault-root", required=True, type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    print(
        install_tree(
            args.source_repo,
            args.vault_root,
            source_url=args.source_url,
            release_version=args.release_version,
            commit=args.commit,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
