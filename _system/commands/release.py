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
from vault_layout import (
    BOOTSTRAP_DIR,
    DEPENDENCY_LOCK_PATH,
    RELEASE_PATH,
    VAULT_PACKAGE_MANIFEST_PATH,
)


DEFAULT_REPO_URL = "https://github.com/MDerman/the-context-vault-template.git"
SKILLS_REPO_URL = "https://github.com/MDerman/the-skill-problem-system.git"
SKILLS_RELEASE_PATH = Path("_system/agents/_package/export/release.json")
SKILLS_EXPORT_CONFIG_PATH = Path("_system/agents/_package/export/agent-package-export.json")
SKILLS_EXPORT = Path("_system/agents/_package/src/agents.py")
LOCK_PATH = DEPENDENCY_LOCK_PATH
PACKAGE_MANIFEST_PATH = VAULT_PACKAGE_MANIFEST_PATH
EXPORT_CONFIG_PATH = BOOTSTRAP_DIR / "bootstrap-export.json"
BOOTSTRAP_EXPORT = Path("_system/commands/bootstrap_export.py")
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


def installed_brew_version(manager: str, name: str) -> str | None:
    brew = shutil.which("brew")
    if not brew:
        return None
    args = [brew, "list"]
    if manager == "brew-cask":
        args.append("--cask")
    args.extend(["--versions", name])
    result = run(args, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    parts = result.stdout.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def gh_version() -> dict[str, Any]:
    gh = shutil.which("gh")
    if not gh:
        return {"available": False, "version": None}
    version = run([gh, "--version"], check=False).stdout.splitlines()
    return {
        "available": True,
        "version": version[0] if version else None,
    }


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
    manifest = read_json(root / PACKAGE_MANIFEST_PATH, {"packages": []})
    vault_packages = []
    for package in manifest.get("packages", []):
        recipe = package.get("platforms", {}).get("macos", {})
        manager = str(recipe.get("manager") or "")
        name = str(recipe.get("package") or "")
        vault_packages.append(
            {
                "id": package.get("id"),
                "manager": manager,
                "package": name,
                "installed_version": installed_brew_version(manager, name)
                if manager in {"brew", "brew-cask"} and name
                else None,
            }
        )
    return {
        "schema_version": 1,
        "release_version": version.version,
        "release_tag": version.tag,
        "generated_at": generated_at,
        "vault_packages": vault_packages,
        "obsidian_plugins": obsidian_plugin_locks(root),
        "github_cli": gh_version(),
    }


def load_export_root(root: Path) -> Path:
    config = read_json(root / EXPORT_CONFIG_PATH)
    return Path(os.path.expanduser(str(config["export_root"]))).resolve()


def load_skills_export_root(root: Path) -> Path:
    config = read_json(root / SKILLS_EXPORT_CONFIG_PATH)
    return Path(os.path.expanduser(str(config["default_export_root"]))).resolve()


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
    if repo_slug(remote) != repo_slug(repo_url):
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
    return choose_product_version(root, args, DEFAULT_REPO_URL, RELEASE_PATH)


def choose_product_version(
    root: Path,
    args: argparse.Namespace,
    repo_url: str,
    release_path: Path,
) -> SemVer:
    release = read_json(root / release_path, {})
    unpublished = release.get("repository") is None and not release.get("published_at") and not release.get("released_at")
    current = None if unpublished else latest_public_version(repo_url, release)
    if args.version:
        version = parse_semver(args.version)
        if not version:
            raise SystemExit(f"Invalid SemVer version: {args.version}")
    else:
        version = bump_semver(current, args.bump)
    ensure_version_available(repo_url, version)
    if current and version <= current:
        raise SystemExit(f"Version must be newer than latest public version {current.tag}: {version.tag}")
    return version


@dataclass(frozen=True)
class Product:
    name: str
    repo_url: str
    public_root: Path
    release_path: Path


def products(root: Path, selected: str) -> list[Product]:
    values = {
        "vault": Product("vault", DEFAULT_REPO_URL, load_export_root(root), RELEASE_PATH),
        "skills": Product("skills", SKILLS_REPO_URL, load_skills_export_root(root), SKILLS_RELEASE_PATH),
    }
    return list(values.values()) if selected == "all" else [values[selected]]


def exported_fingerprint(root: Path, product: Product) -> dict[str, str]:
    ignored = {
        "vault": {"_system/local/state/export-manifest.json", RELEASE_PATH.as_posix(), LOCK_PATH.as_posix()},
        "skills": {MANIFEST for MANIFEST in [".ctx9-agent-export-manifest.json", "release.json"]},
    }[product.name]
    result: dict[str, str] = {}
    if not root.is_dir():
        return result
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if ".git" in path.relative_to(root).parts or relative in ignored or not path.is_file():
            continue
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def stage_export(root: Path, product: Product, destination: Path) -> None:
    if product.name == "vault":
        run(
            [sys.executable, str(root / BOOTSTRAP_EXPORT), "--force", "--root", str(root), "--export-root", str(destination)],
            cwd=root,
        )
    else:
        run(
            [sys.executable, str(root / SKILLS_EXPORT), "export", "--destination", str(destination), "--apply"],
            cwd=root,
        )


def has_meaningful_changes(root: Path, product: Product) -> bool:
    import tempfile

    with tempfile.TemporaryDirectory(prefix=f"ctx9-release-{product.name}-") as temporary:
        stage = Path(temporary) / "export"
        stage_export(root, product, stage)
        return exported_fingerprint(stage, product) != exported_fingerprint(product.public_root, product)


def write_product_release(root: Path, product: Product, version: SemVer, generated_at: str) -> None:
    if product.name == "vault":
        lock = dependency_lock(root, version, generated_at)
        lock_sha = hashlib.sha256(json_bytes(lock)).hexdigest()
        write_json(root / LOCK_PATH, lock)
        write_json(root / RELEASE_PATH, release_payload(version, generated_at, lock_sha))
        run([sys.executable, str(root / BOOTSTRAP_EXPORT), "--force", "--root", str(root)], cwd=root)
        return
    write_json(
        root / SKILLS_RELEASE_PATH,
        {
            "schema_version": 1,
            "version": version.version,
            "tag": version.tag,
            "published_at": generated_at,
            "repository": SKILLS_REPO_URL,
        },
    )
    run(
        [sys.executable, str(root / SKILLS_EXPORT), "export", "--destination", str(product.public_root), "--apply"],
        cwd=root,
    )


def publish_product(root: Path, product: Product, version: SemVer, branch: str) -> None:
    write_product_release(root, product, version, utc_iso())
    status = run(["git", "status", "--short"], cwd=product.public_root).stdout.strip()
    if not status:
        raise SystemExit(f"{product.name} export produced no changes; refusing an empty release")
    run(["git", "add", "-A"], cwd=product.public_root)
    run(["git", "commit", "-m", f"Release {version.tag}"], cwd=product.public_root)
    commit = run(["git", "rev-parse", "HEAD"], cwd=product.public_root).stdout.strip()
    run(["git", "tag", "-a", version.tag, "-m", f"Release {version.tag}", commit], cwd=product.public_root)
    run(["git", "push", "origin", branch], cwd=product.public_root)
    run(["git", "push", "origin", version.tag], cwd=product.public_root)
    run(
        [
            "gh", "release", "create", version.tag,
            "--repo", repo_slug(product.repo_url),
            "--title", f"Release {version.tag}",
            "--notes", f"Public {product.name} release {version.tag}.",
            "--verify-tag",
        ],
        cwd=product.public_root,
    )
    print(f"published {product.name} {version.tag} at {commit}")


def publish(root: Path, args: argparse.Namespace) -> int:
    ensure_tools()
    selected = products(root, args.product)
    branches = {product.name: ensure_public_repo(product.public_root, product.repo_url) for product in selected}
    changed = [product for product in selected if has_meaningful_changes(root, product)]
    unchanged = sorted({product.name for product in selected} - {product.name for product in changed})
    for name in unchanged:
        print(f"{name}: unchanged, no release planned")
    planned: list[tuple[Product, SemVer]] = []
    for product in changed:
        version = choose_product_version(root, args, product.repo_url, product.release_path)
        planned.append((product, version))
        print(f"{product.name}: changed, planned {version.tag} from {product.public_root}")
    if args.dry_run:
        print("dry run: no files, commits, tags, pushes, or releases changed.")
        return 0
    for product, version in planned:
        publish_product(root, product, version, branches[product.name])
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish Context Vault and Skill Problem System releases.")
    subparsers = parser.add_subparsers(dest="command")
    publish_parser = subparsers.add_parser("publish", help="Export, commit, tag, push, and create GitHub release.")
    mode = publish_parser.add_mutually_exclusive_group()
    mode.add_argument("--bump", choices=["patch", "minor", "major"], default="patch", help="Version bump.")
    mode.add_argument("--version", help="Explicit SemVer version, with or without v prefix.")
    publish_parser.add_argument("--dry-run", action="store_true", help="Preview release actions without changes.")
    publish_parser.add_argument(
        "--product",
        choices=["vault", "skills", "all"],
        default="all",
        help="Limit publishing to one public product. Defaults to all changed products.",
    )
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
