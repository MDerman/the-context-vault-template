#!/usr/bin/env python3
"""Move legacy context HOME.md files and entity operating sections."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SKIP_PREFIXES = (".", "_")
TEXT_SUFFIXES = {".base", ".json", ".md", ".markdown", ".txt", ".yaml", ".yml"}
LEGACY_DECLARATION_STEM = "DECLARATION"
ENTITY_SUPPORT_DIR = "brand-strategy-and-vision"
CONTENT_CADENCE_PATH = Path("_obsidian/content/content-cadence.json")
SENSITIVE_PATH_NAMES = {"secret", "secrets", "token", "tokens", "key", "keys", "kubeconfig"}


def context_folders_with_legacy_home(root: Path) -> list[Path]:
    folders: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(SKIP_PREFIXES):
            continue
        if (child / "HOME.md").exists():
            folders.append(child)
    return folders


def is_context_folder(path: Path) -> bool:
    if not path.is_dir() or path.name.startswith(SKIP_PREFIXES):
        return False
    return (path / f"{path.name}.md").exists() or (path / "HOME.md").exists()


def context_folders(root: Path) -> list[Path]:
    return [child for child in sorted(root.iterdir()) if is_context_folder(child)]


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    close_end = end + len("\n---")
    if close_end < len(text) and text[close_end] == "\n":
        close_end += 1
    return text[:close_end], text[close_end:]


def extract_section(text: str, heading: str) -> str | None:
    _frontmatter, body = split_frontmatter(text)
    lines = body.splitlines()
    heading_re = re.compile(r"^(#{1,6})\s+" + re.escape(heading) + r"\s*$")
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = heading_re.match(line)
        if match:
            start = index
            level = len(match.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def section_has_content(section: str | None) -> bool:
    if not section:
        return False
    lines = [
        line.strip()
        for line in section.splitlines()[1:]
        if line.strip() and not re.match(r"^#{1,6}\s+", line.strip())
    ]
    return bool(lines)


def managed_text(text: str) -> bool:
    props, _body = split_frontmatter(text)
    return (
        "generated: true" in props
        or "managed-by:" in props
        or "managed-by: _master/system/bootstrap" in text
    )


def migrate_sections(folder: Path, root: Path, apply: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    moved: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    legacy_note = folder / f"{LEGACY_DECLARATION_STEM}.md"
    entity_note = folder / f"{folder.name}.md"
    if not legacy_note.exists() or not entity_note.exists():
        return moved, conflicts
    legacy_text = legacy_note.read_text(encoding="utf-8")
    entity_text = entity_note.read_text(encoding="utf-8")
    updated = entity_text.rstrip()
    conflict = False
    for heading in ("Identity", "Momentum", "Social Selling"):
        source_section = extract_section(legacy_text, heading)
        if not section_has_content(source_section):
            continue
        target_section = extract_section(entity_text, heading)
        entry = {
            "source": f"{legacy_note.relative_to(root).as_posix()}#{heading}",
            "target": f"{entity_note.relative_to(root).as_posix()}#{heading}",
        }
        if section_has_content(target_section):
            conflicts.append(entry)
            conflict = True
            continue
        updated += "\n\n" + source_section.strip()
        moved.append(entry)
    if apply and updated != entity_text.rstrip():
        entity_note.write_text(updated.rstrip() + "\n", encoding="utf-8")
    if apply and not conflict and managed_text(legacy_text):
        legacy_note.unlink()
    return moved, conflicts


def move_cadence_config(folder: Path, root: Path, apply: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    source = folder / LEGACY_DECLARATION_STEM / "content-cadence.json"
    target = folder / CONTENT_CADENCE_PATH
    if not source.exists():
        return [], []
    entry = {
        "source": source.relative_to(root).as_posix(),
        "target": target.relative_to(root).as_posix(),
    }
    if target.exists():
        return [], [entry]
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    return [entry], []


def rename_support_folder(folder: Path, root: Path, apply: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    source = folder / LEGACY_DECLARATION_STEM
    target = folder / ENTITY_SUPPORT_DIR
    if not source.exists() or not source.is_dir():
        return [], []
    entry = {
        "source": source.relative_to(root).as_posix(),
        "target": target.relative_to(root).as_posix(),
    }
    if target.exists():
        return [], [entry]
    if apply:
        source.rename(target)
    return [entry], []


def path_is_sensitive(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    for part in parts:
        lowered = part.lower()
        if lowered.startswith(".env") or lowered in SENSITIVE_PATH_NAMES:
            return True
    return False


def rewrite_text(text: str, entity: str, *, include_relative: bool) -> str:
    replacements = {
        f"{entity}/{LEGACY_DECLARATION_STEM}/content-cadence.json": f"{entity}/_obsidian/content/content-cadence.json",
        f"{entity}/{LEGACY_DECLARATION_STEM}#": f"{entity}/{entity}#",
        f"{entity}/{LEGACY_DECLARATION_STEM}/": f"{entity}/{ENTITY_SUPPORT_DIR}/",
    }
    if include_relative:
        replacements.update(
            {
                f"{LEGACY_DECLARATION_STEM}/content-cadence.json": "_obsidian/content/content-cadence.json",
                f"[[{LEGACY_DECLARATION_STEM}#": f"[[{entity}#",
                f"![[{LEGACY_DECLARATION_STEM}#": f"![[{entity}#",
                f"[[{LEGACY_DECLARATION_STEM}/": f"[[{ENTITY_SUPPORT_DIR}/",
                f"![[{LEGACY_DECLARATION_STEM}/": f"![[{ENTITY_SUPPORT_DIR}/",
            }
        )
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def owning_entity(path: Path, folders: list[Path]) -> str | None:
    for folder in folders:
        try:
            path.relative_to(folder)
        except ValueError:
            continue
        return folder.name
    return None


def rewrite_legacy_refs(root: Path, folders: list[Path], apply: bool) -> list[str]:
    changed: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.is_symlink() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path_is_sensitive(path, root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rewritten = text
        owner = owning_entity(path, folders)
        for folder in folders:
            rewritten = rewrite_text(rewritten, folder.name, include_relative=owner == folder.name)
        if rewritten == text:
            continue
        changed.append(path.relative_to(root).as_posix())
        if apply:
            path.write_text(rewritten, encoding="utf-8")
    return changed


def run(root: Path, apply: bool) -> dict[str, object]:
    moved: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    section_moves: list[dict[str, str]] = []
    section_conflicts: list[dict[str, str]] = []
    cadence_moves: list[dict[str, str]] = []
    cadence_conflicts: list[dict[str, str]] = []
    support_moves: list[dict[str, str]] = []
    support_conflicts: list[dict[str, str]] = []

    for folder in context_folders_with_legacy_home(root):
        source = folder / "HOME.md"
        target = folder / f"{folder.name}.md"
        entry = {
            "source": source.relative_to(root).as_posix(),
            "target": target.relative_to(root).as_posix(),
        }
        if target.exists():
            conflicts.append(entry)
            continue
        moved.append(entry)
        if apply:
            source.rename(target)
    folders = context_folders(root)
    for folder in folders:
        migrated, section_conflict = migrate_sections(folder, root, apply)
        section_moves.extend(migrated)
        section_conflicts.extend(section_conflict)
        cadence_moved, cadence_conflict = move_cadence_config(folder, root, apply)
        cadence_moves.extend(cadence_moved)
        cadence_conflicts.extend(cadence_conflict)
        support_moved, support_conflict = rename_support_folder(folder, root, apply)
        support_moves.extend(support_moved)
        support_conflicts.extend(support_conflict)
    rewritten_refs = rewrite_legacy_refs(root, folders, apply)
    conflicts.extend(section_conflicts)
    conflicts.extend(cadence_conflicts)
    conflicts.extend(support_conflicts)

    return {
        "migration": "2026_05_30_context_folder_notes",
        "mode": "apply" if apply else "dry-run",
        "moved": moved,
        "moved_count": len(moved),
        "section_moves": section_moves,
        "section_move_count": len(section_moves),
        "cadence_moves": cadence_moves,
        "cadence_move_count": len(cadence_moves),
        "support_folder_moves": support_moves,
        "support_folder_move_count": len(support_moves),
        "rewritten_refs": rewritten_refs,
        "rewritten_ref_count": len(rewritten_refs),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--report", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    report = Path(args.report).expanduser().resolve()
    payload = run(root, apply=args.apply)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"moved files: {payload['moved_count']}")
    print(f"moved sections: {payload['section_move_count']}")
    print(f"moved cadence configs: {payload['cadence_move_count']}")
    print(f"moved support folders: {payload['support_folder_move_count']}")
    print(f"rewritten refs: {payload['rewritten_ref_count']}")
    print(f"conflicts: {payload['conflict_count']}")
    return 1 if payload["conflict_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
