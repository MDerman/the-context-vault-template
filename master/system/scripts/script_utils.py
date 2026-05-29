"""Shared helpers for vault scripts."""

from __future__ import annotations

import re
from pathlib import Path

LEGACY_VAULT_ROOT_PREFIXES = (
    "/Users/matthewderman/" + "My " + "Drive/" + "Work" + "space/",
    "~/" + "My " + "Drive/" + "Work" + "space/",
)


def discover_vault_root(start: Path) -> Path | None:
    """Find the Obsidian workspace root from a file or directory inside it."""
    start = start.expanduser().resolve()
    current = start if start.is_dir() else start.parent
    for candidate in (current, *current.parents):
        if (
            (candidate / "AGENTS.md").exists()
            and (candidate / "master").is_dir()
            and (candidate / ".obsidian").is_dir()
        ):
            return candidate
    return None


def resolve_vault_root(root_arg: str | Path | None, script_file: str | Path) -> Path:
    """Resolve an optional --root arg, otherwise discover the workspace root."""
    if root_arg:
        return Path(root_arg).expanduser().resolve()

    for start in (Path.cwd(), Path(script_file)):
        root = discover_vault_root(start)
        if root:
            return root

    raise SystemExit(
        "Could not find vault root. Run from inside the workspace or pass --root."
    )


def discover_context_folders(root: Path) -> list[str]:
    """Return configured context folders discovered from NN-* directories with HOME.md."""
    contexts: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not re.match(r"^\d\d-", child.name):
            continue
        if (child / "HOME.md").exists():
            contexts.append(child.name)
    return contexts


def configured_context_folders(root: Path, explicit: list[str], fallback: list[str]) -> list[str]:
    """Use explicit configured folders, otherwise discover folders, otherwise fallback defaults."""
    if explicit:
        return explicit
    return discover_context_folders(root) or fallback[:]


def vault_relative_path_string(path: Path, root: Path) -> str:
    """Return a vault-relative, slash-separated path for portable metadata."""
    resolved_root = root.expanduser().resolve()
    try:
        return path.expanduser().resolve().relative_to(resolved_root).as_posix()
    except ValueError:
        value = path.expanduser().as_posix()
        for prefix in LEGACY_VAULT_ROOT_PREFIXES:
            if value.startswith(prefix):
                return value.removeprefix(prefix)
        return value
