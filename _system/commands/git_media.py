#!/usr/bin/env python3
"""Manage pointer-only Git LFS metadata without uploading media bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


MANIFEST_REL = Path("_system/config/git-media-manifest.json")
POINTER_VERSION = "https://git-lfs.github.com/spec/v1"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
HOOK_MARKER = "vault pointer-only LFS pre-push guard"
ZERO_OID = "0" * 40

BINARY_SUFFIXES = {
    ".7z",
    ".aac",
    ".ai",
    ".arw",
    ".avi",
    ".bmp",
    ".bmpr",
    ".cr2",
    ".cr3",
    ".dng",
    ".doc",
    ".docx",
    ".eot",
    ".eps",
    ".epub",
    ".fig",
    ".flac",
    ".gif",
    ".heic",
    ".heif",
    ".ico",
    ".jam",
    ".jpeg",
    ".jpg",
    ".key",
    ".keynote",
    ".kra",
    ".m3u8",
    ".m4a",
    ".m4s",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".nef",
    ".numbers",
    ".odp",
    ".ods",
    ".odt",
    ".ogg",
    ".orf",
    ".pages",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".psd",
    ".pxd",
    ".raf",
    ".rar",
    ".raw",
    ".rw2",
    ".sketch",
    ".tif",
    ".tiff",
    ".wav",
    ".webm",
    ".webp",
    ".xls",
    ".xlsb",
    ".xlsm",
    ".xlsx",
    ".zip",
}


class GitMediaError(RuntimeError):
    """Raised when pointer-only repository invariants fail."""


def run_git(
    root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    return subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=command_env,
        check=check,
    )


def index_environment(root: Path, ref: str | None) -> tuple[dict[str, str] | None, tempfile.TemporaryDirectory[str] | None]:
    if ref is None:
        return None, None
    temporary = tempfile.TemporaryDirectory(prefix="vault-git-media-index-")
    index_path = Path(temporary.name) / "index"
    env = {"GIT_INDEX_FILE": str(index_path)}
    run_git(root, "read-tree", ref, env=env)
    return env, temporary


def tracked_index(root: Path, ref: str | None) -> tuple[list[bytes], dict[bytes, str], set[bytes]]:
    env, temporary = index_environment(root, ref)
    try:
        paths = [item for item in run_git(root, "ls-files", "-z", env=env).stdout.split(b"\0") if item]
        staged: dict[bytes, str] = {}
        for record in run_git(root, "ls-files", "-s", "-z", env=env).stdout.split(b"\0"):
            if not record:
                continue
            metadata, path = record.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            if stage == "0" and mode != "160000":
                staged[path] = oid

        request = b"\0".join(paths) + (b"\0" if paths else b"")
        attributes = run_git(
            root,
            "check-attr",
            "--cached",
            "-z",
            "--stdin",
            "filter",
            input_bytes=request,
            env=env,
        ).stdout.split(b"\0")
        lfs_paths: set[bytes] = set()
        for offset in range(0, len(attributes) - 2, 3):
            path, attribute, value = attributes[offset : offset + 3]
            if attribute == b"filter" and value == b"lfs":
                lfs_paths.add(path)
        return paths, staged, lfs_paths
    finally:
        if temporary is not None:
            temporary.cleanup()


def read_blobs(root: Path, object_ids: set[str]) -> dict[str, bytes]:
    if not object_ids:
        return {}
    request = b"".join(f"{oid}\n".encode("ascii") for oid in sorted(object_ids))
    response = run_git(root, "cat-file", "--batch", input_bytes=request).stdout
    offset = 0
    blobs: dict[str, bytes] = {}
    for _ in object_ids:
        line_end = response.find(b"\n", offset)
        if line_end < 0:
            raise GitMediaError("Truncated git cat-file response")
        header = response[offset:line_end].decode("ascii").strip()
        offset = line_end + 1
        parts = header.split()
        if len(parts) != 3 or parts[1] != "blob":
            raise GitMediaError(f"Unable to read Git blob: {header}")
        oid, _, size_text = parts
        size = int(size_text)
        blobs[oid] = response[offset : offset + size]
        offset += size
        if response[offset : offset + 1] != b"\n":
            raise GitMediaError(f"Malformed git cat-file response for {oid}")
        offset += 1
    return blobs


def parse_pointer(content: bytes, path: str) -> tuple[str, int]:
    if content == b"":
        return EMPTY_SHA256, 0
    try:
        lines = content.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GitMediaError(f"LFS path is not a pointer: {path}") from exc
    if len(lines) != 3 or lines[0] != f"version {POINTER_VERSION}":
        raise GitMediaError(f"LFS path is not a canonical pointer: {path}")
    if not lines[1].startswith("oid sha256:") or not lines[2].startswith("size "):
        raise GitMediaError(f"Malformed LFS pointer: {path}")
    oid = lines[1].removeprefix("oid sha256:")
    if len(oid) != 64 or any(character not in "0123456789abcdef" for character in oid):
        raise GitMediaError(f"Invalid pointer SHA-256: {path}")
    try:
        size = int(lines[2].removeprefix("size "))
    except ValueError as exc:
        raise GitMediaError(f"Invalid pointer size: {path}") from exc
    if size < 0:
        raise GitMediaError(f"Negative pointer size: {path}")
    return oid, size


def build_manifest(root: Path, ref: str | None) -> dict[str, object]:
    paths, staged, lfs_paths = tracked_index(root, ref)
    missing_routing: list[str] = []
    for raw_path in paths:
        path = os.fsdecode(raw_path)
        suffix = Path(path).suffix.lower()
        if suffix in BINARY_SUFFIXES and raw_path not in lfs_paths:
            missing_routing.append(path)
    if missing_routing:
        preview = "\n".join(f"  - {path}" for path in missing_routing[:20])
        raise GitMediaError(f"Binary paths are not routed through LFS:\n{preview}")

    object_ids = {staged[path] for path in lfs_paths if path in staged}
    blobs = read_blobs(root, object_ids)
    entries: list[dict[str, object]] = []
    for raw_path in sorted(lfs_paths):
        if raw_path not in staged:
            continue
        path = os.fsdecode(raw_path)
        pointer_blob = staged[raw_path]
        oid, size = parse_pointer(blobs[pointer_blob], path)
        entries.append(
            {
                "path": path,
                "sha256": oid,
                "size": size,
                "pointer_blob": pointer_blob,
            }
        )
    return {
        "schema_version": 1,
        "pointer_version": POINTER_VERSION,
        "summary": {
            "files": len(entries),
            "logical_bytes": sum(int(entry["size"]) for entry in entries),
        },
        "files": entries,
    }


def manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def read_manifest(root: Path, ref: str | None) -> dict[str, object]:
    spec = f":{MANIFEST_REL.as_posix()}" if ref is None else f"{ref}:{MANIFEST_REL.as_posix()}"
    result = run_git(root, "show", spec, check=False)
    if result.returncode != 0:
        raise GitMediaError(f"Manifest missing from {'index' if ref is None else ref}: {MANIFEST_REL}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GitMediaError(f"Manifest is invalid JSON: {MANIFEST_REL}") from exc


def lfs_object_root(root: Path) -> Path:
    result = run_git(root, "rev-parse", "--git-path", "lfs/objects")
    path = Path(result.stdout.decode().strip())
    return path if path.is_absolute() else root / path


def verify_local_objects(root: Path, manifest: dict[str, object], full_hash: bool) -> None:
    object_root = lfs_object_root(root)
    errors: list[str] = []
    for entry in manifest["files"]:
        assert isinstance(entry, dict)
        oid = str(entry["sha256"])
        expected_size = int(entry["size"])
        object_path = object_root / oid[:2] / oid[2:4] / oid
        if not object_path.is_file():
            errors.append(f"missing local object {oid} ({entry['path']})")
            continue
        if object_path.stat().st_size != expected_size:
            errors.append(f"wrong local size {oid} ({entry['path']})")
            continue
        if full_hash:
            digest = hashlib.sha256()
            with object_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != oid:
                errors.append(f"wrong local hash {oid} ({entry['path']})")
    if errors:
        preview = "\n".join(f"  - {error}" for error in errors[:20])
        raise GitMediaError(f"Local LFS object verification failed:\n{preview}")


def verify(root: Path, ref: str | None, *, local_objects: bool, full_hash: bool) -> dict[str, object]:
    expected = build_manifest(root, ref)
    stored = read_manifest(root, ref)
    if stored != expected:
        raise GitMediaError("Tracked media manifest is stale; run `vault git-media write-manifest` and stage it.")
    if local_objects:
        verify_local_objects(root, expected, full_hash)
    return expected


def install_hook(root: Path, apply: bool) -> None:
    hook_path_text = run_git(root, "rev-parse", "--git-path", "hooks/pre-push").stdout.decode().strip()
    hook_path = Path(hook_path_text)
    if not hook_path.is_absolute():
        hook_path = root / hook_path
    script = root / "_system/commands/git_media.py"
    content = (
        "#!/bin/sh\n"
        f"# {HOOK_MARKER}\n"
        'root="$(git rev-parse --show-toplevel)" || exit 2\n'
        f"exec python3 {shlex.quote(str(script))} --root \"$root\" pre-push \"$@\"\n"
    )
    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8", errors="replace")
        if HOOK_MARKER not in existing and "git lfs pre-push" not in existing:
            raise GitMediaError(f"Refusing to replace unrelated pre-push hook: {hook_path}")
    if not apply:
        print(f"DRY RUN: install pointer-only pre-push hook at {hook_path}")
        return
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(content, encoding="utf-8")
    hook_path.chmod(0o755)
    print(f"Installed pointer-only pre-push hook: {hook_path}")


def hook_is_installed(root: Path) -> bool:
    hook_path_text = run_git(root, "rev-parse", "--git-path", "hooks/pre-push").stdout.decode().strip()
    hook_path = Path(hook_path_text)
    if not hook_path.is_absolute():
        hook_path = root / hook_path
    if not hook_path.is_file():
        return False
    content = hook_path.read_text(encoding="utf-8", errors="replace")
    return HOOK_MARKER in content or "_system/commands/git_media.py" in content


def pointer_only_role(root: Path) -> str:
    identity = run_git(root, "config", "--get", "vault.machine-id", check=False).stdout.decode().strip()
    registry_path = root / "_system/config/code-folder-and-computer-topology/private/machines.json"
    if not identity or not registry_path.is_file():
        return "primary"
    try:
        registry: dict[str, Any] = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "primary"
    for machine in registry.get("machines", []):
        if machine.get("id") == identity:
            return str(machine.get("role", "primary"))
    return "primary"


def media_write_authorized(root: Path) -> bool:
    value = run_git(root, "config", "--bool", "--get", "vault.media-write-authorized", check=False)
    return value.returncode == 0 and value.stdout.decode().strip() == "true"


def stored_manifest(root: Path, ref: str) -> dict[str, object]:
    manifest = read_manifest(root, ref)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise GitMediaError(f"Manifest has unsupported structure at {ref}: {MANIFEST_REL}")
    summary = manifest.get("summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("files"), int):
        raise GitMediaError(f"Manifest summary is invalid at {ref}: {MANIFEST_REL}")
    return manifest


def changed_media_paths(root: Path, old_sha: str, new_sha: str) -> list[str]:
    if old_sha == ZERO_OID:
        result = run_git(root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", new_sha)
    else:
        result = run_git(root, "diff", "--name-only", "-z", old_sha, new_sha)
    paths = [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]
    return [
        path for path in paths
        if path == MANIFEST_REL.as_posix() or Path(path).suffix.lower() in BINARY_SUFFIXES
    ]


def pre_push(root: Path) -> None:
    updates = sys.stdin.read().splitlines()
    refs: dict[str, str] = {}
    for update in updates:
        fields = update.split()
        if len(fields) != 4:
            raise GitMediaError(f"Malformed pre-push input: {update}")
        local_sha = fields[1]
        if local_sha != ZERO_OID:
            refs[local_sha] = fields[3]
    role = pointer_only_role(root)
    authorized = media_write_authorized(root)
    for ref, old_sha in sorted(refs.items()):
        media_changes = changed_media_paths(root, old_sha, ref) if role == "worker" else []
        if media_changes and not authorized:
            preview = "\n".join(f"  - {path}" for path in media_changes[:20])
            raise GitMediaError(
                "Worker push changes LFS pointers or media manifest; media write is not authorized:\n" + preview
            )
        if role == "worker" and not media_changes:
            # Parent state was primary-verified. Avoid hydrating every pointer blob in a partial clone.
            manifest = stored_manifest(root, ref)
        else:
            manifest = verify(root, ref, local_objects=True, full_hash=False)
        print(f"Pointer-only media verified for {ref[:12]}: {manifest['summary']['files']} files.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("write-manifest", help="Write deterministic manifest from staged LFS pointers.")

    verify_parser = subparsers.add_parser("verify", help="Verify pointers, manifest, routing, and local objects.")
    verify_parser.add_argument("--ref", default="HEAD", help="Tree-ish to verify. Defaults to HEAD.")
    verify_parser.add_argument("--index", action="store_true", help="Verify staged index instead of a committed ref.")
    verify_parser.add_argument("--skip-local-objects", action="store_true", help="Do not require media bodies locally.")
    verify_parser.add_argument("--full-local-hash", action="store_true", help="Re-hash every local media body.")

    subparsers.add_parser("status", help="Show pointer-only repository status.")

    hook_parser = subparsers.add_parser("install-hook", help="Install no-upload pre-push verification hook.")
    hook_parser.add_argument("--apply", action="store_true", help="Apply instead of showing dry run.")

    pre_push_parser = subparsers.add_parser("pre-push", help=argparse.SUPPRESS)
    pre_push_parser.add_argument("remote", nargs="?")
    pre_push_parser.add_argument("remote_url", nargs="?")

    args = parser.parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    try:
        if args.command == "write-manifest":
            manifest = build_manifest(root, None)
            destination = root / MANIFEST_REL
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(manifest_bytes(manifest))
            print(f"Wrote {destination}: {manifest['summary']['files']} pointers.")
            return 0
        if args.command == "verify":
            manifest = verify(
                root,
                None if args.index else args.ref,
                local_objects=not args.skip_local_objects,
                full_hash=args.full_local_hash,
            )
            print(
                f"Pointer-only media verified: {manifest['summary']['files']} files, "
                f"{manifest['summary']['logical_bytes']} logical bytes."
            )
            return 0
        if args.command == "status":
            role = pointer_only_role(root)
            manifest = stored_manifest(root, "HEAD") if role == "worker" else verify(
                root, "HEAD", local_objects=True, full_hash=False
            )
            print(json.dumps(manifest["summary"], sort_keys=True))
            if role == "worker":
                print("worker_pointer_state=inherited; media changes are checked during pre-push")
            print(f"pre_push_hook={'installed' if hook_is_installed(root) else 'missing'}")
            return 0
        if args.command == "install-hook":
            install_hook(root, args.apply)
            return 0
        if args.command == "pre-push":
            pre_push(root)
            return 0
    except (GitMediaError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            message = exc.stderr.decode("utf-8", "replace").strip() if exc.stderr else str(exc)
        else:
            message = str(exc)
        print(f"Git media verification failed: {message}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
