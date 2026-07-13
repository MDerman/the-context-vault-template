#!/usr/bin/env python3
"""Publish SemVer releases for the public vault export."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


DEFAULT_REPO_URL = "https://github.com/MDerman/the-context-vault-template.git"
RELEASE_PATH = Path("_master/system/bootstrap/state/release.json")
LOCK_PATH = Path("_master/system/config/dependencies.lock.json")
DEPS_PATH = Path("_master/system/config/deps.json")
BREWFILE_PATH = Path("_master/system/bootstrap/Brewfile")
EXPORT_CONFIG_PATH = Path("_master/system/bootstrap/bootstrap-export.json")
BOOTSTRAP_EXPORT = Path("_master/system/scripts/bootstrap_export.py")
SEMVER_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def tag(self) -> str:
        return f"v{self.version}"


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"command failed: {' '.join(args)}\n{detail}")
    return result


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(payload))


def parse_semver(value: str | None) -> SemVer | None:
    if not value:
        return None
    match = SEMVER_RE.match(value.strip())
    if not match:
        return None
    return SemVer(*(int(part) for part in match.groups()))


def bump_semver(current: SemVer | None, bump: str) -> SemVer:
    if current is None:
        return SemVer(0, 1, 0)
    if bump == "major":
        return SemVer(current.major + 1, 0, 0)
    if bump == "minor":
        return SemVer(current.major, current.minor + 1, 0)
    if bump == "patch":
        return SemVer(current.major, current.minor, current.patch + 1)
    raise SystemExit(f"Unknown bump: {bump}")


def brewfile_entries(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not path.exists():
        return entries
    pattern = re.compile(r'^\s*(brew|cask)\s+"([^"]+)"')
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            entries.append({"type": match.group(1), "name": match.group(2)})
    return entries


def installed_brew_version(entry: dict[str, str]) -> str | None:
    brew = shutil.which("brew")
    if not brew:
        return None
    args = [brew, "list"]
    if entry["type"] == "cask":
        args.append("--cask")
    args.extend(["--versions", entry["name"]])
    result = run(args, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    parts = result.stdout.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def gh_version() -> dict[str, Any]:
    gh = shutil.which("gh")
    if not gh:
        return {"available": False, "version": None, "skill_available": False}
    version = run([gh, "--version"], check=False).stdout.splitlines()
    return {
        "available": True,
        "version": version[0] if version else None,
        "skill_available": run([gh, "skill", "--help"], check=False).returncode == 0,
    }


def git_ls_remote(repo_url: str, ref: str) -> str | None:
    refs = [f"refs/heads/{ref}", f"refs/tags/{ref}", ref]
    for candidate in refs:
        result = run(["git", "ls-remote", repo_url, candidate], check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0]
    return None


def dependency_repo_locks(root: Path) -> list[dict[str, Any]]:
    data = read_json(root / DEPS_PATH, {"repos": []})
    locks: list[dict[str, Any]] = []
    for item in data.get("repos", []):
        repo_url = str(item["url"])
        ref = str(item.get("ref") or "main")
        resolved = git_ls_remote(repo_url, ref)
        if not resolved:
            raise SystemExit(f"Could not resolve dependency ref {ref} for {repo_url}")
        locks.append(
            {
                "id": item["id"],
                "url": repo_url,
                "path": item.get("path"),
                "ref": ref,
                "resolved_commit": resolved,
            }
        )
    return sorted(locks, key=lambda item: str(item["id"]))


def obsidian_plugin_locks(root: Path) -> list[dict[str, Any]]:
    locks: list[dict[str, Any]] = []
    for profile in [".obsidian", ".obsidian-mobile"]:
        plugins_root = root / profile / "plugins"
        if not plugins_root.is_dir():
            continue
        for manifest in sorted(plugins_root.glob("*/manifest.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            locks.append(
                {
                    "profile": profile,
                    "plugin": manifest.parent.name,
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "version": data.get("version"),
                    "manifest_path": manifest.relative_to(root).as_posix(),
                }
            )
    return locks


def dependency_lock(root: Path, version: SemVer, generated_at: str) -> dict[str, Any]:
    brew_entries = []
    for entry in brewfile_entries(root / BREWFILE_PATH):
        brew_entries.append(
            {
                **entry,
                "installed_version": installed_brew_version(entry),
            }
        )
    return {
        "schema_version": 1,
        "release_version": version.version,
        "release_tag": version.tag,
        "generated_at": generated_at,
        "homebrew": brew_entries,
        "external_repos": dependency_repo_locks(root),
        "obsidian_plugins": obsidian_plugin_locks(root),
        "github_cli": gh_version(),
    }


def load_export_root(root: Path) -> Path:
    config = read_json(root / EXPORT_CONFIG_PATH)
    return Path(os.path.expanduser(str(config["export_root"]))).resolve()


def release_payload(version: SemVer, generated_at: str, lock_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "version": version.version,
        "tag": version.tag,
        "repo_url": DEFAULT_REPO_URL,
        "channel": "public-bootstrap",
        "released_at": generated_at,
        "dependency_lock_path": LOCK_PATH.as_posix(),
        "dependency_lock_sha256": lock_sha,
        "notes": f"Public bootstrap release {version.tag}.",
    }


def gh_release_tags(repo_url: str) -> list[SemVer]:
    result = run(
        ["gh", "release", "list", "--repo", repo_slug(repo_url), "--limit", "100", "--json", "tagName"],
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    tags: list[SemVer] = []
    for item in json.loads(result.stdout):
        parsed = parse_semver(item.get("tagName"))
        if parsed:
            tags.append(parsed)
    return tags


def remote_tags(repo_url: str) -> list[SemVer]:
    result = run(["git", "ls-remote", "--tags", repo_url, "refs/tags/v*"], check=False)
    if result.returncode != 0:
        return []
    tags: list[SemVer] = []
    for line in result.stdout.splitlines():
        ref = line.split()[-1].removeprefix("refs/tags/").removesuffix("^{}")
        parsed = parse_semver(ref)
        if parsed:
            tags.append(parsed)
    return tags


def latest_public_version(repo_url: str, local_release: dict[str, Any]) -> SemVer | None:
    candidates = gh_release_tags(repo_url) + remote_tags(repo_url)
    if candidates:
        return max(candidates)
    return parse_semver(str(local_release.get("version") or ""))


def repo_slug(repo_url: str) -> str:
    value = repo_url.removesuffix(".git")
    if value.startswith("https://github.com/"):
        return value.removeprefix("https://github.com/")
    if value.startswith("git@github.com:"):
        return value.removeprefix("git@github.com:")
    return value


def ensure_tools() -> None:
    for tool in ["git", "gh"]:
        if not shutil.which(tool):
            raise SystemExit(f"Missing required command: {tool}")
    auth = run(["gh", "auth", "status", "--hostname", "github.com"], check=False)
    if auth.returncode != 0:
        detail = auth.stderr.strip() or auth.stdout.strip()
        raise SystemExit(f"GitHub CLI is not authenticated.\n{detail}")


def ensure_public_repo(public_root: Path, repo_url: str) -> str:
    if not (public_root / ".git").exists():
        raise SystemExit(f"Public export root is not a Git repo: {public_root}")
    branch = run(["git", "branch", "--show-current"], cwd=public_root).stdout.strip()
    if not branch:
        raise SystemExit("Public repo is not on a branch.")
    remote = run(["git", "remote", "get-url", "origin"], cwd=public_root).stdout.strip()
    if remote.removesuffix(".git") != repo_url.removesuffix(".git"):
        raise SystemExit(f"Unexpected public repo origin: {remote}")
    status = run(["git", "status", "--short"], cwd=public_root).stdout.strip()
    if status:
        raise SystemExit(f"Public repo has uncommitted changes:\n{status}")
    return branch


def ensure_version_available(repo_url: str, version: SemVer) -> None:
    tag_exists = run(["git", "ls-remote", "--tags", repo_url, f"refs/tags/{version.tag}"], check=False)
    if tag_exists.returncode == 0 and tag_exists.stdout.strip():
        raise SystemExit(f"Tag already exists: {version.tag}")
    release_exists = run(["gh", "release", "view", version.tag, "--repo", repo_slug(repo_url)], check=False)
    if release_exists.returncode == 0:
        raise SystemExit(f"GitHub release already exists: {version.tag}")


def choose_version(root: Path, args: argparse.Namespace) -> SemVer:
    release = read_json(root / RELEASE_PATH, {})
    current = latest_public_version(DEFAULT_REPO_URL, release)
    if args.version:
        version = parse_semver(args.version)
        if not version:
            raise SystemExit(f"Invalid SemVer version: {args.version}")
    else:
        version = bump_semver(current, args.bump)
    ensure_version_available(DEFAULT_REPO_URL, version)
    if current and version <= current:
        raise SystemExit(f"Version must be newer than latest public version {current.tag}: {version.tag}")
    return version


def print_plan(version: SemVer, public_root: Path, lock_sha: str, branch: str) -> None:
    print(f"version: {version.version}")
    print(f"tag: {version.tag}")
    print(f"public repo: {public_root}")
    print(f"public branch: {branch}")
    print(f"dependency lock sha256: {lock_sha}")
    print("actions:")
    print(f"  write {RELEASE_PATH}")
    print(f"  write {LOCK_PATH}")
    print("  vault bootstrap-export --force")
    print(f"  git commit -m 'Release {version.tag}'")
    print(f"  git tag -a {version.tag}")
    print("  git push origin branch")
    print(f"  git push origin {version.tag}")
    print(f"  gh release create {version.tag} --verify-tag")


def publish(root: Path, args: argparse.Namespace) -> int:
    ensure_tools()
    public_root = load_export_root(root)
    branch = ensure_public_repo(public_root, DEFAULT_REPO_URL)
    version = choose_version(root, args)
    generated_at = utc_iso()
    lock = dependency_lock(root, version, generated_at)
    lock_sha = hashlib.sha256(json_bytes(lock)).hexdigest()
    release = release_payload(version, generated_at, lock_sha)
    print_plan(version, public_root, lock_sha, branch)
    if args.dry_run:
        print("dry run: no files, commits, tags, pushes, or releases changed.")
        return 0

    write_json(root / LOCK_PATH, lock)
    write_json(root / RELEASE_PATH, release)
    run([sys.executable, str(root / BOOTSTRAP_EXPORT), "--force", "--root", str(root)], cwd=root)

    status = run(["git", "status", "--short"], cwd=public_root).stdout.strip()
    if not status:
        raise SystemExit("Public export produced no changes; refusing empty release commit.")
    run(["git", "add", "-A"], cwd=public_root)
    run(["git", "commit", "-m", f"Release {version.tag}"], cwd=public_root)
    commit = run(["git", "rev-parse", "HEAD"], cwd=public_root).stdout.strip()
    run(["git", "tag", "-a", version.tag, "-m", f"Release {version.tag}", commit], cwd=public_root)
    run(["git", "push", "origin", branch], cwd=public_root)
    run(["git", "push", "origin", version.tag], cwd=public_root)
    run(
        [
            "gh",
            "release",
            "create",
            version.tag,
            "--repo",
            repo_slug(DEFAULT_REPO_URL),
            "--title",
            f"Release {version.tag}",
            "--notes",
            f"Public vault release {version.tag}.",
            "--verify-tag",
        ],
        cwd=public_root,
    )
    print(f"published {version.tag} at {commit}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish public vault SemVer releases.")
    subparsers = parser.add_subparsers(dest="command")
    publish_parser = subparsers.add_parser("publish", help="Export, commit, tag, push, and create GitHub release.")
    mode = publish_parser.add_mutually_exclusive_group()
    mode.add_argument("--bump", choices=["patch", "minor", "major"], default="patch", help="Version bump.")
    mode.add_argument("--version", help="Explicit SemVer version, with or without v prefix.")
    publish_parser.add_argument("--dry-run", action="store_true", help="Preview release actions without changes.")
    publish_parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(getattr(args, "root", None), __file__)
    if args.command == "publish":
        return publish(root, args)
    print("Use `vault release publish --dry-run` or `vault release publish --bump patch`.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
