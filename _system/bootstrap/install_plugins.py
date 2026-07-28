#!/usr/bin/env python3
"""Install active Obsidian community plugin bundles for a bootstrap vault."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any


REGISTRY_URL = "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json"
REQUIRED_ASSETS = ("main.js", "manifest.json")
OPTIONAL_ASSETS = ("styles.css",)
DEFAULT_CONFIG = "_system/bootstrap/bootstrap-export.json"
REQUEST_TIMEOUT_SECONDS = 120
DOWNLOAD_ATTEMPTS = 4
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


def default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def retry_delay(attempt: int) -> float:
    return min(2 ** (attempt - 1), 10)


def transient_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in TRANSIENT_HTTP_STATUS
    if isinstance(exc, urllib.error.URLError):
        return isinstance(exc.reason, (TimeoutError, socket.timeout, ConnectionResetError, OSError))
    return isinstance(exc, (TimeoutError, socket.timeout, http.client.IncompleteRead, ConnectionResetError))


def with_retries(description: str, operation):
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= DOWNLOAD_ATTEMPTS or not transient_error(exc):
                raise
            delay = retry_delay(attempt)
            print(
                f"retry {description} after {type(exc).__name__}: {exc} "
                f"({attempt}/{DOWNLOAD_ATTEMPTS})",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise RuntimeError(f"unreachable retry state for {description}")


def urlopen_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "context-nine-vault-bootstrap",
        },
    )

    def load() -> Any:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)

    return with_retries(url, load)


def download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "context-nine-vault-bootstrap"})

    def download() -> bytes:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read()

    return with_retries(url, download)


def url_exists(url: str) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "context-nine-vault-bootstrap"}, method="HEAD")
    try:
        return with_retries(
            url,
            lambda: urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS).close() is None,
        )
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, TimeoutError, socket.timeout, http.client.IncompleteRead, ConnectionResetError):
        return False


def exact_copy_plugins(config: dict[str, Any]) -> set[str]:
    return set(
        config.get("obsidian_plugin_exact_copy_plugins")
        or config.get("obsidian_plugin_full_copy_plugins")
        or []
    )


def active_plugins(root: Path) -> list[str]:
    path = root / ".obsidian/community-plugins.json"
    plugins = read_json(path)
    if not isinstance(plugins, list) or not all(isinstance(item, str) for item in plugins):
        raise SystemExit(f"Expected plugin id list in {path}")
    return plugins


def plugin_version(root: Path, plugin_id: str) -> str:
    path = root / ".obsidian/plugins" / plugin_id / "manifest.json"
    if not path.exists():
        raise SystemExit(f"Missing plugin manifest: {path}")
    manifest = read_json(path)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit(f"Missing version in plugin manifest: {path}")
    return version


def load_registry() -> dict[str, dict[str, Any]]:
    data = urlopen_json(REGISTRY_URL)
    if not isinstance(data, list):
        raise SystemExit("Unexpected Obsidian community plugin registry shape.")
    return {item["id"]: item for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)}


def asset_url(repo: str, tag: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{name}"


def resolve_assets(repo: str, version: str, apply: bool) -> tuple[str, dict[str, bytes | str]]:
    if not apply:
        tag = version
        return tag, {name: asset_url(repo, tag, name) for name in (*REQUIRED_ASSETS, *OPTIONAL_ASSETS)}

    failures: list[str] = []
    for tag in (version, f"v{version}"):
        assets: dict[str, bytes | str] = {}
        ok = True
        for name in REQUIRED_ASSETS:
            url = asset_url(repo, tag, name)
            if apply:
                try:
                    assets[name] = download_bytes(url)
                except urllib.error.HTTPError as exc:
                    failures.append(f"{tag}/{name}: HTTP {exc.code}")
                    ok = False
                    break
                except urllib.error.URLError as exc:
                    failures.append(f"{tag}/{name}: {exc.reason}")
                    ok = False
                    break
            elif url_exists(url):
                assets[name] = url
            else:
                failures.append(f"{tag}/{name}: not found")
                ok = False
                break
        if not ok:
            continue
        for name in OPTIONAL_ASSETS:
            url = asset_url(repo, tag, name)
            if apply:
                try:
                    assets[name] = download_bytes(url)
                except (urllib.error.HTTPError, urllib.error.URLError):
                    continue
            elif url_exists(url):
                assets[name] = url
        return tag, assets
    detail = "; ".join(failures)
    raise SystemExit(f"Could not resolve required plugin assets for {repo} version {version}. {detail}")


def install_plugin(root: Path, plugin_id: str, repo: str, version: str, apply: bool) -> dict[str, Any]:
    tag, assets = resolve_assets(repo, version, apply)
    plugin_dir = root / ".obsidian/plugins" / plugin_id
    result: dict[str, Any] = {
        "plugin": plugin_id,
        "repo": repo,
        "version": version,
        "release": tag,
        "assets": sorted(assets),
        "result": "dry-run",
    }
    print(f"{'install' if apply else 'would install'} {plugin_id} {version} from {repo}")
    if not apply:
        return result
    plugin_dir.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        if isinstance(data, bytes):
            (plugin_dir / name).write_bytes(data)
    installed_manifest = read_json(plugin_dir / "manifest.json")
    if installed_manifest.get("id") != plugin_id:
        raise SystemExit(f"Downloaded manifest id mismatch for {plugin_id}: {installed_manifest.get('id')}")
    result["result"] = "installed"
    return result


def install_plugins(root: Path, config: dict[str, Any], apply: bool) -> list[dict[str, Any]]:
    registry = load_registry()
    exact = exact_copy_plugins(config)
    results: list[dict[str, Any]] = []
    for plugin_id in active_plugins(root):
        if plugin_id in exact:
            print(f"skip exact-copy plugin {plugin_id}")
            results.append({"plugin": plugin_id, "result": "exact-copy"})
            continue
        entry = registry.get(plugin_id)
        if not entry or not isinstance(entry.get("repo"), str):
            raise SystemExit(f"Plugin {plugin_id} missing from Obsidian registry or has no repo.")
        version = plugin_version(root, plugin_id)
        results.append(install_plugin(root, plugin_id, entry["repo"], version, apply))
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install active Obsidian plugin bundles.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to this script's vault.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Bootstrap config path. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--report", default=None, help="Optional report JSON path.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Download and write plugin bundles.")
    mode.add_argument("--dry-run", action="store_true", help="Preview plugin downloads.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser().resolve() if args.root else default_root()
    config = read_json(root / args.config)
    apply = bool(args.apply and not args.dry_run)
    results = install_plugins(root, config, apply)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "apply" if apply else "dry-run",
        "plugins": results,
    }
    if args.report:
        write_json(Path(args.report), payload)
    print(f"plugins processed: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
