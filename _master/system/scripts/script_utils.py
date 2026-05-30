"""Shared helpers for vault scripts."""

from __future__ import annotations

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
            and ((candidate / "_master").is_dir() or (candidate / "master").is_dir())
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


def simple_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for raw_line in text[4:end].splitlines():
        if ":" not in raw_line or raw_line.startswith(" "):
            continue
        key, value = raw_line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def is_context_folder(path: Path) -> bool:
    if not path.is_dir() or path.name.startswith(".") or path.name.startswith("_"):
        return False
    home = path / "HOME.md"
    if not home.is_file():
        return False
    metadata = simple_frontmatter(home.read_text(encoding="utf-8", errors="replace"))
    registered = str(metadata.get("context_registered", "true")).strip().lower()
    if registered in {"false", "no", "0"}:
        return False
    return bool(metadata.get("status") or metadata.get("context_type"))


def discover_context_folders(root: Path) -> list[str]:
    """Return configured context folders discovered from HOME.md metadata."""
    contexts: list[str] = []
    for child in sorted(root.iterdir()):
        if is_context_folder(child):
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
