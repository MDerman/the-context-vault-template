#!/usr/bin/env python3
"""Create or refresh the Obsidian mobile profile."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from script_utils import resolve_vault_root


MOBILE_PLUGINS = [
    "tasknotes",
    "calendar",
    "periodic-notes",
    "sync-embeds",
    "obsidian-style-settings",
    "obsidian-file-color",
    "obsidian-icon-folder",
    "system3-relay",
]

CORE_SETTINGS_TO_COPY = [
    "app.json",
    "daily-notes.json",
    "graph.json",
    "types.json",
]


def read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def copy_file(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def ignore_backup_files(_: str, names: list[str]) -> set[str]:
    return {name for name in names if ".bak" in name or name.startswith("relay.log") or name.startswith("relay ")}


def copy_directory(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=ignore_backup_files)
    return True


def sync_plugins(source_profile: Path, mobile_profile: Path, prune: bool) -> list[str]:
    copied: list[str] = []
    source_plugins = source_profile / "plugins"
    mobile_plugins = mobile_profile / "plugins"
    mobile_plugins.mkdir(parents=True, exist_ok=True)

    for plugin_id in MOBILE_PLUGINS:
        if copy_directory(source_plugins / plugin_id, mobile_plugins / plugin_id):
            copied.append(plugin_id)
        else:
            print(f"Warning: plugin source missing: {source_plugins / plugin_id}")

    if prune:
        allowed = set(MOBILE_PLUGINS)
        for child in mobile_plugins.iterdir():
            if child.is_dir() and child.name not in allowed:
                shutil.rmtree(child)

    return copied


def sync_theme_and_snippets(source_profile: Path, mobile_profile: Path, prune: bool) -> None:
    appearance = read_json(source_profile / "appearance.json", {})
    if isinstance(appearance, dict):
        write_json(mobile_profile / "appearance.json", appearance)
    else:
        appearance = {}

    theme = appearance.get("cssTheme")
    if isinstance(theme, str) and theme:
        copy_directory(source_profile / "themes" / theme, mobile_profile / "themes" / theme)
        if prune:
            themes_dir = mobile_profile / "themes"
            if themes_dir.exists():
                for child in themes_dir.iterdir():
                    if child.is_dir() and child.name != theme:
                        shutil.rmtree(child)

    snippet_names = appearance.get("enabledCssSnippets", [])
    if not isinstance(snippet_names, list):
        snippet_names = []
    snippets_dir = mobile_profile / "snippets"
    snippets_dir.mkdir(parents=True, exist_ok=True)
    for name in snippet_names:
        if isinstance(name, str) and name:
            copy_file(source_profile / "snippets" / f"{name}.css", snippets_dir / f"{name}.css")
    if prune:
        allowed = {f"{name}.css" for name in snippet_names if isinstance(name, str)}
        for child in snippets_dir.iterdir():
            if child.is_file() and child.name not in allowed:
                child.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create/update .obsidian-mobile from safe mobile settings.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--source-profile", default=".obsidian", help="Source Obsidian config folder.")
    parser.add_argument("--mobile-profile", default=".obsidian-mobile", help="Mobile Obsidian config folder.")
    parser.add_argument("--no-prune", action="store_true", help="Do not remove unapproved mobile plugin/theme/snippet dirs.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    source_profile = root / args.source_profile
    mobile_profile = root / args.mobile_profile
    mobile_profile.mkdir(parents=True, exist_ok=True)

    copied = sync_plugins(source_profile, mobile_profile, prune=not args.no_prune)
    write_json(mobile_profile / "community-plugins.json", MOBILE_PLUGINS)
    sync_theme_and_snippets(source_profile, mobile_profile, prune=not args.no_prune)

    for filename in CORE_SETTINGS_TO_COPY:
        copy_file(source_profile / filename, mobile_profile / filename)
    if not (mobile_profile / "core-plugins.json").exists():
        copy_file(source_profile / "core-plugins.json", mobile_profile / "core-plugins.json")

    print(f"Mobile profile refreshed: {mobile_profile.relative_to(root)}")
    print("Synced core settings:")
    for filename in CORE_SETTINGS_TO_COPY:
        if (mobile_profile / filename).exists():
            print(f"- {filename}")
    print("Enabled mobile plugins:")
    for plugin_id in MOBILE_PLUGINS:
        status = "copied" if plugin_id in copied else "missing"
        print(f"- {plugin_id} ({status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
