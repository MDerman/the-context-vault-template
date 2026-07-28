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
from vault_layout import (
    BOOTSTRAP_POLICY_PATH,
    INSTALL_STATE_PATH,
    RELEASE_PATH,
    UPGRADE_REPORTS_DIR,
)


DEFAULT_REPO_URL = "https://github.com/MDerman/the-context-vault-template.git"
INSTALL_PATH = INSTALL_STATE_PATH
POLICY_PATH = BOOTSTRAP_POLICY_PATH
REPORT_ROOT = UPGRADE_REPORTS_DIR
DEPS_SCRIPT = Path("_system/commands/deps.py")
STATE_BASE = Path.home() / "Library/Application Support/context-nine-vault-bootstrap"


@dataclass
class Change:
    status: str
    path: str
    old_path: str | None = None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


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
    return read_json(root / INSTALL_PATH)


def load_release(root: Path) -> dict[str, Any]:
    return read_json(root / RELEASE_PATH)


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


def load_policy(root: Path, git_dir: Path | None = None, rev: str | None = None) -> dict[str, Any]:
    if git_dir and rev:
        text = git_show_text(root, git_dir, rev, POLICY_PATH.as_posix())
        if text:
            return json.loads(text)
    return read_json(
        root / POLICY_PATH,
        {"schema_version": 1, "default_action": "preserve", "actions": {}},
    )


def latest_release(root: Path, git_dir: Path, rev: str) -> dict[str, Any]:
    text = git_show_text(root, git_dir, rev, RELEASE_PATH.as_posix())
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
    report_root = root / REPORT_ROOT
    reports = list(report_root.glob("*/report.json")) if report_root.exists() else []
    return sorted(reports)[-1] if reports else None


def write_report(root: Path, payload: dict[str, Any]) -> Path:
    report_dir = root / REPORT_ROOT / payload["timestamp"]
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.json"
    write_json(report_path, payload)
    return report_path


def finish_report(root: Path, payload: dict[str, Any], result: str, error: str | None = None) -> Path:
    payload["result"] = result
    payload["error"] = error
    payload["finished_at"] = utc_iso()
    return write_report(root, payload)


def failed_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("result") == "failed"]


def write_install(root: Path, install: dict[str, Any]) -> None:
    write_json(root / INSTALL_PATH, install)


def run_upgrade(root: Path, apply: bool) -> int:
    install, state_dir, upstream_git_dir = ensure_install_state(root)
    latest_rev = fetch_latest(root, upstream_git_dir)
    installed_rev = install.get("installed_commit") or git(root, upstream_git_dir, ["rev-parse", "HEAD"]).stdout.strip()
    policy = load_policy(root, upstream_git_dir, latest_rev)
    release = latest_release(root, upstream_git_dir, latest_rev)
    timestamp = utc_stamp()
    started_at = utc_iso()
    backup_root = state_dir / "backups" / timestamp

    changes = changed_paths(root, upstream_git_dir, installed_rev, latest_rev)
    entries: list[dict[str, Any]] = []
    report_payload: dict[str, Any] = {
        "timestamp": timestamp,
        "started_at": started_at,
        "finished_at": None,
        "mode": "apply" if apply else "dry-run",
        "repo_url": install.get("repo_url") or release.get("repo_url") or DEFAULT_REPO_URL,
        "from_commit": installed_rev,
        "to_commit": latest_rev,
        "from_version": install.get("installed_version"),
        "to_version": release.get("version"),
        "release_tag": release.get("tag"),
        "dependency_lock_sha256": release.get("dependency_lock_sha256"),
        "installed_commit": installed_rev,
        "latest_commit": latest_rev,
        "installed_version": install.get("installed_version"),
        "latest_version": release.get("version"),
        "result": "running",
        "error": None,
        "backup_root": backup_root.as_posix(),
        "changes": entries,
        "migrations": [],
        "dependencies": {},
    }
    report_path = write_report(root, report_payload)

    try:
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
        report_payload["changes"] = entries
        write_report(root, report_payload)

        migrations = run_migrations(root, policy, report_path.parent, apply=apply)
        report_payload["migrations"] = migrations
        migration_failures = failed_entries(migrations)
        if migration_failures:
            report_path = finish_report(root, report_payload, "failed", "Migration failed.")
            raise SystemExit(f"Migration failed. See report: {report_path}")

        dependencies = run_dependency_sync(root, apply=apply)
        report_payload["dependencies"] = dependencies
        if dependencies.get("stdout"):
            print(dependencies["stdout"])
        if dependencies.get("stderr"):
            print(dependencies["stderr"], file=sys.stderr)
        if dependencies.get("result") == "failed":
            report_path = finish_report(root, report_payload, "failed", "Dependency sync failed.")
            raise SystemExit(f"Dependency sync failed. See report: {report_path}")

        if apply:
            git(root, upstream_git_dir, ["reset", "--mixed", latest_rev])
            install["installed_commit"] = latest_rev
            install["installed_version"] = release.get("version") or install.get("installed_version")
            install["installed_tag"] = release.get("tag") or install.get("installed_tag")
            install["dependency_lock_sha256"] = release.get("dependency_lock_sha256")
            install["last_upgrade_report"] = str(report_path.relative_to(root))
            write_install(root, install)

        report_path = finish_report(root, report_payload, "ok")
    except SystemExit as exc:
        if report_payload.get("result") == "running":
            report_path = finish_report(root, report_payload, "failed", str(exc) or "Upgrade failed.")
        raise

    print(f"{'Applied' if apply else 'Dry-run'} upgrade report: {report_path}")
    print(f"changes: {len(entries)}")
    print(f"migrations: {len(report_payload['migrations'])}")
    return 0


def run_dependency_only_upgrade(root: Path, apply: bool) -> int:
    timestamp = utc_stamp()
    started_at = utc_iso()
    dependencies = run_dependency_sync(root, apply=apply)
    report_payload: dict[str, Any] = {
        "timestamp": timestamp,
        "started_at": started_at,
        "finished_at": None,
        "mode": "apply" if apply else "dry-run",
        "public_bootstrap": "skipped_missing_install_state",
        "from_version": None,
        "to_version": None,
        "from_commit": None,
        "to_commit": None,
        "release_tag": None,
        "dependency_lock_sha256": None,
        "result": "running",
        "error": None,
        "changes": [],
        "migrations": [],
        "dependencies": dependencies,
    }
    if dependencies.get("stdout"):
        print(dependencies["stdout"])
    if dependencies.get("stderr"):
        print(dependencies["stderr"], file=sys.stderr)
    if dependencies.get("result") == "failed":
        report_path = finish_report(root, report_payload, "failed", "Dependency sync failed.")
        raise SystemExit(f"Dependency sync failed. See report: {report_path}")
    report_path = finish_report(root, report_payload, "ok")
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
        "latestFailedAttempt": None,
    }
    if report:
        report_payload = read_json(report)
        if report_payload.get("result") == "failed":
            payload["latestFailedAttempt"] = {
                "report": str(report),
                "fromVersion": report_payload.get("from_version") or report_payload.get("installed_version"),
                "toVersion": report_payload.get("to_version") or report_payload.get("latest_version"),
                "fromCommit": report_payload.get("from_commit") or report_payload.get("installed_commit"),
                "toCommit": report_payload.get("to_commit") or report_payload.get("latest_commit"),
                "error": report_payload.get("error"),
                "finishedAt": report_payload.get("finished_at"),
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
            "installedTag": install.get("installed_tag") or "unknown",
            "dependencyLockSha256": install.get("dependency_lock_sha256") or "unknown",
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
    print(f"installed tag:     {install.get('installed_tag') or 'unknown'}")
    print(f"latest version:    {release.get('version') or 'unknown'}")
    print(f"dependency lock:   {install.get('dependency_lock_sha256') or 'unknown'}")
    print("up to date: " + ("yes" if installed_rev == latest_rev else "no"))
    report = latest_report(root)
    if report:
        report_payload = read_json(report)
        if report_payload.get("result") == "failed":
            print(
                "latest failed attempt: "
                f"{report_payload.get('from_version') or report_payload.get('installed_version') or 'unknown'}"
                " -> "
                f"{report_payload.get('to_version') or report_payload.get('latest_version') or 'unknown'}"
                f" ({report})"
            )
    return 0


def doctor_payload(root: Path) -> dict[str, Any]:
    ok = True
    install = load_install(root)
    release = load_release(root)
    policy = read_json(root / POLICY_PATH)
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
            "path": str(root / INSTALL_PATH),
        },
        "policy": {
            "present": bool(policy),
            "path": str(root / POLICY_PATH),
        },
        "releaseVersion": release.get("version") or "unknown",
        "stateRoot": str(root / INSTALL_PATH.parent),
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
    print(f"vault state: {payload['stateRoot']}")
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
