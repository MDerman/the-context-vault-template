#!/usr/bin/env python3
"""Patch the installed Primary theme with VS Code-ish root tabs."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from script_utils import resolve_vault_root

START_MARKER = "/* BEGIN managed-by patch_primary_tabs_theme.py */"
END_MARKER = "/* END managed-by patch_primary_tabs_theme.py */"

PATCH = f"""{START_MARKER}
/* Last-attempt root tab layout for Primary.
   Goal: normal horizontal tabs, full labels, flex-wrapped rows.
   This keeps the change inside Primary's theme.css instead of Obsidian snippets. */
.workspace .mod-root .workspace-tabs,
.workspace .mod-root .workspace-tab-container,
.workspace .mod-root .workspace-tab-header-container,
.workspace .mod-root .workspace-tab-header-container-inner {{
    overflow: visible !important;
}}

.workspace .mod-root .workspace-tab-header-container {{
    display: flex !important;
    align-items: flex-start !important;
    height: auto !important;
    min-height: 34px !important;
    padding: 0 8px 2px 8px !important;
}}

.workspace .mod-root .workspace-tab-header-container-inner {{
    display: flex !important;
    flex: 1 1 auto !important;
    flex-wrap: wrap !important;
    align-items: flex-start !important;
    align-content: flex-start !important;
    gap: 2px !important;
    height: auto !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}}

.workspace .mod-root .workspace-tabs:not(.mod-stacked) .workspace-tab-header {{
    --tab-width: auto;
    --tab-max-width: none;
    box-sizing: border-box !important;
    display: inline-flex !important;
    flex: 0 0 auto !important;
    width: max-content !important;
    min-width: max-content !important;
    max-width: none !important;
    height: 32px !important;
    min-height: 32px !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 1px solid var(--color-base-50);
    border-radius: 4px 4px 0 0;
    overflow: visible !important;
}}

.workspace .mod-root .workspace-tab-header-inner {{
    box-sizing: border-box !important;
    position: static !important;
    display: inline-flex !important;
    flex: 0 0 auto !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 6px !important;
    width: max-content !important;
    min-width: max-content !important;
    max-width: none !important;
    height: 100% !important;
    padding: 0 10px !important;
    overflow: visible !important;
    white-space: nowrap !important;
    writing-mode: horizontal-tb !important;
    transform: none !important;
}}

.workspace .mod-root .workspace-tab-header-inner::after {{
    display: none !important;
}}

.workspace .mod-root .workspace-tab-header-inner-title,
.workspace .mod-root .workspace-tab-header-inner-icon,
.workspace .mod-root .workspace-tab-header-status-icon {{
    position: static !important;
    inset: auto !important;
    display: inline-flex !important;
    flex: 0 0 auto !important;
    width: max-content !important;
    min-width: max-content !important;
    max-width: none !important;
    height: auto !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
    text-overflow: clip !important;
    white-space: nowrap !important;
    writing-mode: horizontal-tb !important;
    transform: none !important;
}}

.titlebar .workspace-tab-header-new-tab,
.mod-root .workspace-tab-header-new-tab {{
    display: inline-flex !important;
    flex: 0 0 auto !important;
    align-items: center !important;
    height: 32px !important;
    min-height: 32px !important;
    padding: 0 8px !important;
    margin: 0 !important;
}}

.titlebar .workspace-tab-header-tab-list,
.mod-root .workspace-tab-header-tab-list {{
    display: none !important;
}}

.workspace .mod-root .workspace-tabs:not(.mod-stacked) .workspace-tab-header-inner-close-button,
.workspace .mod-root .workspace-tabs:not(.mod-stacked) .workspace-tab-header:hover .workspace-tab-header-inner-close-button,
.workspace .mod-root .workspace-tab-header.is-active .workspace-tab-header-inner-close-button,
.workspace .mod-root .workspace-tab-header.is-active:hover .workspace-tab-header-inner-close-button {{
    display: none !important;
}}
{END_MARKER}
"""


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(f"{path.suffix}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def replace_managed_block(css: str, replacement: str) -> tuple[str, str]:
    start = css.find(START_MARKER)
    end = css.find(END_MARKER)

    if start == -1 and end == -1:
        separator = "\n" if css.endswith("\n") else "\n\n"
        return f"{css}{separator}{replacement}\n", "added"

    if start == -1 or end == -1 or end < start:
        raise SystemExit("Found a partial managed tabs block. Please inspect theme.css before patching.")

    end += len(END_MARKER)
    return f"{css[:start]}{replacement}{css[end:]}", "updated"


def remove_managed_block(css: str) -> tuple[str, str]:
    start = css.find(START_MARKER)
    end = css.find(END_MARKER)

    if start == -1 and end == -1:
        return css, "not present"

    if start == -1 or end == -1 or end < start:
        raise SystemExit("Found a partial managed tabs block. Please inspect theme.css before removing.")

    end += len(END_MARKER)
    return f"{css[:start]}{css[end:]}".rstrip() + "\n", "removed"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Patch .obsidian/themes/Primary/theme.css with local tab layout overrides."
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--theme", default="Primary", help="Theme folder under .obsidian/themes.")
    parser.add_argument("--remove", action="store_true", help="Remove the managed tabs patch block.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing.")
    parser.add_argument("--no-backup", action="store_true", help="Skip writing a timestamped .bak file.")
    args = parser.parse_args()

    root = resolve_vault_root(args.root, __file__)
    theme_css = root / ".obsidian" / "themes" / args.theme / "theme.css"
    if not theme_css.exists():
        raise SystemExit(f"Could not find theme CSS: {theme_css}")

    original = theme_css.read_text(encoding="utf-8")
    updated, action = remove_managed_block(original) if args.remove else replace_managed_block(original, PATCH)

    if updated == original:
        print(f"No change: managed tabs patch block is {action}.")
        return

    if args.dry_run:
        print(f"[dry-run] Would {action} managed tabs patch block in {theme_css}")
        return

    if not args.no_backup:
        print(f"Backup written: {backup_file(theme_css)}")

    theme_css.write_text(updated, encoding="utf-8")
    print(f"Tabs patch {action}: {theme_css}")


if __name__ == "__main__":
    main()
