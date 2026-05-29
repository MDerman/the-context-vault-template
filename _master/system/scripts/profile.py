#!/usr/bin/env python3
"""Focused Obsidian profile upgrade command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root
from upgrade import (
    DEFAULT_REPO_URL,
    REPORT_ROOT,
    apply_change,
    changed_paths,
    ensure_install_state,
    fetch_latest,
    latest_release,
    load_policy,
    read_json,
    utc_stamp,
    write_json,
)


PROFILE_PATTERNS = [
    ".obsidian/app.json",
    ".obsidian/appearance.json",
    ".obsidian/community-plugins.json",
    ".obsidian/community-plugins.full-desktop.json",
    ".obsidian/core-plugins.json",
    ".obsidian/daily-notes.json",
    ".obsidian/graph.json",
    ".obsidian/hotkeys.json",
    ".obsidian/snippets/**",
    ".obsidian/themes/**",
    ".obsidian/plugins/*/main.js",
    ".obsidian/plugins/*/manifest.json",
    ".obsidian/plugins/*/styles.css",
]
WORKSPACE_PATTERNS = [
    ".obsidian/workspace.json",
    ".obsidian/workspaces.json",
    ".obsidian/workspace-mobile.json",
]
INSTALL_PLUGINS = Path("_master/system/bootstrap/install_plugins.py")


def match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) or (pattern.endswith("/**") and path.startswith(pattern[:-3] + "/")) for pattern in patterns)


def allowed_change(change_path: str, old_path: str | None, include_workspace: bool) -> bool:
    patterns = [*PROFILE_PATTERNS, *(WORKSPACE_PATTERNS if include_workspace else [])]
    return match_any(change_path, patterns) or (old_path is not None and match_any(old_path, patterns))


def report_path(root: Path, timestamp: str) -> Path:
    return root / REPORT_ROOT / timestamp / "profile-report.json"


def run_plugin_installer(root: Path, apply: bool) -> dict[str, Any]:
    script = root / INSTALL_PLUGINS
    if not script.exists():
        return {"path": INSTALL_PLUGINS.as_posix(), "result": "missing"}
    args = [
        sys.executable,
        str(script),
        "--root",
        str(root),
        "--apply" if apply else "--dry-run",
    ]
    completed = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        "path": INSTALL_PLUGINS.as_posix(),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "result": "ok" if completed.returncode == 0 else "failed",
    }


def run_profile_upgrade(root: Path, apply: bool, include_workspace: bool) -> int:
    install, state_dir, upstream_git_dir = ensure_install_state(root)
    latest_rev = fetch_latest(root, upstream_git_dir)
    installed_rev = install.get("installed_commit") or "HEAD"
    policy = load_policy(root, upstream_git_dir, latest_rev)
    release = latest_release(root, upstream_git_dir, latest_rev)
    timestamp = utc_stamp()
    backup_root = state_dir / "backups" / timestamp / "profile"

    changes = [
        change
        for change in changed_paths(root, upstream_git_dir, installed_rev, latest_rev)
        if allowed_change(change.path, change.old_path, include_workspace)
    ]
    entries: list[dict[str, Any]] = []
    for change in changes:
        entries.append(
            apply_change(
                root=root,
                git_dir=upstream_git_dir,
                latest_rev=latest_rev,
                change=change,
                action="replace",
                policy=policy,
                apply=apply,
                backup_root=backup_root,
            )
        )

    plugin_install = run_plugin_installer(root, apply=apply)
    payload: dict[str, Any] = {
        "timestamp": timestamp,
        "mode": "apply" if apply else "dry-run",
        "include_workspace": include_workspace,
        "repo_url": install.get("repo_url") or release.get("repo_url") or DEFAULT_REPO_URL,
        "installed_commit": installed_rev,
        "latest_commit": latest_rev,
        "installed_version": install.get("installed_version"),
        "latest_version": release.get("version"),
        "backup_root": backup_root.as_posix(),
        "changes": entries,
        "plugin_install": plugin_install,
    }
    path = report_path(root, timestamp)
    write_json(path, payload)
    print(f"{'Applied' if apply else 'Dry-run'} profile upgrade report: {path}")
    print(f"profile changes: {len(entries)}")
    print(f"plugin install: {plugin_install.get('result')}")
    if plugin_install.get("returncode", 0) not in {0, None}:
        return int(plugin_install["returncode"])
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upgrade only Obsidian profile/plugin files from public bootstrap state.")
    parser.add_argument("command", nargs="?", choices=["upgrade"], help="Use `upgrade` to preview or apply profile updates.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview profile updates and write a report.")
    mode.add_argument("--apply", action="store_true", help="Apply profile updates and install active plugins.")
    parser.add_argument("--include-workspace", action="store_true", help="Also replace Obsidian workspace/open-tabs layout files.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    if args.command != "upgrade":
        print("Use `vault profile upgrade --dry-run` or `vault profile upgrade --apply`.")
        return 2
    if not args.apply and not args.dry_run:
        print("Use `--dry-run` or `--apply`.")
        return 2
    return run_profile_upgrade(root, apply=args.apply, include_workspace=args.include_workspace)


if __name__ == "__main__":
    raise SystemExit(main())
