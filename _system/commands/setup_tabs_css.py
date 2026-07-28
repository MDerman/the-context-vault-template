#!/usr/bin/env python3
"""Install and enable the local tabs.css Obsidian snippet."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from script_utils import resolve_vault_root

TABS_CSS = """/* VS Code-ish root tabs: full names, multiple rows, no close buttons. */
body {
    --tab-outline-color: transparent;
}

.workspace .mod-root .workspace-tab-header-container {
    display: flex;
    align-items: stretch;
    height: auto;
    min-height: var(--header-height);
    overflow: visible;
}

.workspace .mod-root .workspace-tab-header-container-inner {
    display: flex;
    flex: 1 1 auto;
    flex-wrap: wrap;
    align-items: stretch;
    gap: 2px;
    height: auto;
    margin: 0;
    padding: 2px;
    overflow: visible;
}

.workspace .mod-root .workspace-tabs:not(.mod-stacked) .workspace-tab-header {
    flex: 0 0 auto !important;
    width: max-content !important;
    max-width: none !important;
    min-width: 120px;
    height: var(--header-height);
    border: 1px solid var(--color-base-50);
}

.workspace .mod-root .workspace-tab-header-inner {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: var(--size-2-2);
    width: max-content !important;
    max-width: none !important;
    min-width: 120px;
    height: 100%;
    padding-inline: var(--size-4-2);
    writing-mode: horizontal-tb !important;
    transform: none !important;
}

.workspace .mod-root .workspace-tab-header-inner::after {
    width: 0;
}

.workspace .mod-root .workspace-tab-header-inner-title {
    display: block;
    flex: 0 0 auto;
    width: max-content !important;
    min-width: max-content !important;
    max-width: none !important;
    overflow: visible;
    text-overflow: clip;
    white-space: nowrap;
    writing-mode: horizontal-tb !important;
    transform: none !important;
}

.workspace .mod-root .workspace-tab-header-inner-icon,
.workspace .mod-root .workspace-tab-header-status-icon {
    flex: 0 0 auto;
    writing-mode: horizontal-tb !important;
    transform: none !important;
}

.titlebar .workspace-tab-header-new-tab,
.mod-root .workspace-tab-header-new-tab {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    height: var(--header-height);
    padding: 0 var(--size-4-2);
}

.titlebar .workspace-tab-header-tab-list,
.mod-root .workspace-tab-header-tab-list {
    display: none;
}

.workspace .mod-root .workspace-tabs:not(.mod-stacked) .workspace-tab-header-inner-close-button,
.workspace .mod-root .workspace-tabs:not(.mod-stacked) .workspace-tab-header:hover .workspace-tab-header-inner-close-button,
.workspace .mod-root .workspace-tab-header.is-active .workspace-tab-header-inner-close-button,
.workspace .mod-root .workspace-tab-header.is-active:hover .workspace-tab-header-inner-close-button {
    display: none;
}
"""


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(f"{path.suffix}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse JSON: {path}: {exc}") from exc


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create .obsidian/snippets/tabs.css and enable it in Obsidian appearance settings."
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--no-enable", action="store_true", help="Write tabs.css without enabling it.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing.")
    parser.add_argument("--no-backup", action="store_true", help="Skip backups for existing files.")
    args = parser.parse_args()

    root = resolve_vault_root(args.root, __file__)
    snippets_dir = root / ".obsidian" / "snippets"
    tabs_css = snippets_dir / "tabs.css"
    appearance_json = root / ".obsidian" / "appearance.json"

    if args.dry_run:
        print(f"[dry-run] Would write {tabs_css}")
        if not args.no_enable:
            print(f"[dry-run] Would ensure 'tabs' is enabled in {appearance_json}")
        return

    snippets_dir.mkdir(parents=True, exist_ok=True)
    if tabs_css.exists() and tabs_css.read_text(encoding="utf-8") != TABS_CSS and not args.no_backup:
        print(f"Backup written: {backup_file(tabs_css)}")
    tabs_css.write_text(TABS_CSS, encoding="utf-8")
    print(f"Wrote {tabs_css}")

    if args.no_enable:
        return

    appearance = load_json(appearance_json)
    snippets = appearance.get("enabledCssSnippets", [])
    if not isinstance(snippets, list):
        raise SystemExit(f"Expected enabledCssSnippets to be a list in {appearance_json}")

    if "tabs" not in snippets:
        if appearance_json.exists() and not args.no_backup:
            print(f"Backup written: {backup_file(appearance_json)}")
        snippets.append("tabs")
        appearance["enabledCssSnippets"] = snippets
        write_json(appearance_json, appearance)
        print("Enabled CSS snippet: tabs")
    else:
        print("CSS snippet already enabled: tabs")


if __name__ == "__main__":
    main()
