#!/usr/bin/env python3
"""Patch the installed Primary theme with local dark-mode palette presets."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root

START_MARKER = "/* BEGIN managed-by patch_primary_dark_theme.py */"
END_MARKER = "/* END managed-by patch_primary_dark_theme.py */"
PRESETS_FILE = Path(__file__).with_name("primary_theme_presets.json")
STYLE_SETTINGS_PATH = Path(".obsidian/plugins/obsidian-style-settings/data.json")


def load_presets(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Could not find preset config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Preset config is not valid JSON: {path}: {exc}") from exc

    presets = data.get("presets")
    if not isinstance(presets, dict) or not presets:
        raise SystemExit(f"Preset config must contain a non-empty 'presets' object: {path}")
    return data


def preset_names(config: dict[str, Any]) -> list[str]:
    return sorted(config["presets"])


def get_preset(config: dict[str, Any], name: str | None) -> tuple[str, dict[str, Any]]:
    selected = name or config.get("default_preset") or "current-local"
    presets = config["presets"]
    if selected not in presets:
        available = ", ".join(preset_names(config))
        raise SystemExit(f"Unknown preset '{selected}'. Available presets: {available}")
    preset = presets[selected]
    if not isinstance(preset, dict):
        raise SystemExit(f"Preset '{selected}' must be an object.")
    return selected, preset


def css_comment_lines(lines: list[str]) -> str:
    return "\n".join(f"    /* {line} */" for line in lines)


def css_variable_lines(variables: list[list[str]]) -> str:
    rendered = []
    for item in variables:
        if not isinstance(item, list) or len(item) != 2:
            raise SystemExit("Each CSS variable entry must be a two-item list.")
        name, value = item
        rendered.append(f"    {name}: {value};")
    return "\n".join(rendered)


def build_weird_overrides() -> str:
    return """

    /* Temporary visibility test. Remove by rerunning without --weird-test. */
    --background-primary: hsl(300, 70%, 14%);
    --background-primary-alt: hsl(300, 70%, 11%);
    --background-secondary: hsl(140, 60%, 10%);
    --background-secondary-alt: hsl(140, 60%, 10%);
    --tab-container-background: hsl(140, 60%, 10%);
    --titlebar-background: hsl(140, 60%, 10%);
    --titlebar-background-focused: hsl(140, 60%, 10%);
    --ribbon-background: hsl(55, 90%, 18%);
    --text-normal: hsl(82, 100%, 84%);
    --text-muted: hsl(82, 60%, 72%);
    --text-faint: hsl(82, 35%, 62%);
"""


def build_patch(preset_name: str, preset: dict[str, Any], weird_test: bool = False) -> str:
    comments = preset.get("comments", [])
    variables = preset.get("theme_dark_variables")
    scrollbar_track = preset.get("scrollbar_track")
    scrollbar_thumb = preset.get("scrollbar_thumb", "var(--scrollbar-thumb-bg)")
    extra_css = preset.get("extra_css", "")

    if not isinstance(comments, list) or not all(isinstance(line, str) for line in comments):
        raise SystemExit(f"Preset '{preset_name}' comments must be a list of strings.")
    if not isinstance(variables, list):
        raise SystemExit(f"Preset '{preset_name}' must define theme_dark_variables.")
    if not isinstance(scrollbar_track, str):
        raise SystemExit(f"Preset '{preset_name}' must define scrollbar_track.")
    if not isinstance(scrollbar_thumb, str):
        raise SystemExit(f"Preset '{preset_name}' scrollbar_thumb must be a string.")
    if not isinstance(extra_css, str):
        raise SystemExit(f"Preset '{preset_name}' extra_css must be a string.")

    comment_block = css_comment_lines(comments)
    variable_block = css_variable_lines(variables)
    weird_overrides = build_weird_overrides().rstrip() if weird_test else ""
    if weird_overrides:
        variable_block = f"{variable_block}\n{weird_overrides}"

    return f"""{START_MARKER}
.theme-dark {{
    /* Preset: {preset_name} */
{comment_block}
{variable_block}
}}

.theme-dark ::-webkit-scrollbar,
.theme-dark ::-webkit-scrollbar-track,
.theme-dark ::-webkit-scrollbar-track-piece,
.theme-dark ::-webkit-scrollbar-corner {{
    background-color: {scrollbar_track};
}}

.theme-dark {{
    scrollbar-color: {scrollbar_thumb} {scrollbar_track};
}}
{extra_css.rstrip()}
{END_MARKER}
"""


def replace_managed_block(css: str, replacement: str) -> tuple[str, str]:
    start = css.find(START_MARKER)
    end = css.find(END_MARKER)

    if start == -1 and end == -1:
        separator = "\n" if css.endswith("\n") else "\n\n"
        return f"{css}{separator}{replacement}\n", "added"

    if start == -1 or end == -1 or end < start:
        raise SystemExit("Found a partial managed block. Please inspect theme.css before patching.")

    end += len(END_MARKER)
    return f"{css[:start]}{replacement}{css[end:].lstrip(chr(10))}", "updated"


def remove_managed_block(css: str) -> tuple[str, str]:
    start = css.find(START_MARKER)
    end = css.find(END_MARKER)

    if start == -1 and end == -1:
        return css, "not present"

    if start == -1 or end == -1 or end < start:
        raise SystemExit("Found a partial managed block. Please inspect theme.css before removing.")

    end += len(END_MARKER)
    return f"{css[:start]}{css[end:]}".rstrip() + "\n", "removed"


def backup_file(path: Path, timestamp: str) -> Path:
    backup = path.with_suffix(f"{path.suffix}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def load_style_settings(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Could not find Style Settings data: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Style Settings data is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Style Settings data must be a JSON object: {path}")
    return data


def merge_style_settings(existing: dict[str, Any], preset: dict[str, Any]) -> tuple[dict[str, Any], int]:
    style_settings = preset.get("style_settings", {})
    if not isinstance(style_settings, dict):
        raise SystemExit("Preset style_settings must be an object.")

    updated = dict(existing)
    changed = 0
    for key, value in style_settings.items():
        if updated.get(key) != value:
            changed += 1
        updated[key] = value
    return updated, changed


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def action_verb(action: str) -> str:
    return {"added": "add", "updated": "update", "removed": "remove"}.get(action, action)


def main() -> None:
    config = load_presets(PRESETS_FILE)

    parser = argparse.ArgumentParser(
        description="Patch .obsidian/themes/Primary/theme.css with local Primary dark-mode presets."
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--theme", default="Primary", help="Theme folder under .obsidian/themes.")
    parser.add_argument(
        "--preset",
        default=None,
        help="Preset name from primary_theme_presets.json. Defaults to the config default_preset.",
    )
    parser.add_argument("--list-presets", action="store_true", help="List available presets and exit.")
    parser.add_argument("--remove", action="store_true", help="Remove the managed patch block.")
    parser.add_argument("--weird-test", action="store_true", help="Use obvious colors to verify the patch is loading.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing.")
    parser.add_argument("--no-backup", action="store_true", help="Skip writing timestamped .bak files.")
    args = parser.parse_args()

    if args.list_presets:
        for name in preset_names(config):
            description = config["presets"][name].get("description", "")
            suffix = f" - {description}" if description else ""
            print(f"{name}{suffix}")
        return

    root = resolve_vault_root(args.root, __file__)
    theme_css = root / ".obsidian" / "themes" / args.theme / "theme.css"
    style_settings_path = root / STYLE_SETTINGS_PATH
    if not theme_css.exists():
        raise SystemExit(f"Could not find theme CSS: {theme_css}")

    original_css = theme_css.read_text(encoding="utf-8")
    if args.remove:
        updated_css, css_action = remove_managed_block(original_css)
        style_settings = None
        updated_style_settings = None
        style_changed = 0
        preset_name = None
    else:
        preset_name, preset = get_preset(config, args.preset)
        updated_css, css_action = replace_managed_block(original_css, build_patch(preset_name, preset, args.weird_test))
        style_settings = load_style_settings(style_settings_path)
        updated_style_settings, style_changed = merge_style_settings(style_settings, preset)

    css_changed = updated_css != original_css
    settings_changed = style_changed > 0

    if not css_changed and not settings_changed:
        if args.remove:
            print(f"No change: managed patch block is {css_action}.")
        else:
            print(f"No change: preset '{preset_name}' is already applied.")
        return

    if args.dry_run:
        if css_changed:
            print(f"[dry-run] Would {action_verb(css_action)} managed patch block in {theme_css}")
        if settings_changed:
            print(f"[dry-run] Would update {style_changed} Style Settings key(s) in {style_settings_path}")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if css_changed:
        if not args.no_backup:
            print(f"Backup written: {backup_file(theme_css, timestamp)}")
        theme_css.write_text(updated_css, encoding="utf-8")
        print(f"Patch {css_action}: {theme_css}")

    if settings_changed:
        if not args.no_backup:
            print(f"Backup written: {backup_file(style_settings_path, timestamp)}")
        write_json(style_settings_path, updated_style_settings)
        print(f"Style Settings updated: {style_settings_path} ({style_changed} key(s))")


if __name__ == "__main__":
    main()
