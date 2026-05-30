#!/usr/bin/env python3
"""Rename a context folder and rewrite structured vault references."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".vault-upgrade",
    "__pycache__",
    "node_modules",
}
SENSITIVE_PATH_NAMES = {"secret", "secrets", "token", "tokens", "key", "keys", "kubeconfig"}
TEXT_SUFFIXES = {
    ".base",
    ".canvas",
    ".css",
    ".csv",
    ".html",
    ".json",
    ".md",
    ".markdown",
    ".svg",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
EXACT_VALUE_SKIP_KEYS = {"context_type", "entity_type", "type"}


@dataclass(frozen=True)
class RenameResult:
    moved: bool
    merged: bool
    rewritten_files: tuple[Path, ...]


def validate_slug(value: str, label: str) -> str:
    slug = value.strip()
    if "/" in slug or "\\" in slug or not VALID_NAME.match(slug):
        raise SystemExit(f"{label} must be lowercase and contain only letters, numbers, and hyphens.")
    return slug


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def path_is_sensitive(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    for part in parts:
        lowered = part.lower()
        if lowered.startswith(".env"):
            return True
        if lowered in SENSITIVE_PATH_NAMES:
            return True
    return False


def should_skip_dir(path: Path, root: Path) -> bool:
    return path.name in SKIP_DIR_NAMES or path_is_sensitive(path, root)


def should_consider_file(path: Path, root: Path) -> bool:
    if path_is_sensitive(path, root):
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in {"AGENTS.md", "CLAUDE.md", "README.md"}


def conflicts_for_merge(source: Path, target: Path) -> list[tuple[Path, Path]]:
    conflicts: list[tuple[Path, Path]] = []
    for item in sorted(source.rglob("*")):
        destination = target / item.relative_to(source)
        if item.is_dir() and not item.is_symlink():
            if destination.exists() and not destination.is_dir():
                conflicts.append((item, destination))
            continue
        if not destination.exists():
            continue
        if item.is_symlink():
            if destination.is_dir() and not destination.is_symlink():
                conflicts.append((item, destination))
            continue
        if item.is_file():
            if not destination.is_file():
                conflicts.append((item, destination))
            continue
        if destination.exists():
            conflicts.append((item, destination))
    return conflicts


def copy_missing(source: Path, target: Path, root: Path, dry_run: bool) -> None:
    for item in sorted(source.rglob("*"), key=lambda path: (len(path.parts), str(path))):
        destination = target / item.relative_to(source)
        if item.is_dir() and not item.is_symlink():
            if not dry_run:
                destination.mkdir(parents=True, exist_ok=True)
            continue
        if destination.exists():
            continue
        print(f"copy {rel(root, item)} -> {rel(root, destination)}")
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if item.is_symlink():
            destination.symlink_to(os.readlink(item))
        else:
            shutil.copy2(item, destination)


def move_or_merge_folder(root: Path, old: str, new: str, dry_run: bool, missing_ok: bool = False) -> tuple[bool, bool]:
    source = root / old
    target = root / new
    if old == new:
        return False, False
    if not source.exists():
        if missing_ok:
            print(f"skip missing context folder: {old}")
            return False, False
        raise SystemExit(f"context folder does not exist: {old}")
    if not source.is_dir() or source.is_symlink():
        raise SystemExit(f"context folder path is not a directory: {rel(root, source)}")
    if target.exists() and (not target.is_dir() or target.is_symlink()):
        raise SystemExit(f"context rename target is not a directory: {rel(root, target)}")
    if not target.exists():
        print(f"move {rel(root, source)} -> {rel(root, target)}")
        if not dry_run:
            source.rename(target)
        return True, False

    conflicts = conflicts_for_merge(source, target)
    if conflicts:
        shown = "\n".join(
            f"  - {rel(root, src)} conflicts with {rel(root, dst)}"
            for src, dst in conflicts[:20]
        )
        suffix = "" if len(conflicts) <= 20 else f"\n  ... and {len(conflicts) - 20} more"
        raise SystemExit(
            "Cannot safely merge context folder rename target.\n"
            f"Source: {rel(root, source)}\n"
            f"Target: {rel(root, target)}\n"
            "Move or remove conflicting files manually, then rerun.\n"
            f"{shown}{suffix}"
        )

    print(f"merge {rel(root, source)} -> {rel(root, target)}")
    copy_missing(source, target, root, dry_run)
    print(f"remove {rel(root, source)}")
    if not dry_run:
        shutil.rmtree(source)
    return False, True


def rename_inside_folder_note(root: Path, old: str, new: str, dry_run: bool) -> None:
    context_root = root / (old if dry_run else new)
    source = context_root / f"{old}.md"
    target = root / new / f"{new}.md"
    if source.exists():
        if target.exists() and source.resolve() != target.resolve():
            raise SystemExit(
                "Cannot rename context folder note because target already exists.\n"
                f"Source: {rel(root, source)}\n"
                f"Target: {rel(root, target)}"
            )
        print(f"move {rel(root, source)} -> {rel(root, target)}")
        if not dry_run:
            source.rename(target)
        return

    if not target.exists():
        raise SystemExit(f"Context folder note missing after rename: {rel(root, target)}")


def replace_common_structured(text: str, old: str, new: str) -> str:
    escaped = re.escape(old)
    text = re.sub(rf"(!?\[\[){escaped}(?=([/#|\]]))", rf"\1{new}", text)
    text = re.sub(rf"(\]\(<?){escaped}(?=([/#)>]))", rf"\1{new}", text)
    text = re.sub(rf"(?<![A-Za-z0-9_@/.-]){escaped}/", f"{new}/", text)
    text = re.sub(rf"(?<![A-Za-z0-9_/-])@{escaped}(?![A-Za-z0-9_-])", f"@{new}", text)
    return text


def replace_yaml_exact_values(text: str, old: str, new: str) -> str:
    escaped = re.escape(old)
    out: list[str] = []
    key_value = re.compile(rf"^(\s*)([A-Za-z0-9_-]+)(\s*:\s*)([\"']?){escaped}\4(\s*(?:#.*)?)$")
    list_value = re.compile(rf"^(\s*-\s*)([\"']?){escaped}\2(\s*(?:#.*)?)$")
    for line in text.splitlines(keepends=True):
        newline = ""
        body = line
        if body.endswith("\n"):
            body = body[:-1]
            newline = "\n"
        match = key_value.match(body)
        if match and match.group(2) not in EXACT_VALUE_SKIP_KEYS:
            body = f"{match.group(1)}{match.group(2)}{match.group(3)}{match.group(4)}{new}{match.group(4)}{match.group(5)}"
        else:
            match = list_value.match(body)
            if match:
                body = f"{match.group(1)}{match.group(2)}{new}{match.group(2)}{match.group(3)}"
        out.append(body + newline)
    return "".join(out)


def split_frontmatter(text: str) -> tuple[str, str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    close_end = end + len("\n---")
    if close_end < len(text) and text[close_end] == "\n":
        close_end += 1
    return text[:4], text[4:end], text[close_end:]


def replace_json_value(value: Any, old: str, new: str, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: replace_json_value(child, old, new, key) for key, child in value.items()}
    if isinstance(value, list):
        return [replace_json_value(child, old, new, parent_key) for child in value]
    if not isinstance(value, str):
        return value
    rewritten = replace_common_structured(value, old, new)
    if parent_key not in EXACT_VALUE_SKIP_KEYS and rewritten == old:
        return new
    return rewritten


def rewrite_json_text(text: str, old: str, new: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return replace_common_structured(text, old, new)
    rewritten = replace_json_value(data, old, new)
    if rewritten == data:
        return text
    return json.dumps(rewritten, indent=2, ensure_ascii=False) + "\n"


def rewrite_text_for_context(path: Path, text: str, old: str, new: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return rewrite_json_text(text, old, new)
    if suffix in {".md", ".markdown"}:
        frontmatter = split_frontmatter(text)
        if frontmatter is None:
            return replace_common_structured(text, old, new)
        open_marker, frontmatter_body, body = frontmatter
        rewritten_frontmatter = replace_common_structured(frontmatter_body, old, new)
        rewritten_frontmatter = replace_yaml_exact_values(rewritten_frontmatter, old, new)
        rewritten_body = replace_common_structured(body, old, new)
        return f"{open_marker}{rewritten_frontmatter}\n---\n{rewritten_body}"
    if suffix in {".base", ".yaml", ".yml", ".toml"}:
        rewritten = replace_common_structured(text, old, new)
        return replace_yaml_exact_values(rewritten, old, new)
    return replace_common_structured(text, old, new)


def iter_rewrite_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(should_skip_dir(parent, root) for parent in path.parents if parent != path):
            continue
        if path.is_symlink() or not should_consider_file(path, root):
            continue
        candidates.append(path)
    return sorted(candidates)


def rewrite_structured_references(root: Path, old: str, new: str, dry_run: bool) -> tuple[Path, ...]:
    changed: list[Path] = []
    for path in iter_rewrite_candidates(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rewritten = rewrite_text_for_context(path, text, old, new)
        if rewritten == text:
            continue
        changed.append(path)
        print(f"rewrite {rel(root, path)}")
        if not dry_run:
            path.write_text(rewritten, encoding="utf-8")
    return tuple(changed)


def rename_context_folder(root: Path, old: str, new: str, dry_run: bool = False, missing_ok: bool = False) -> RenameResult:
    old = validate_slug(old, "old context folder")
    new = validate_slug(new, "new context folder")
    root = root.expanduser().resolve()
    if old == new:
        print(f"no-op context rename: {old}")
        return RenameResult(moved=False, merged=False, rewritten_files=())
    moved, merged = move_or_merge_folder(root, old, new, dry_run, missing_ok)
    rename_inside_folder_note(root, old, new, dry_run)
    rewritten_files = rewrite_structured_references(root, old, new, dry_run)
    if dry_run:
        print(f"[dry-run] {len(rewritten_files)} files would be rewritten")
    else:
        print(f"{len(rewritten_files)} files rewritten")
    return RenameResult(moved=moved, merged=merged, rewritten_files=rewritten_files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rename a context folder and rewrite structured references.")
    parser.add_argument("old_slug", help="Existing context folder slug.")
    parser.add_argument("new_slug", help="New context folder slug.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without modifying files.")
    parser.add_argument("--missing-ok", action="store_true", help="Do not fail if the old folder is already gone.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    rename_context_folder(root, args.old_slug, args.new_slug, args.dry_run, args.missing_ok)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
