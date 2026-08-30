#!/usr/bin/env python3
"""Install and verify the approved public Vault dependency manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


SYSTEM_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SYSTEM_DIRECTORY / "packages.yaml"
DEFAULT_LOCK = SYSTEM_DIRECTORY.parent / "local/dependencies.lock.json"
SUPPORTED_MANAGERS = {"apt", "brew", "brew-cask"}


class DependencyError(RuntimeError):
    pass


def platform_name() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise DependencyError(f"unsupported platform: {sys.platform}")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DependencyError(f"dependency manifest is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DependencyError(f"dependency manifest is invalid JSON-compatible YAML: {exc}") from exc
    if value.get("schema_version") != 1 or not isinstance(value.get("packages"), list):
        raise DependencyError("dependency manifest needs schema_version 1 and a packages list")
    seen: set[str] = set()
    for package in value["packages"]:
        if not isinstance(package, dict) or not isinstance(package.get("id"), str):
            raise DependencyError("every dependency needs a string id")
        package_id = package["id"]
        if package_id in seen:
            raise DependencyError(f"duplicate dependency id: {package_id}")
        seen.add(package_id)
        platforms = package.get("platforms")
        verify = package.get("verify")
        if not isinstance(platforms, dict) or not isinstance(verify, dict):
            raise DependencyError(f"dependency {package_id} needs platforms and verify objects")
        for recipe in platforms.values():
            if not isinstance(recipe, dict) or recipe.get("manager") not in SUPPORTED_MANAGERS:
                raise DependencyError(f"dependency {package_id} uses an unsupported package manager")
            if not isinstance(recipe.get("package"), str) or not recipe["package"]:
                raise DependencyError(f"dependency {package_id} has no package name")
        if not isinstance(verify.get("command"), str) or not isinstance(verify.get("args", []), list):
            raise DependencyError(f"dependency {package_id} has an invalid verification command")
    return value


def command_environment() -> dict[str, str]:
    home = Path.home()
    candidates = [
        home / ".local/bin",
        home / ".bun/bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
        Path("/usr/sbin"),
        Path("/sbin"),
    ]
    env = dict(os.environ)
    env["PATH"] = ":".join(str(path) for path in candidates)
    return env


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        env=command_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def verify_package(package: dict[str, Any]) -> dict[str, Any]:
    verify = package["verify"]
    command = str(verify["command"])
    executable = shutil.which(command, path=command_environment()["PATH"])
    if executable is None:
        return {"id": package["id"], "ready": False, "detail": f"{command} is missing"}
    result = run([executable, *[str(value) for value in verify.get("args", [])]])
    output = (result.stdout or result.stderr).strip().splitlines()
    return {
        "id": package["id"],
        "ready": result.returncode == 0,
        "command": executable,
        "version": output[0][:500] if output else None,
        "detail": "verified" if result.returncode == 0 else (output[-1][:500] if output else "verification failed"),
    }


def install_command(recipe: dict[str, Any]) -> list[str]:
    manager = recipe["manager"]
    package = str(recipe["package"])
    if manager == "brew":
        installed = run(["brew", "list", "--versions", package]).returncode == 0
        return ["brew", "upgrade" if installed else "install", package]
    if manager == "brew-cask":
        installed = run(["brew", "list", "--cask", "--versions", package]).returncode == 0
        return ["brew", "upgrade" if installed else "install", "--cask", package]
    if manager == "apt":
        return ["sudo", "-n", "apt-get", "install", "-y", "--no-install-recommends", package]
    raise DependencyError(f"unsupported package manager: {manager}")


def install_package(package: dict[str, Any], recipe: dict[str, Any]) -> None:
    command = install_command(recipe)
    executable = shutil.which(command[0], path=command_environment()["PATH"])
    if executable is None:
        raise DependencyError(f"package manager is missing for {package['id']}: {command[0]}")
    result = run([executable, *command[1:]])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise DependencyError(
            f"dependency installation failed for {package['id']}: "
            f"{detail[-1][:500] if detail else 'command failed'}"
        )


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def update_lock(path: Path, installed: list[dict[str, Any]]) -> None:
    try:
        lock = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise DependencyError(f"dependency lock is invalid: {path}: {exc}") from exc
    if not isinstance(lock, dict):
        raise DependencyError(f"dependency lock must contain an object: {path}")
    lock["vault_packages"] = installed
    lock["vault_packages_verified_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    atomic_write_json(path, lock)


def reconcile(
    manifest: dict[str, Any],
    *,
    apply: bool,
    verify: bool,
    update: bool,
    lock_path: Path,
) -> int:
    platform = platform_name()
    selected = [
        package
        for package in manifest["packages"]
        if isinstance(package.get("platforms", {}).get(platform), dict)
    ]
    preview = [verify_package(package) for package in selected]
    missing = [result for result in preview if not result["ready"]]
    mode = "verify" if verify else "update" if update else "apply" if apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"Platform: {platform}")
    for result in preview:
        print(f"  {result['id']}: {'ready' if result['ready'] else result['detail']}")
    if verify:
        return 0 if not missing else 2
    if update:
        for package, state in zip(selected, preview, strict=True):
            recipe = package["platforms"][platform]
            manager = str(recipe["manager"])
            package_name = str(recipe["package"])
            installed = (
                run(["brew", "list", "--cask", "--versions", package_name]).returncode == 0
                if manager == "brew-cask"
                else run(["brew", "list", "--versions", package_name]).returncode == 0
                if manager == "brew"
                else run(["dpkg-query", "-W", "-f=${Status}", package_name]).stdout.strip() == "install ok installed"
            )
            if installed:
                install_package(package, recipe)
            elif state["ready"]:
                raise DependencyError(
                    f"{package['id']} verifies but is not owned by its approved {manager} recipe"
                )
        installed_state = [verify_package(package) for package in selected]
        failed = [result for result in installed_state if not result["ready"]]
        if failed:
            raise DependencyError(
                "post-update verification failed: " + ", ".join(str(item["id"]) for item in failed)
            )
        update_lock(lock_path, installed_state)
        return 0
    if not apply:
        for result in missing:
            package = next(item for item in selected if item["id"] == result["id"])
            print("  would run: " + " ".join(install_command(package["platforms"][platform])))
        return 0
    for result in missing:
        package = next(item for item in selected if item["id"] == result["id"])
        install_package(package, package["platforms"][platform])
    installed = [verify_package(package) for package in selected]
    failed = [result for result in installed if not result["ready"]]
    if failed:
        raise DependencyError("post-install verification failed: " + ", ".join(str(item["id"]) for item in failed))
    update_lock(lock_path, installed)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview without installing packages")
    mode.add_argument("--verify", action="store_true", help="verify without installing packages")
    mode.add_argument("--update", action="store_true", help="update installed packages through their approved managers")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return reconcile(
            load_manifest(args.manifest.expanduser().resolve()),
            apply=not args.dry_run and not args.verify and not args.update,
            verify=bool(args.verify),
            update=bool(args.update),
            lock_path=args.lock.expanduser().resolve(),
        )
    except (DependencyError, OSError) as exc:
        print(f"Vault dependency install failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
