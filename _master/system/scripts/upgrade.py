#!/usr/bin/env python3
"""Upgrade a public bootstrap vault from its hidden upstream Git state."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


DEFAULT_REPO_URL = "https://github.com/MDerman/the-context-vault-template.git"
BOOTSTRAP_STATE = Path("_master/system/bootstrap/state")
INSTALL_PATH = BOOTSTRAP_STATE / "install.json"
POLICY_PATH = BOOTSTRAP_STATE / "policy.json"
RELEASE_PATH = BOOTSTRAP_STATE / "release.json"
REPORT_ROOT = BOOTSTRAP_STATE / "upgrade-reports"
EXPORT_MANIFEST_PATH = BOOTSTRAP_STATE / "export-manifest.json"
DEPS_SCRIPT = Path("_master/system/scripts/deps.py")
LEGACY_INSTALL_PATH = Path(".vault-bootstrap/install.json")
LEGACY_POLICY_PATH = Path(".vault-bootstrap/policy.json")
LEGACY_RELEASE_PATH = Path(".vault-bootstrap/release.json")
LEGACY_REPORT_ROOT = Path(".vault-upgrade")
LEGACY_EXPORT_MANIFEST_PATH = Path(".bootstrap-export-manifest.json")
STATE_BASE = Path.home() / "Library/Application Support/context-nine-vault-bootstrap"


@dataclass
class Change:
    status: str
    path: str
    old_path: str | None = None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def read_first_json(
    root: Path,
    paths: list[Path],
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    for rel_path in paths:
        path = root / rel_path
        if path.exists():
            return read_json(path, default)
    return {} if default is None else default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"command failed: {' '.join(args)}\n{detail}")
    return result


def git(root: Path, git_dir: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", "--git-dir", str(git_dir), "--work-tree", str(root), *args], check=check)


def git_bytes(root: Path, git_dir: Path, args: list[str]) -> bytes:
    result = subprocess.run(
        ["git", "--git-dir", str(git_dir), "--work-tree", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(f"command failed: git {' '.join(args)}\n{result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def app_state_dir(install_id: str) -> Path:
    return STATE_BASE / install_id


def load_install(root: Path) -> dict[str, Any]:
    return read_first_json(root, [INSTALL_PATH, LEGACY_INSTALL_PATH])


def load_release(root: Path) -> dict[str, Any]:
    return read_first_json(root, [RELEASE_PATH, LEGACY_RELEASE_PATH])


def install_paths(root: Path, install: dict[str, Any]) -> tuple[Path, Path]:
    install_id = install.get("install_id") or "default"
    state_dir = Path(install.get("state_dir") or app_state_dir(install_id)).expanduser()
    upstream_git_dir = Path(install.get("upstream_git_dir") or (state_dir / "upstream.git")).expanduser()
    return state_dir, upstream_git_dir


def ensure_install_state(root: Path) -> tuple[dict[str, Any], Path, Path]:
    install = load_install(root)
    if not install:
        raise SystemExit(
            f"Missing {INSTALL_PATH}. Run `vault upgrade doctor` or `vault upgrade init-state --from-current`."
        )
    state_dir, upstream_git_dir = install_paths(root, install)
    if not upstream_git_dir.exists():
        raise SystemExit(
            f"Missing hidden upstream Git state: {upstream_git_dir}\n"
            "Run `vault upgrade doctor` or `vault upgrade init-state --from-current`."
        )
    return install, state_dir, upstream_git_dir


def git_show_text(root: Path, git_dir: Path, rev: str, path: str) -> str | None:
    result = git(root, git_dir, ["show", f"{rev}:{path}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def git_show_first_text(root: Path, git_dir: Path, rev: str, paths: list[Path]) -> str | None:
    for path in paths:
        text = git_show_text(root, git_dir, rev, path.as_posix())
        if text:
            return text
    return None


def load_policy(root: Path, git_dir: Path | None = None, rev: str | None = None) -> dict[str, Any]:
    if git_dir and rev:
        text = git_show_first_text(root, git_dir, rev, [POLICY_PATH, LEGACY_POLICY_PATH])
        if text:
            return json.loads(text)
    return read_first_json(
        root,
        [POLICY_PATH, LEGACY_POLICY_PATH],
        {"schema_version": 1, "default_action": "preserve", "actions": {}},
    )


def latest_release(root: Path, git_dir: Path, rev: str) -> dict[str, Any]:
    text = git_show_first_text(root, git_dir, rev, [RELEASE_PATH, LEGACY_RELEASE_PATH])
    if not text:
        return {}
    return json.loads(text)


def match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) or (pattern.endswith("/**") and path.startswith(pattern[:-3] + "/")) for pattern in patterns)


def classify(policy: dict[str, Any], path: str) -> str:
    actions = policy.get("actions", {})
    for action in ("preserve", "create_if_missing", "replace"):
        patterns = actions.get(action, [])
        if isinstance(patterns, list) and match_any(path, patterns):
            return action
    return str(policy.get("default_action") or "preserve")


def fetch_latest(root: Path, git_dir: Path) -> str:
    git(root, git_dir, ["fetch", "--prune", "origin"])
    candidates = [
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
        "refs/remotes/origin/master",
    ]
    for candidate in candidates:
        result = git(root, git_dir, ["rev-parse", "--verify", candidate], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    raise SystemExit("Could not resolve origin HEAD, origin/main, or origin/master.")


def parse_changes(raw: str) -> list[Change]:
    changes: list[Change] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            changes.append(Change(status=status[0], old_path=parts[1], path=parts[2]))
        elif len(parts) >= 2:
            changes.append(Change(status=status[0], path=parts[1]))
    return changes


def changed_paths(root: Path, git_dir: Path, old_rev: str, new_rev: str) -> list[Change]:
    result = git(root, git_dir, ["diff", "--name-status", "--find-renames", old_rev, new_rev])
    return parse_changes(result.stdout)


def tree_mode(root: Path, git_dir: Path, rev: str, path: str) -> str | None:
    result = git(root, git_dir, ["ls-tree", rev, "--", path], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split(maxsplit=1)[0]


def backup_existing(root: Path, backup_root: Path, rel_path: str) -> str | None:
    source = root / rel_path
    if not source.exists() and not source.is_symlink():
        return None
    target = backup_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)
    return target.as_posix()


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def remove_empty_parent(path: Path, stop_at: Path) -> None:
    current = path
    stop_at = stop_at.resolve()
    while current.exists() and current.is_dir():
        try:
            if any(current.iterdir()):
                return
            current.rmdir()
        except OSError:
            return
        if current.resolve() == stop_at:
            return
        current = current.parent


def move_legacy_file(root: Path, legacy: Path, current: Path) -> dict[str, Any] | None:
    legacy_path = root / legacy
    current_path = root / current
    if not legacy_path.exists() and not legacy_path.is_symlink():
        return None
    result: dict[str, Any] = {"legacy_path": legacy.as_posix(), "current_path": current.as_posix()}
    current_path.parent.mkdir(parents=True, exist_ok=True)
    if current_path.exists() or current_path.is_symlink():
        remove_path(legacy_path)
        result["result"] = "removed_legacy_duplicate"
    else:
        shutil.move(str(legacy_path), str(current_path))
        result["result"] = "moved"
    remove_empty_parent(legacy_path.parent, root)
    return result


def move_legacy_reports(root: Path) -> dict[str, Any] | None:
    legacy_root = root / LEGACY_REPORT_ROOT
    if not legacy_root.exists():
        return None
    report_root = root / REPORT_ROOT
    report_root.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, str]] = []
    if legacy_root.is_dir():
        for item in sorted(legacy_root.iterdir(), key=lambda path: path.name):
            target = report_root / item.name
            if target.exists() or target.is_symlink():
                target = report_root / f"legacy-{utc_stamp()}-{item.name}"
            shutil.move(str(item), str(target))
            moved.append({"from": item.relative_to(root).as_posix(), "to": target.relative_to(root).as_posix()})
        shutil.rmtree(legacy_root)
    else:
        target = report_root / legacy_root.name
        if target.exists() or target.is_symlink():
            target = report_root / f"legacy-{utc_stamp()}-{legacy_root.name}"
        shutil.move(str(legacy_root), str(target))
        moved.append({"from": LEGACY_REPORT_ROOT.as_posix(), "to": target.relative_to(root).as_posix()})
    return {"legacy_path": LEGACY_REPORT_ROOT.as_posix(), "current_path": REPORT_ROOT.as_posix(), "moved": moved}


def migrate_legacy_state(root: Path) -> list[dict[str, Any]]:
    migrations: list[dict[str, Any]] = []
    for legacy, current in [
        (LEGACY_INSTALL_PATH, INSTALL_PATH),
        (LEGACY_EXPORT_MANIFEST_PATH, EXPORT_MANIFEST_PATH),
    ]:
        moved = move_legacy_file(root, legacy, current)
        if moved:
            migrations.append(moved)
    for legacy in [LEGACY_POLICY_PATH, LEGACY_RELEASE_PATH]:
        legacy_path = root / legacy
        if legacy_path.exists() or legacy_path.is_symlink():
            remove_path(legacy_path)
            migrations.append({"legacy_path": legacy.as_posix(), "result": "removed_legacy_export_file"})
    moved_reports = move_legacy_reports(root)
    if moved_reports:
        migrations.append(moved_reports)
    legacy_bootstrap = root / ".vault-bootstrap"
    if legacy_bootstrap.exists() and legacy_bootstrap.is_dir():
        if not any(legacy_bootstrap.iterdir()):
            legacy_bootstrap.rmdir()
            migrations.append({"legacy_path": ".vault-bootstrap", "result": "removed_empty_dir"})
    return migrations


def write_from_git(root: Path, git_dir: Path, rev: str, rel_path: str) -> None:
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = tree_mode(root, git_dir, rev, rel_path)
    remove_path(target)
    data = git_bytes(root, git_dir, ["show", f"{rev}:{rel_path}"])
    if mode == "120000":
        target.symlink_to(data.decode("utf-8").strip())
    else:
        target.write_bytes(data)


def apply_change(
    *,
    root: Path,
    git_dir: Path,
    latest_rev: str,
    change: Change,
    action: str,
    policy: dict[str, Any],
    apply: bool,
    backup_root: Path,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"status": change.status, "path": change.path, "action": action}
    if change.old_path:
        entry["old_path"] = change.old_path

    if action == "preserve":
        entry["result"] = "preserved"
        return entry

    if change.status in {"D", "R"} and change.old_path:
        old_action = classify(policy, change.old_path)
        if old_action == "replace":
            entry["old_action"] = "replace"
            if apply:
                entry["backup"] = backup_existing(root, backup_root, change.old_path)
                remove_path(root / change.old_path)
            entry["old_result"] = "removed"

    if change.status == "D":
        if action == "replace":
            if apply:
                entry["backup"] = backup_existing(root, backup_root, change.path)
                remove_path(root / change.path)
            entry["result"] = "removed"
        else:
            entry["result"] = "preserved_delete"
        return entry

    target = root / change.path
    if action == "create_if_missing" and (target.exists() or target.is_symlink()):
        entry["result"] = "skipped_existing"
        return entry

    if action in {"replace", "create_if_missing"}:
        if apply and (target.exists() or target.is_symlink()):
            entry["backup"] = backup_existing(root, backup_root, change.path)
        if apply:
            write_from_git(root, git_dir, latest_rev, change.path)
        entry["result"] = "overwritten" if action == "replace" else "created"
        return entry

    entry["result"] = "unknown_action_preserved"
    return entry


def run_migrations(root: Path, policy: dict[str, Any], report_dir: Path, apply: bool) -> list[dict[str, Any]]:
    migrations = policy.get("migrations") or []
    results: list[dict[str, Any]] = []
    for item in migrations:
        migration_path = item.get("path") if isinstance(item, dict) else str(item)
        script = root / migration_path
        result: dict[str, Any] = {"path": migration_path}
        if not script.exists():
            result["result"] = "missing"
            results.append(result)
            continue
        migration_report = report_dir / f"migration-{Path(migration_path).stem}.json"
        args = [
            sys.executable,
            str(script),
            "--root",
            str(root),
            "--report",
            str(migration_report),
            "--apply" if apply else "--dry-run",
        ]
        completed = run(args, check=False)
        result["returncode"] = completed.returncode
        result["stdout"] = completed.stdout.strip()
        result["stderr"] = completed.stderr.strip()
        result["report"] = migration_report.as_posix()
        result["result"] = "ok" if completed.returncode == 0 else "failed"
        results.append(result)
    return results


def run_dependency_sync(root: Path, apply: bool) -> dict[str, Any]:
    script = root / DEPS_SCRIPT
    mode = "--apply" if apply else "--dry-run"
    result: dict[str, Any] = {"path": DEPS_SCRIPT.as_posix(), "mode": mode}
    if not script.exists():
        result["result"] = "missing"
        return result
    completed = run([sys.executable, str(script), "sync", mode, "--root", str(root)], check=False)
    result["returncode"] = completed.returncode
    result["stdout"] = completed.stdout.strip()
    result["stderr"] = completed.stderr.strip()
    result["result"] = "ok" if completed.returncode == 0 else "failed"
    return result


def latest_report(root: Path) -> Path | None:
    reports: list[Path] = []
    for rel_root in [REPORT_ROOT, LEGACY_REPORT_ROOT]:
        report_root = root / rel_root
        if report_root.exists():
            reports.extend(report_root.glob("*/report.json"))
    return sorted(reports)[-1] if reports else None


def write_report(root: Path, payload: dict[str, Any]) -> Path:
    report_dir = root / REPORT_ROOT / payload["timestamp"]
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.json"
    write_json(report_path, payload)
    return report_path


def write_install(root: Path, install: dict[str, Any]) -> None:
    write_json(root / INSTALL_PATH, install)


def run_upgrade(root: Path, apply: bool) -> int:
    install, state_dir, upstream_git_dir = ensure_install_state(root)
    latest_rev = fetch_latest(root, upstream_git_dir)
    installed_rev = install.get("installed_commit") or git(root, upstream_git_dir, ["rev-parse", "HEAD"]).stdout.strip()
    policy = load_policy(root, upstream_git_dir, latest_rev)
    release = latest_release(root, upstream_git_dir, latest_rev)
    timestamp = utc_stamp()
    backup_root = state_dir / "backups" / timestamp

    changes = changed_paths(root, upstream_git_dir, installed_rev, latest_rev)
    entries: list[dict[str, Any]] = []
    for change in changes:
        action = classify(policy, change.path)
        entries.append(
            apply_change(
                root=root,
                git_dir=upstream_git_dir,
                latest_rev=latest_rev,
                change=change,
                action=action,
                policy=policy,
                apply=apply,
                backup_root=backup_root,
            )
        )

    report_payload: dict[str, Any] = {
        "timestamp": timestamp,
        "mode": "apply" if apply else "dry-run",
        "repo_url": install.get("repo_url") or release.get("repo_url") or DEFAULT_REPO_URL,
        "installed_commit": installed_rev,
        "latest_commit": latest_rev,
        "installed_version": install.get("installed_version"),
        "latest_version": release.get("version"),
        "backup_root": backup_root.as_posix(),
        "changes": entries,
        "migrations": [],
        "state_migration": [],
        "dependencies": {},
    }
    report_path = write_report(root, report_payload)

    migrations: list[dict[str, Any]] = []
    if apply:
        migrations = run_migrations(root, policy, report_path.parent, apply=True)
        git(root, upstream_git_dir, ["reset", "--mixed", latest_rev])
        install["installed_commit"] = latest_rev
        install["installed_version"] = release.get("version") or install.get("installed_version")
        install["last_upgrade_report"] = str(report_path.relative_to(root))
        write_install(root, install)
        report_payload["state_migration"] = migrate_legacy_state(root)
    else:
        migrations = run_migrations(root, policy, report_path.parent, apply=False)

    report_payload["migrations"] = migrations
    dependencies = run_dependency_sync(root, apply=apply)
    report_payload["dependencies"] = dependencies
    report_path = write_report(root, report_payload)
    if dependencies.get("stdout"):
        print(dependencies["stdout"])
    if dependencies.get("stderr"):
        print(dependencies["stderr"], file=sys.stderr)
    if dependencies.get("result") == "failed":
        raise SystemExit(f"Dependency sync failed. See report: {report_path}")
    print(f"{'Applied' if apply else 'Dry-run'} upgrade report: {report_path}")
    print(f"changes: {len(entries)}")
    print(f"migrations: {len(migrations)}")
    return 0


def run_dependency_only_upgrade(root: Path, apply: bool) -> int:
    timestamp = utc_stamp()
    dependencies = run_dependency_sync(root, apply=apply)
    report_payload: dict[str, Any] = {
        "timestamp": timestamp,
        "mode": "apply" if apply else "dry-run",
        "public_bootstrap": "skipped_missing_install_state",
        "changes": [],
        "migrations": [],
        "state_migration": [],
        "dependencies": dependencies,
    }
    report_path = write_report(root, report_payload)
    if dependencies.get("stdout"):
        print(dependencies["stdout"])
    if dependencies.get("stderr"):
        print(dependencies["stderr"], file=sys.stderr)
    if dependencies.get("result") == "failed":
        raise SystemExit(f"Dependency sync failed. See report: {report_path}")
    print("Skipped public bootstrap upgrade: missing install state.")
    print(f"{'Applied' if apply else 'Dry-run'} dependency sync report: {report_path}")
    return 0


def upgrade_status_payload(root: Path) -> dict[str, Any]:
    install = load_install(root)
    report = latest_report(root)
    payload: dict[str, Any] = {
        "vaultRoot": str(root),
        "installed": bool(install),
        "repo": DEFAULT_REPO_URL,
        "installedCommit": None,
        "latestCommit": None,
        "installedVersion": None,
        "latestVersion": None,
        "upToDate": None,
        "latestReport": str(report) if report else None,
    }
    if not install:
        payload["state"] = "missing-install-state"
        payload["message"] = "No public bootstrap install state; upgrade runs dependency sync only."
        return payload

    release = load_release(root)
    state_dir, upstream_git_dir = install_paths(root, install)
    payload.update(
        {
            "state": "ok",
            "repo": install.get("repo_url") or release.get("repo_url") or DEFAULT_REPO_URL,
            "stateDir": str(state_dir),
            "hiddenUpstreamGit": str(upstream_git_dir),
            "hiddenUpstreamGitExists": upstream_git_dir.exists(),
            "installedCommit": install.get("installed_commit") or "unknown",
            "installedVersion": install.get("installed_version") or "unknown",
        }
    )
    if not upstream_git_dir.exists():
        payload["state"] = "missing-hidden-upstream"
        payload["message"] = "Run `vault upgrade doctor` or `vault upgrade init-state --from-current`."
        return payload

    try:
        latest_rev = fetch_latest(root, upstream_git_dir)
        latest = latest_release(root, upstream_git_dir, latest_rev)
    except SystemExit as exc:
        payload["state"] = "fetch-failed"
        payload["message"] = str(exc)
        return payload
    payload["latestCommit"] = latest_rev
    payload["latestVersion"] = latest.get("version") or "unknown"
    payload["upToDate"] = payload["installedCommit"] == latest_rev
    payload["repo"] = payload["repo"] or latest.get("repo_url") or DEFAULT_REPO_URL
    return payload


def status(root: Path, json_output: bool = False) -> int:
    if json_output:
        print(json.dumps(upgrade_status_payload(root), indent=2, sort_keys=True))
        return 0
    install, _state_dir, upstream_git_dir = ensure_install_state(root)
    latest_rev = fetch_latest(root, upstream_git_dir)
    installed_rev = install.get("installed_commit") or "unknown"
    release = latest_release(root, upstream_git_dir, latest_rev)
    print(f"repo: {install.get('repo_url') or release.get('repo_url') or DEFAULT_REPO_URL}")
    print(f"installed commit: {installed_rev}")
    print(f"latest commit:    {latest_rev}")
    print(f"installed version: {install.get('installed_version') or 'unknown'}")
    print(f"latest version:    {release.get('version') or 'unknown'}")
    print("up to date: " + ("yes" if installed_rev == latest_rev else "no"))
    return 0


def doctor_payload(root: Path) -> dict[str, Any]:
    ok = True
    install = load_install(root)
    release = load_release(root)
    policy = read_first_json(root, [POLICY_PATH, LEGACY_POLICY_PATH])
    legacy_present = (
        (root / LEGACY_INSTALL_PATH).exists()
        or (root / LEGACY_REPORT_ROOT).exists()
        or (root / LEGACY_EXPORT_MANIFEST_PATH).exists()
    )
    state_dir = None
    upstream_git_dir = None
    if install:
        state_dir, upstream_git_dir = install_paths(root, install)
        if not upstream_git_dir.exists():
            ok = False
    else:
        ok = False
    if not policy:
        ok = False
    dot_git = root / ".git"
    if dot_git.is_dir():
        git_state = "directory-inside-vault"
    elif dot_git.is_file() or dot_git.is_symlink():
        git_state = "pointer-or-symlink"
    else:
        git_state = "absent"
    return {
        "ok": ok,
        "vaultRoot": str(root),
        "install": {
            "present": bool(install),
            "path": str(root / (INSTALL_PATH if (root / INSTALL_PATH).exists() else LEGACY_INSTALL_PATH)),
        },
        "policy": {
            "present": bool(policy),
            "path": str(root / (POLICY_PATH if (root / POLICY_PATH).exists() else LEGACY_POLICY_PATH)),
        },
        "releaseVersion": release.get("version") or "unknown",
        "bootstrapState": str(root / BOOTSTRAP_STATE),
        "legacyStatePresent": legacy_present,
        "stateDir": str(state_dir) if state_dir else None,
        "hiddenUpstreamGit": str(upstream_git_dir) if upstream_git_dir else None,
        "hiddenUpstreamGitExists": upstream_git_dir.exists() if upstream_git_dir else False,
        "gitState": git_state,
        "repair": None if ok else "run `vault upgrade init-state --from-current` if this is a public bootstrap install.",
    }


def doctor(root: Path, json_output: bool = False) -> int:
    payload = doctor_payload(root)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["ok"] else 1
    ok = bool(payload["ok"])
    print(f"vault root: {root}")
    if payload["install"]["present"]:
        print(f"install.json: ok ({payload['install']['path']})")
    else:
        print("install.json: missing")
    if payload["policy"]["present"]:
        print(f"policy: ok ({payload['policy']['path']})")
    else:
        print("policy: missing")
    print(f"release version: {payload['releaseVersion']}")
    if payload["legacyStatePresent"]:
        print(f"legacy root state: present; next `vault upgrade --apply` migrates it to {BOOTSTRAP_STATE}")
    else:
        print(f"bootstrap state: {payload['bootstrapState']}")
    if payload["install"]["present"]:
        print(f"hidden upstream git: {payload['hiddenUpstreamGit']}")
        if payload["hiddenUpstreamGitExists"]:
            print("hidden upstream git: ok")
        else:
            print("hidden upstream git: missing")
    if payload["gitState"] == "directory-inside-vault":
        print(".git: directory inside vault (not recommended for iCloud)")
    elif payload["gitState"] == "pointer-or-symlink":
        print(".git: pointer/symlink present, likely optional user Git")
    else:
        print(".git: absent")
    if not ok:
        print("repair: run `vault upgrade init-state --from-current` if this is a public bootstrap install.")
        return 1
    return 0


def repair_prompt(root: Path) -> int:
    report = latest_report(root)
    if not report:
        print("No upgrade report found. Run `vault upgrade --dry-run` first.")
        return 1
    print(
        f"""Use skill `vault-upgrade-repair`.

Inputs:
- Report: {report}
- Vault root: {root}

Tasks:
- Read report JSON and unresolved migration logs.
- Preserve user-owned notes/tasks/entity operating notes unless report says migration should update them.
- Repair failed migrations or skipped/conflicting files.
- Run `vault upgrade doctor`.
- Summarize remaining manual work."""
    )
    return 0


def init_state(root: Path, from_current: bool, repo_url: str | None) -> int:
    if not from_current:
        raise SystemExit("Use `vault upgrade init-state --from-current`.")
    install = load_install(root)
    release = load_release(root)
    install_id = install.get("install_id") or f"{utc_stamp()}-{uuid.uuid4()}"
    repo = repo_url or install.get("repo_url") or release.get("repo_url") or DEFAULT_REPO_URL
    state_dir = Path(install.get("state_dir") or app_state_dir(install_id)).expanduser()
    upstream_git_dir = Path(install.get("upstream_git_dir") or (state_dir / "upstream.git")).expanduser()
    if upstream_git_dir.exists():
        raise SystemExit(f"Hidden upstream Git state already exists: {upstream_git_dir}")
    state_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vault-upstream-", dir=str(state_dir)) as tmp:
        tmp_worktree = Path(tmp) / "worktree"
        run(["git", "clone", "--separate-git-dir", str(upstream_git_dir), repo, str(tmp_worktree)])
        latest = run(["git", "--git-dir", str(upstream_git_dir), "--work-tree", str(tmp_worktree), "rev-parse", "HEAD"]).stdout.strip()
    target_commit = install.get("installed_commit") or latest
    git(root, upstream_git_dir, ["config", "core.worktree", str(root)])
    git(root, upstream_git_dir, ["reset", "--mixed", target_commit])
    install.update(
        {
            "schema_version": 1,
            "repo_url": repo,
            "install_id": install_id,
            "state_dir": state_dir.as_posix(),
            "upstream_git_dir": upstream_git_dir.as_posix(),
            "installed_commit": target_commit,
            "installed_version": install.get("installed_version") or release.get("version") or "unknown",
        }
    )
    write_install(root, install)
    migrate_legacy_state(root)
    print(f"Hidden upstream state initialized: {upstream_git_dir}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upgrade a public bootstrap vault from hidden upstream Git state.")
    parser.add_argument("command", nargs="?", choices=["status", "doctor", "repair-prompt", "init-state"])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview upgrade and write a report.")
    mode.add_argument("--apply", action="store_true", help="Apply upgrade.")
    parser.add_argument("--from-current", action="store_true", help="For init-state: recreate hidden state from current public repo.")
    parser.add_argument("--repo-url", default=None, help="Override upstream public repo URL for init-state.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON for status/doctor.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    if args.command == "status":
        return status(root, json_output=args.json)
    if args.command == "doctor":
        return doctor(root, json_output=args.json)
    if args.command == "repair-prompt":
        return repair_prompt(root)
    if args.command == "init-state":
        return init_state(root, args.from_current, args.repo_url)
    if args.apply:
        if not load_install(root):
            return run_dependency_only_upgrade(root, apply=True)
        return run_upgrade(root, apply=True)
    if args.dry_run:
        if not load_install(root):
            return run_dependency_only_upgrade(root, apply=False)
        return run_upgrade(root, apply=False)
    print("Use `vault upgrade status`, `vault upgrade --dry-run`, or `vault upgrade --apply`.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
