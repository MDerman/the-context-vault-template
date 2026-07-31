#!/usr/bin/env python3
"""Validate and materialize centrally managed text snippets across repositories."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import difflib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any

from vault_layout import CONFIG_DIR, VAULT_ROOT


ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MARKER_RE = re.compile(r"^<!-- snippet:([a-z0-9]+(?:-[a-z0-9]+)*):(start|end) -->$")
MARKER_PREFIX = "<!-- snippet:"


class SnippetError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    snippet_id: str
    source: Path
    content: str
    repository: str
    path: str


@dataclass(frozen=True)
class Block:
    body_start: int
    body_end: int
    newline: str


@dataclass
class Inspection:
    repository: str
    path: str
    target_path: Path | None
    original: str | None
    rendered: str | None
    dirty: bool
    statuses: dict[str, str]
    error: str | None = None


def read_json(path: Path, *, required: bool) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if not required:
            return {}
        raise SnippetError(f"configuration missing: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        raise SnippetError(f"cannot read configuration {path}: {exc}") from exc


def safe_relative_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SnippetError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise SnippetError(f"unsafe {label}: {value!r}")
    return path.as_posix()


def validate_target(value: Any, *, snippet_id: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise SnippetError(f"target for {snippet_id!r} must be an object")
    repository = value.get("repository")
    if not isinstance(repository, str) or not ID_RE.fullmatch(repository):
        raise SnippetError(f"invalid repository id for {snippet_id!r}: {repository!r}")
    path = safe_relative_path(value.get("path"), label=f"target path for {snippet_id!r}")
    return repository, path


def load_targets(config_dir: Path) -> list[Target]:
    defaults = read_json(config_dir / "defaults.json", required=True)
    if defaults.get("schema_version") != 1 or not isinstance(defaults.get("snippets"), dict):
        raise SnippetError("snippet defaults must use schema_version 1 and contain a snippets object")
    private = read_json(config_dir / "private/targets.json", required=False)
    if private and (
        private.get("schema_version") != 1 or not isinstance(private.get("targets"), dict)
    ):
        raise SnippetError("private snippet targets must use schema_version 1 and contain a targets object")

    extra_targets = private.get("targets", {}) if private else {}
    unknown = sorted(set(extra_targets) - set(defaults["snippets"]))
    if unknown:
        raise SnippetError(f"private targets reference unknown snippets: {', '.join(unknown)}")

    targets: list[Target] = []
    seen: set[tuple[str, str, str]] = set()
    for snippet_id, definition in defaults["snippets"].items():
        if not isinstance(snippet_id, str) or not ID_RE.fullmatch(snippet_id):
            raise SnippetError(f"invalid snippet id: {snippet_id!r}")
        if not isinstance(definition, dict):
            raise SnippetError(f"definition for {snippet_id!r} must be an object")
        source_rel = safe_relative_path(
            definition.get("source"), label=f"source path for {snippet_id!r}"
        )
        source_candidate = config_dir / source_rel
        if source_candidate.is_symlink():
            raise SnippetError(f"snippet source must be a physical file: {source_candidate}")
        source = source_candidate.resolve()
        config_root = config_dir.resolve()
        if not source.is_relative_to(config_root):
            raise SnippetError(f"source escapes snippet config: {source_rel}")
        if source.is_symlink() or not source.is_file():
            raise SnippetError(f"snippet source must be a physical file: {source}")
        source_text = source.read_text(encoding="utf-8")
        if not source_text.strip():
            raise SnippetError(f"snippet source is empty: {source}")
        if MARKER_PREFIX in source_text:
            raise SnippetError(f"snippet source may not contain managed markers: {source}")

        configured = definition.get("targets", [])
        if not isinstance(configured, list):
            raise SnippetError(f"targets for {snippet_id!r} must be a list")
        private_configured = extra_targets.get(snippet_id, [])
        if not isinstance(private_configured, list):
            raise SnippetError(f"private targets for {snippet_id!r} must be a list")
        for raw_target in [*configured, *private_configured]:
            repository, path = validate_target(raw_target, snippet_id=snippet_id)
            key = (snippet_id, repository, path)
            if key in seen:
                raise SnippetError(
                    f"duplicate target for {snippet_id!r}: {repository}:{path}"
                )
            seen.add(key)
            targets.append(Target(snippet_id, source, source_text, repository, path))
    return targets


def load_repository_paths(registry_path: Path) -> dict[str, Path]:
    data = read_json(registry_path, required=True)
    repositories = data.get("repositories")
    if not isinstance(repositories, dict):
        raise SnippetError(f"repository registry has no repositories object: {registry_path}")
    resolved: dict[str, Path] = {}
    for repository_id, config in repositories.items():
        if not isinstance(config, dict) or not config.get("path"):
            continue
        resolved[repository_id] = Path(os.path.expanduser(str(config["path"]))).resolve()
    return resolved


def repository_root(
    repository: str,
    *,
    vault_root: Path,
    repository_paths: dict[str, Path],
) -> Path:
    root = vault_root.resolve() if repository == "vault" else repository_paths.get(repository)
    if root is None:
        raise SnippetError(f"repository is not configured: {repository}")
    if not root.is_dir():
        raise SnippetError(f"repository checkout is unavailable: {repository} ({root})")
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SnippetError(f"target is not a Git checkout: {repository} ({root})")
    actual = Path(result.stdout.strip()).resolve()
    if actual != root:
        raise SnippetError(f"repository path is not its Git root: {repository} ({root})")
    return root


def parse_blocks(text: str, *, path: Path) -> dict[str, Block]:
    blocks: dict[str, Block] = {}
    open_id: str | None = None
    body_start = 0
    newline = "\n"
    offset = 0
    for line in text.splitlines(keepends=True):
        marker_text = line.rstrip("\r\n")
        match = MARKER_RE.fullmatch(marker_text)
        if MARKER_PREFIX in marker_text and not match:
            raise SnippetError(f"malformed snippet marker in {path}: {marker_text!r}")
        if match:
            snippet_id, kind = match.groups()
            if kind == "start":
                if open_id is not None:
                    raise SnippetError(f"nested snippet markers in {path}: {open_id!r}, {snippet_id!r}")
                if snippet_id in blocks:
                    raise SnippetError(f"duplicate snippet block in {path}: {snippet_id!r}")
                if not line.endswith(("\n", "\r\n")):
                    raise SnippetError(f"snippet start marker must end with a newline in {path}")
                open_id = snippet_id
                body_start = offset + len(line)
                newline = "\r\n" if line.endswith("\r\n") else "\n"
            else:
                if open_id is None:
                    raise SnippetError(f"unmatched snippet end marker in {path}: {snippet_id!r}")
                if open_id != snippet_id:
                    raise SnippetError(
                        f"mismatched snippet markers in {path}: {open_id!r}, {snippet_id!r}"
                    )
                blocks[snippet_id] = Block(body_start, offset, newline)
                open_id = None
        offset += len(line)
    if open_id is not None:
        raise SnippetError(f"unclosed snippet block in {path}: {open_id!r}")
    return blocks


def rendered_body(source_text: str, newline: str) -> str:
    text = source_text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n").replace("\n", newline) + newline


def target_is_dirty(root: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", relative_path],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return bool(result.stdout.strip())


def inspect_targets(
    targets: list[Target],
    *,
    vault_root: Path,
    registry_path: Path,
) -> list[Inspection]:
    needs_external = any(target.repository != "vault" for target in targets)
    repository_paths = load_repository_paths(registry_path) if needs_external else {}
    grouped: dict[tuple[str, str], list[Target]] = defaultdict(list)
    for target in targets:
        grouped[(target.repository, target.path)].append(target)

    inspections: list[Inspection] = []
    for (repository, relative_path), group in sorted(grouped.items()):
        try:
            root = repository_root(
                repository, vault_root=vault_root, repository_paths=repository_paths
            )
            target_candidate = root / relative_path
            if target_candidate.is_symlink():
                raise SnippetError(
                    f"target must be a physical existing file: {repository}:{relative_path}"
                )
            target_path = target_candidate.resolve()
            if not target_path.is_relative_to(root):
                raise SnippetError(f"target escapes repository: {repository}:{relative_path}")
            if target_path.is_symlink() or not target_path.is_file():
                raise SnippetError(
                    f"target must be a physical existing file: {repository}:{relative_path}"
                )
            original = target_path.read_text(encoding="utf-8")
            blocks = parse_blocks(original, path=target_path)
            replacements: list[tuple[int, int, str]] = []
            statuses: dict[str, str] = {}
            for target in group:
                block = blocks.get(target.snippet_id)
                if block is None:
                    raise SnippetError(
                        f"missing snippet markers for {target.snippet_id!r} in "
                        f"{repository}:{relative_path}"
                    )
                expected = rendered_body(target.content, block.newline)
                current = original[block.body_start:block.body_end]
                statuses[target.snippet_id] = "current" if current == expected else "stale"
                replacements.append((block.body_start, block.body_end, expected))
            rendered = original
            for start, end, replacement in sorted(replacements, reverse=True):
                rendered = rendered[:start] + replacement + rendered[end:]
            inspections.append(
                Inspection(
                    repository,
                    relative_path,
                    target_path,
                    original,
                    rendered,
                    target_is_dirty(root, relative_path),
                    statuses,
                )
            )
        except (OSError, subprocess.SubprocessError, SnippetError) as exc:
            inspections.append(
                Inspection(repository, relative_path, None, None, None, False, {}, str(exc))
            )
    return inspections


def select_targets(
    targets: list[Target], snippet_ids: list[str], repositories: list[str]
) -> list[Target]:
    known_ids = {target.snippet_id for target in targets}
    requested_ids = set(snippet_ids)
    unknown_ids = sorted(requested_ids - known_ids)
    if unknown_ids:
        raise SnippetError(f"unknown snippets: {', '.join(unknown_ids)}")
    selected = [
        target
        for target in targets
        if (not requested_ids or target.snippet_id in requested_ids)
        and (not repositories or target.repository in repositories)
    ]
    if not selected:
        raise SnippetError("no snippet targets matched the requested filters")
    return selected


def records(inspections: list[Inspection]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for inspection in inspections:
        if inspection.error:
            result.append(
                {
                    "repository": inspection.repository,
                    "path": inspection.path,
                    "status": "error",
                    "dirty": False,
                    "error": inspection.error,
                }
            )
            continue
        for snippet_id, status_value in sorted(inspection.statuses.items()):
            result.append(
                {
                    "snippet": snippet_id,
                    "repository": inspection.repository,
                    "path": inspection.path,
                    "status": status_value,
                    "dirty": inspection.dirty,
                }
            )
    return result


def print_records(payload: list[dict[str, Any]]) -> None:
    for item in payload:
        location = f"{item['repository']}:{item['path']}"
        dirty = " dirty" if item.get("dirty") else ""
        snippet = f" {item['snippet']}" if item.get("snippet") else ""
        detail = f" ({item['error']})" if item.get("error") else ""
        print(f"{item['status']:<7}{dirty:<6} {location}{snippet}{detail}")


def write_atomic(inspections: list[Inspection]) -> None:
    pending: list[tuple[Inspection, Path]] = []
    try:
        for inspection in inspections:
            if inspection.original == inspection.rendered:
                continue
            assert inspection.target_path and inspection.original is not None and inspection.rendered is not None
            mode = stat.S_IMODE(inspection.target_path.stat().st_mode)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=inspection.target_path.parent, delete=False
            ) as handle:
                handle.write(inspection.rendered)
                temporary = Path(handle.name)
            temporary.chmod(mode)
            pending.append((inspection, temporary))
        for inspection, _ in pending:
            assert inspection.target_path and inspection.original is not None
            if inspection.target_path.read_text(encoding="utf-8") != inspection.original:
                raise SnippetError(
                    f"target changed concurrently; no snippets applied: "
                    f"{inspection.repository}:{inspection.path}"
                )
        for inspection, temporary in pending:
            assert inspection.target_path
            temporary.replace(inspection.target_path)
    finally:
        for _, temporary in pending:
            temporary.unlink(missing_ok=True)


def command_list(args: argparse.Namespace, targets: list[Target]) -> int:
    selected = select_targets(targets, [], args.repository)
    inspections = inspect_targets(
        selected, vault_root=args.root, registry_path=args.repository_registry
    )
    payload = records(inspections)
    if args.json:
        print(json.dumps({"targets": payload}, indent=2))
    else:
        print_records(payload)
    return 1 if any(item["status"] == "error" for item in payload) else 0


def command_check(args: argparse.Namespace, targets: list[Target]) -> int:
    selected = select_targets(targets, args.snippet_ids, args.repository)
    inspections = inspect_targets(
        selected, vault_root=args.root, registry_path=args.repository_registry
    )
    payload = records(inspections)
    ok = all(item["status"] == "current" for item in payload)
    if args.json:
        print(json.dumps({"ok": ok, "targets": payload}, indent=2))
    else:
        print_records(payload)
    return 0 if ok else 1


def command_sync(args: argparse.Namespace, targets: list[Target]) -> int:
    selected = select_targets(targets, args.snippet_ids, args.repository)
    inspections = inspect_targets(
        selected, vault_root=args.root, registry_path=args.repository_registry
    )
    payload = records(inspections)
    if any(item["status"] == "error" for item in payload):
        print_records(payload)
        return 1
    changed = [item for item in inspections if item.original != item.rendered]
    if not args.apply:
        for inspection in changed:
            assert inspection.original is not None and inspection.rendered is not None
            print(
                "".join(
                    difflib.unified_diff(
                        inspection.original.splitlines(keepends=True),
                        inspection.rendered.splitlines(keepends=True),
                        fromfile=f"{inspection.repository}:{inspection.path}",
                        tofile=f"{inspection.repository}:{inspection.path}",
                    )
                ),
                end="",
            )
        print(f"DRY RUN: {len(changed)} file(s) would change.")
        return 0
    try:
        write_atomic(inspections)
    except SnippetError as exc:
        print(f"Snippet sync failed: {exc}", file=sys.stderr)
        return 1
    for inspection in inspections:
        state = "updated" if inspection in changed else "current"
        dirty = " (target already had local changes)" if inspection.dirty else ""
        print(f"{state}: {inspection.repository}:{inspection.path}{dirty}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=VAULT_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--config-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--repository-registry", type=Path, default=None, help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list configured targets and current status")
    list_parser.add_argument("--repo", dest="repository", action="append", default=[])
    list_parser.add_argument("--json", action="store_true")

    check_parser = subparsers.add_parser("check", help="fail when selected snippets are not current")
    check_parser.add_argument("snippet_ids", nargs="*")
    check_parser.add_argument("--repo", dest="repository", action="append", default=[])
    check_parser.add_argument("--json", action="store_true")

    sync_parser = subparsers.add_parser("sync", help="preview or apply canonical snippet content")
    sync_parser.add_argument("snippet_ids", nargs="*")
    sync_parser.add_argument("--repo", dest="repository", action="append", default=[])
    mode = sync_parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.root = args.root.expanduser().resolve()
    args.config_dir = (
        args.config_dir.expanduser().resolve()
        if args.config_dir
        else args.root / CONFIG_DIR / "snippets"
    )
    args.repository_registry = (
        args.repository_registry.expanduser().resolve()
        if args.repository_registry
        else args.root / CONFIG_DIR / "infra-code-folder-and-computer-topology/private/repositories.json"
    )
    try:
        targets = load_targets(args.config_dir)
        if args.command == "list":
            return command_list(args, targets)
        if args.command == "check":
            return command_check(args, targets)
        return command_sync(args, targets)
    except (OSError, subprocess.SubprocessError, SnippetError) as exc:
        print(f"Snippet error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
