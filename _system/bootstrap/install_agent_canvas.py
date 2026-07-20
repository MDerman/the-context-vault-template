#!/usr/bin/env python3
"""Build and link Agent Canvas from its editable dependency checkout."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys


CLI_DIR = Path("packages/cli")
CLI_PACKAGE = CLI_DIR / "package.json"
BUILD_FILES = (CLI_DIR / "dist/index.js", CLI_DIR / "dist/static/index.html")
PACKAGE_LINK = Path("install/global/node_modules/@agent-canvas/cli")


@dataclass
class Health:
    expected_version: str | None
    bun: Path | None
    node: Path | None
    bun_bin: Path | None
    build_ok: bool
    package_link_ok: bool
    bun_command_ok: bool
    local_command_ok: bool
    version_ok: bool
    version: str | None

    @property
    def ok(self) -> bool:
        return all(
            (
                self.expected_version,
                self.bun,
                self.node,
                self.bun_bin,
                self.build_ok,
                self.package_link_ok,
                self.bun_command_ok,
                self.local_command_ok,
                self.version_ok,
            )
        )

    def problems(self) -> list[str]:
        checks = (
            (self.expected_version, "missing CLI package metadata"),
            (self.bun, "bun unavailable"),
            (self.node, "node unavailable"),
            (self.bun_bin, "Bun global bin unavailable"),
            (self.build_ok, "dependencies or build output missing"),
            (self.package_link_ok, "Bun package link missing or stale"),
            (self.bun_command_ok, "Bun executable missing"),
            (self.local_command_ok, "~/.local/bin/agent-canvas missing or stale"),
            (self.version_ok, "CLI version mismatch or command failed"),
        )
        return [message for value, message in checks if not value]


def run(command: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, text=True, capture_output=True)


def resolves_to(path: Path, target: Path) -> bool:
    try:
        return path.resolve(strict=True) == target.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return False


def expected_version(repo: Path) -> str | None:
    try:
        value = json.loads((repo / CLI_PACKAGE).read_text())["version"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, str) and value else None


def bun_global_bin(bun: Path | None) -> Path | None:
    if not bun:
        return None
    result = run([str(bun), "pm", "bin", "-g"], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).expanduser()


def inspect(repo: Path, home: Path) -> Health:
    bun_value = shutil.which("bun")
    node_value = shutil.which("node")
    bun = Path(bun_value) if bun_value else None
    node = Path(node_value) if node_value else None
    bun_bin = bun_global_bin(bun)
    version = expected_version(repo)
    cli = repo / CLI_DIR
    build_ok = (repo / "node_modules").is_dir() and all((repo / path).is_file() for path in BUILD_FILES)

    package_link_ok = False
    bun_command_ok = False
    local_command_ok = False
    installed_version: str | None = None
    if bun_bin:
        package_link_ok = resolves_to(bun_bin.parent / PACKAGE_LINK, cli)
        bun_command = bun_bin / "agent-canvas"
        bun_command_ok = bun_command.exists()
        local_command_ok = resolves_to(home / ".local/bin/agent-canvas", bun_command)
        if bun_command_ok:
            result = run([str(bun_command), "--version"], check=False)
            if result.returncode == 0:
                installed_version = result.stdout.strip()

    return Health(
        expected_version=version,
        bun=bun,
        node=node,
        bun_bin=bun_bin,
        build_ok=build_ok,
        package_link_ok=package_link_ok,
        bun_command_ok=bun_command_ok,
        local_command_ok=local_command_ok,
        version_ok=bool(version and installed_version == version),
        version=installed_version,
    )


def print_health(health: Health) -> None:
    if health.ok:
        print(f"Agent Canvas setup: ok ({health.expected_version})")
        return
    print("Agent Canvas setup: needs-setup")
    for problem in health.problems():
        print(f"  - {problem}")


def planned_actions(health: Health, force_build: bool) -> list[str]:
    actions: list[str] = []
    if force_build or not health.build_ok or not health.version_ok:
        actions.extend(("bun install --frozen-lockfile", "bun run build"))
    if force_build or not health.package_link_ok or not health.bun_command_ok or not health.version_ok:
        actions.append("bun link (packages/cli)")
    if not health.local_command_ok:
        actions.append("link ~/.local/bin/agent-canvas to Bun global executable")
    return actions


def ensure_local_command(home: Path, bun_command: Path) -> None:
    local_command = home / ".local/bin/agent-canvas"
    local_command.parent.mkdir(parents=True, exist_ok=True)
    if local_command.exists() or local_command.is_symlink():
        if resolves_to(local_command, bun_command):
            return
        raise RuntimeError(f"refusing unrelated command conflict: {local_command}")
    local_command.symlink_to(bun_command)


def apply(repo: Path, home: Path, force_build: bool) -> None:
    health = inspect(repo, home)
    if not health.expected_version:
        raise RuntimeError(f"invalid Agent Canvas checkout: {repo}")
    if not health.bun:
        raise RuntimeError("bun unavailable")
    if not health.node:
        raise RuntimeError("node unavailable")

    build = force_build or not health.build_ok or not health.version_ok
    if build:
        for command in ([str(health.bun), "install", "--frozen-lockfile"], [str(health.bun), "run", "build"]):
            result = run(command, cwd=repo, check=False)
            if result.returncode != 0:
                output = (result.stderr or result.stdout).strip()
                raise RuntimeError(f"{' '.join(command)} failed: {output}")

    health = inspect(repo, home)
    if build or not health.package_link_ok or not health.bun_command_ok:
        result = run([str(health.bun), "link"], cwd=repo / CLI_DIR, check=False)
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"bun link failed: {output}")

    health = inspect(repo, home)
    if not health.bun_bin:
        raise RuntimeError("Bun global bin unavailable")
    bun_command = health.bun_bin / "agent-canvas"
    if not bun_command.exists():
        raise RuntimeError(f"Bun executable missing after link: {bun_command}")
    ensure_local_command(home, bun_command)

    final = inspect(repo, home)
    if not final.ok:
        raise RuntimeError("Agent Canvas verification failed: " + "; ".join(final.problems()))
    print(f"Agent Canvas setup: ok ({final.expected_version})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--force-build", action="store_true")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.expanduser().resolve()
    home = Path(os.environ.get("HOME", "~")).expanduser()
    health = inspect(repo, home)

    if args.check:
        print_health(health)
        return 0 if health.ok else 1
    if args.dry_run:
        print_health(health)
        for action in planned_actions(health, args.force_build):
            print(f"Would run: {action}")
        return 0
    try:
        apply(repo, home, args.force_build)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
