#!/usr/bin/env python3
"""Find persisted vault-root paths that make the vault non-portable."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from script_utils import LEGACY_VAULT_ROOT_PREFIXES, resolve_vault_root


SKIP_DIRS = {
    ".git",
    "node_modules",
    "secrets",
    "secret",
    "kubeconfig",
    "kubeconfigs",
}
SKIP_FILE_PREFIXES = (".env",)
SKIP_PATHS = {".obsidian/plugins/context-nine/data.json"}
SKIP_PATH_PREFIXES = (".obsidian/plugins/system3-relay/",)


def is_skipped(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    path_string = path.as_posix()
    if path_string in SKIP_PATHS or path_string.startswith(SKIP_PATH_PREFIXES):
        return True
    return any(path.name.startswith(prefix) for prefix in SKIP_FILE_PREFIXES)


def is_probably_text(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in chunk


def banned_patterns(root: Path) -> list[str]:
    patterns = [prefix.rstrip("/") for prefix in LEGACY_VAULT_ROOT_PREFIXES]
    home = Path.home().as_posix()
    root_absolute = root.as_posix()
    patterns.append(root_absolute)
    if root_absolute.startswith(home + "/"):
        patterns.append("~/" + root_absolute.removeprefix(home + "/"))
    return sorted(set(patterns), key=len, reverse=True)


def scan(root: Path) -> list[tuple[str, int, str]]:
    patterns = banned_patterns(root)
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if is_skipped(relative) or not path.is_file() or not is_probably_text(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern in line for pattern in patterns):
                hits.append((relative.as_posix(), line_number, line.strip()))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find non-portable vault-root path references.")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    hits = scan(root)
    if hits:
        for path, line_number, line in hits:
            print(f"{path}:{line_number}: {line}")
        print(f"{len(hits)} non-portable vault path reference(s) found.", file=sys.stderr)
        return 1
    print("No non-portable vault path references found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
