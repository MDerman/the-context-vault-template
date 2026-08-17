#!/usr/bin/env python3
"""Render and reconcile versioned global agent configuration."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any


MANAGED_MARKER = "vault.bootstrap"
CONFIG_RELATIVE = Path("_system/agents/config")
REGISTRY_RELATIVE = Path(
    "_system/local/skills/infra-code-folder-and-computer-topology/private/machines.json"
)
TEMPLATE_BY_MACHINE = {
    ("primary", "macos"): "primary-macos.md",
    ("worker", "macos"): "worker-macos.md",
    ("worker", "linux"): "worker-linux.md",
}
NOVNC_EXAMPLE_PORT = 61152


class AgentConfigurationError(RuntimeError):
    pass


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def result(path: Path | str, kind: str, status: str, detail: str, **extra: object) -> dict[str, object]:
    return {"path": str(path), "kind": kind, "status": status, "detail": detail, **extra}


def can_replace_managed_agent_file(path: Path) -> bool:
    if not path.exists() or path.is_symlink() or not path.is_file():
        return False
    return MANAGED_MARKER in path.read_text(encoding="utf-8", errors="replace")


def ensure_directory(path: Path, dry_run: bool) -> dict[str, object]:
    if path.is_dir() and not path.is_symlink():
        return result(path, "directory", "match", "directory exists")
    if lexists(path):
        raise AgentConfigurationError(f"Refusing to replace existing non-directory path: {path}")
    if dry_run:
        return result(path, "directory", "missing", "directory would be created")
    path.mkdir(parents=True, exist_ok=True)
    return result(path, "directory", "installed", "directory created")


def ensure_real_directory(path: Path, dry_run: bool) -> dict[str, object]:
    if path.is_symlink():
        if dry_run:
            return result(path, "directory", "different", "legacy symlink would be replaced with a directory")
        path.unlink()
        path.mkdir(parents=True, exist_ok=True)
        return result(path, "directory", "installed", "legacy symlink replaced with a directory")
    return ensure_directory(path, dry_run)


def ensure_symlink(
    path: Path,
    target: str,
    dry_run: bool,
    *,
    directory: bool = False,
) -> dict[str, object]:
    if path.is_symlink() and os.readlink(path) == target:
        return result(path, "symlink", "match", "symlink target matches", target=target)
    if path.is_symlink():
        if dry_run:
            return result(path, "symlink", "different", "symlink target would be replaced", target=target)
        path.unlink()
    elif path.exists():
        if path.is_file() and can_replace_managed_agent_file(path):
            if dry_run:
                return result(path, "symlink", "different", "managed generated file would be replaced", target=target)
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            if dry_run:
                return result(path, "symlink", "different", "empty directory would be replaced", target=target)
            path.rmdir()
        else:
            raise AgentConfigurationError(f"Refusing to replace existing unmanaged path: {path}")
    if dry_run:
        return result(path, "symlink", "missing", "symlink would be created", target=target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target, target_is_directory=directory)
    return result(path, "symlink", "installed", "symlink created", target=target)


def ensure_agent_paths(root: Path, dry_run: bool) -> dict[str, object]:
    """Ensure Vault-local agent directories and aliases from one shared implementation."""
    root = root.expanduser().resolve()
    results: list[dict[str, object]] = []
    for relative in (
        "_system/agents/skills",
        "_system/agents/auto-skills",
        "_system/agents/manual-skills",
        "_system/agents/gh-skills",
        "_system/agents/skills-dump",
        ".agents",
        ".claude",
    ):
        results.append(ensure_directory(root / relative, dry_run))
    results.append(ensure_symlink(root / "CLAUDE.md", "AGENTS.md", dry_run))
    results.append(ensure_real_directory(root / ".agents/skills", dry_run))
    results.append(
        ensure_symlink(
            root / ".claude/skills",
            "../.agents/skills",
            dry_run,
            directory=True,
        )
    )
    return {
        "ok": True,
        "ready": not any(item["status"] in {"missing", "different"} for item in results),
        "applied": not dry_run,
        "results": results,
    }


def safe_target(home: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise AgentConfigurationError(f"unsafe managed path: {relative!r}")
    target = home.joinpath(*candidate.parts)
    if target == home or home not in target.parents:
        raise AgentConfigurationError(f"managed path escapes home: {relative!r}")
    return target


def backup_existing(target: Path, suffix: str) -> Path | None:
    if not lexists(target):
        return None
    backup = target.with_name(f"{target.name}.backup-{suffix}")
    if lexists(backup):
        raise AgentConfigurationError(f"backup path already exists: {backup}")
    os.replace(target, backup)
    return backup


def install_file(target: Path, content: bytes, mode: int, suffix: str) -> Path | None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.parent.chmod(0o700)
    backup = backup_existing(target, suffix)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.sync-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return backup


def install_symlink(target: Path, link_target: str, suffix: str) -> Path | None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.parent.chmod(0o700)
    backup = backup_existing(target, suffix)
    temporary = target.with_name(f".{target.name}.sync-link-{os.getpid()}")
    if lexists(temporary):
        raise AgentConfigurationError(f"temporary symlink already exists: {temporary}")
    os.symlink(link_target, temporary)
    os.replace(temporary, target)
    return backup


def inspect_file(target: Path, expected: bytes, mode: int) -> tuple[str, str]:
    if not lexists(target):
        return "missing", "file is absent"
    if target.is_symlink() or not target.is_file():
        return "different", "path is not a regular file"
    actual_mode = stat.S_IMODE(target.stat().st_mode)
    differences: list[str] = []
    if target.read_bytes() != expected:
        differences.append("content differs")
    if actual_mode != mode:
        differences.append(f"mode is {oct(actual_mode)}, expected {oct(mode)}")
    return ("different", ", ".join(differences)) if differences else ("match", "content and mode match")


def inspect_symlink(target: Path, link_target: str) -> tuple[str, str]:
    if not lexists(target):
        return "missing", "symlink is absent"
    if target.is_symlink() and os.readlink(target) == link_target:
        return "match", "symlink target matches"
    return "different", "path is not the expected symlink"


TOML_TABLE_HEADER = re.compile(r"^\s*(\[{1,2})(.+?)(\]{1,2})\s*(?:#.*)?$")


def split_toml_sections(text: str) -> list[tuple[str | None, list[str]]]:
    """Split TOML without reserializing it so comments and CLI-owned formatting survive."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in text.splitlines():
        match = TOML_TABLE_HEADER.match(line)
        if match and len(match.group(1)) == len(match.group(3)):
            sections.append((match.group(2).strip(), [line]))
        else:
            sections[-1][1].append(line)
    return sections


def managed_toml_content(managed: str, existing: str, preserve_tables: list[str]) -> bytes:
    """Render primary-owned TOML plus exact target-local table subtrees."""

    def preserved(name: str | None) -> bool:
        return bool(name) and any(name == prefix or name.startswith(f"{prefix}.") for prefix in preserve_tables)

    managed_lines = [
        line
        for name, lines in split_toml_sections(managed)
        if not preserved(name)
        for line in lines
    ]
    existing_lines = [
        line
        for name, lines in split_toml_sections(existing)
        if preserved(name)
        for line in lines
    ]
    rendered = "\n".join(managed_lines).rstrip()
    preserved_text = "\n".join(existing_lines).strip()
    if preserved_text:
        rendered = f"{rendered}\n\n{preserved_text}" if rendered else preserved_text
    return (rendered.rstrip() + "\n").encode()


def reconcile_home(
    home: Path,
    files: list[dict[str, object]],
    *,
    apply: bool,
    verify: bool,
    backup_suffix: str,
    require_process_home: bool = True,
) -> dict[str, object]:
    home = home.expanduser().resolve()
    if not home.is_absolute() or (require_process_home and home != Path.home().resolve()):
        raise AgentConfigurationError(f"target home mismatch: expected {home}, process home is {Path.home()}")
    results: list[dict[str, object]] = []
    for raw in files:
        relative = str(raw.get("path") or "")
        kind = str(raw.get("kind") or "file")
        target = safe_target(home, relative)
        if kind in {"file", "toml"}:
            encoded = raw.get("content")
            if not isinstance(encoded, str):
                raise AgentConfigurationError(f"managed file has no content: {relative}")
            content = base64.b64decode(encoded, validate=True)
            if kind == "toml":
                prefixes = raw.get("preserve_tables")
                if not isinstance(prefixes, list) or not prefixes or not all(
                    isinstance(prefix, str) and prefix for prefix in prefixes
                ):
                    raise AgentConfigurationError(f"managed TOML file needs preserve_tables: {relative}")
                existing = (
                    target.read_text(encoding="utf-8")
                    if target.is_file() and not target.is_symlink()
                    else ""
                )
                content = managed_toml_content(
                    content.decode("utf-8"),
                    existing,
                    prefixes,
                )
            mode = int(raw.get("mode") or 0o600)
            state, detail = inspect_file(target, content, mode)
            if apply and state != "match":
                backup = install_file(target, content, mode, backup_suffix)
                state, detail = "installed", "installed atomically"
                if backup is not None:
                    detail += f"; previous path backed up as {backup.name}"
            results.append(result(relative, kind, state, detail, sha256=digest_bytes(content)))
        elif kind == "symlink":
            link_target = str(raw.get("target") or "")
            if not link_target or PurePosixPath(link_target).is_absolute():
                raise AgentConfigurationError(f"managed symlink needs a relative target: {relative}")
            state, detail = inspect_symlink(target, link_target)
            if apply and state != "match":
                backup = install_symlink(target, link_target, backup_suffix)
                state, detail = "installed", "installed symlink atomically"
                if backup is not None:
                    detail += f"; previous path backed up as {backup.name}"
            results.append(result(relative, kind, state, detail, target=link_target))
        else:
            raise AgentConfigurationError(f"unsupported managed file kind: {kind}")
    mismatched = any(item["status"] in {"missing", "different"} for item in results)
    return {
        "ok": True,
        "mode": "apply" if apply else "verify" if verify else "preview",
        "ready": not mismatched,
        "applied": apply,
        "results": results,
    }


def reconcile_payload(payload: dict[str, object]) -> dict[str, object]:
    files = payload.get("files")
    if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
        raise AgentConfigurationError("managed files payload must be a list of objects")
    return reconcile_home(
        Path(str(payload["home"])),
        files,
        apply=bool(payload.get("apply")),
        verify=bool(payload.get("verify")),
        backup_suffix=str(payload.get("backup_suffix") or "unknown"),
    )


def load_registry(root: Path, path: Path | None = None) -> dict[str, Any]:
    registry_path = path or root / REGISTRY_RELATIVE
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentConfigurationError(f"machine registry is missing: {registry_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentConfigurationError(f"machine registry is invalid: {exc}") from exc
    machines = registry.get("machines") if isinstance(registry, dict) else None
    if not isinstance(machines, list) or not machines:
        raise AgentConfigurationError("machine registry has no machines")
    return registry


def current_machine_id(root: Path, home: Path) -> str:
    identity = subprocess.run(
        ["git", "-C", str(root), "config", "--get", "vault.machine-id"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if identity.returncode == 0 and identity.stdout.strip():
        return identity.stdout.strip()
    marker = home / ".config/vault/machine-id"
    value = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if not value:
        raise AgentConfigurationError("current machine has no Vault identity")
    return value


def machine_by_id(registry: dict[str, Any], machine_id: str) -> dict[str, Any]:
    matches = [item for item in registry["machines"] if isinstance(item, dict) and item.get("id") == machine_id]
    if len(matches) != 1:
        raise AgentConfigurationError(f"machine {machine_id!r} did not resolve exactly once")
    return matches[0]


def peer_lines(registry: dict[str, Any], machine_id: str) -> str:
    lines: list[str] = []
    for peer in registry["machines"]:
        if not isinstance(peer, dict) or not peer.get("enabled") or peer.get("id") == machine_id:
            continue
        address = peer.get("wireguard_address")
        route = f", WireGuard `{address}`" if isinstance(address, str) and address else ""
        lines.append(
            f"- {peer.get('display_name')} (`{peer.get('id')}`): {peer.get('role')} {peer.get('platform')}{route}."
        )
    return "\n".join(lines) if lines else "- No other enabled fleet machines are registered."


def recorded_novnc_url(source_home: Path, machine: dict[str, Any]) -> str | None:
    runtime = source_home / ".cache/vault-machine"
    path = runtime / f"{machine.get('id')}-vnc.json"
    control = runtime / f"{machine.get('id')}-vnc.sock"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    alias = machine.get("ssh_alias")
    if not control.exists() or not isinstance(alias, str) or not alias:
        return None
    try:
        check = subprocess.run(
            ["ssh", "-S", str(control), "-O", "check", alias],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if check.returncode != 0:
        return None
    url = value.get("url") if isinstance(value, dict) and value.get("machine_id") == machine.get("id") else None
    return url if isinstance(url, str) and url.startswith("http://127.0.0.1:") else None


def access_guidance(machine: dict[str, Any], source_home: Path) -> str:
    vnc = machine.get("vnc")
    if not isinstance(vnc, dict):
        return ""
    if vnc.get("kind") == "native-url" and isinstance(vnc.get("url"), str):
        return f"For GUI inspection from Mattbook, return the Screen Sharing link [{vnc['url']}]({vnc['url']})."
    if vnc.get("kind") != "ssh-novnc":
        return ""
    active = recorded_novnc_url(source_home, machine)
    open_path = str(vnc.get("open_path") or "/vnc.html")
    example = f"http://127.0.0.1:{NOVNC_EXAMPLE_PORT}{open_path}"
    guidance = (
        "For GUI inspection, ensure Mattbook has established and confirmed the SSH noVNC tunnel with "
        f"`vault machine vnc {machine.get('id')}`, then return its actual clickable loopback URL."
    )
    if active:
        return f"{guidance} The last recorded tunnel URL is [{active}]({active}); confirm it before use."
    return f"{guidance} A possible forwarded URL is [{example}]({example}); its port is only an example."


def render_agents(
    root: Path,
    registry: dict[str, Any],
    machine: dict[str, Any],
    *,
    source_home: Path,
) -> str:
    config = root / CONFIG_RELATIVE
    source = config / "AGENTS.md"
    template_name = TEMPLATE_BY_MACHINE.get((str(machine.get("role")), str(machine.get("platform"))))
    if template_name is None:
        raise AgentConfigurationError(
            f"no global agent template for {machine.get('role')} {machine.get('platform')}"
        )
    template = config / "overlays" / template_name
    if not source.is_file() or not template.is_file():
        raise AgentConfigurationError(f"global agent configuration is incomplete under {config}")
    primary = machine_by_id(registry, str(registry.get("primary_machine_id") or ""))
    address = str(machine.get("wireguard_address") or "")
    service_url = f"http://{address}:<port>" if address else "a registry-provided reachable address"
    footer = template.read_text(encoding="utf-8").format_map(
        {
            "machine_id": machine.get("id"),
            "display_name": machine.get("display_name"),
            "wireguard_address": address or "not configured",
            "service_url": service_url,
            "primary_id": primary.get("id"),
            "primary_display_name": primary.get("display_name"),
            "primary_wireguard_address": primary.get("wireguard_address") or "not configured",
            "peers": peer_lines(registry, str(machine.get("id"))),
            "access_guidance": access_guidance(machine, source_home),
        }
    ).strip()
    return source.read_text(encoding="utf-8").rstrip() + "\n\n***\n\n" + footer + "\n"


def home_agent_files(rendered_agents: str) -> list[dict[str, object]]:
    return [
        {
            "path": ".codex/AGENTS.md",
            "kind": "file",
            "mode": 0o644,
            "content": base64.b64encode(rendered_agents.encode()).decode(),
        },
        {
            "path": ".claude/CLAUDE.md",
            "kind": "symlink",
            "target": "../.codex/AGENTS.md",
        },
    ]


def sync_local(
    root: Path,
    home: Path,
    *,
    apply: bool,
    backup_suffix: str,
) -> dict[str, object]:
    root_report = ensure_agent_paths(root, dry_run=not apply)
    config = root / CONFIG_RELATIVE
    registry_path = root / REGISTRY_RELATIVE
    if not config.is_dir() or not registry_path.is_file():
        return {
            "ok": True,
            "ready": bool(root_report["ready"]),
            "applied": apply,
            "root": root_report,
            "home": None,
            "warning": "personal global agent configuration is unavailable; only Vault-local paths were checked",
        }
    registry = load_registry(root)
    machine_id = current_machine_id(root, home)
    machine = machine_by_id(registry, machine_id)
    rendered = render_agents(root, registry, machine, source_home=home)
    home_report = reconcile_home(
        home,
        home_agent_files(rendered),
        apply=apply,
        verify=False,
        backup_suffix=backup_suffix,
        require_process_home=home.resolve() == Path.home().resolve(),
    )
    return {
        "ok": True,
        "ready": bool(root_report["ready"]) and bool(home_report["ready"]),
        "applied": apply,
        "machine_id": machine_id,
        "root": root_report,
        "home": home_report,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise AgentConfigurationError("payload must be an object")
        response = reconcile_payload(payload)
        json.dump(response, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        json.dump({"ok": False, "error": str(exc)[:500]}, sys.stdout)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
