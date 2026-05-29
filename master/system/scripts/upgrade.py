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
INSTALL_PATH = Path(".vault-bootstrap/install.json")
POLICY_PATH = Path(".vault-bootstrap/policy.json")
RELEASE_PATH = Path(".vault-bootstrap/release.json")
REPORT_ROOT = Path(".vault-upgrade")
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
            "Missing .vault-bootstrap/install.json. Run `vault upgrade doctor` or `vault upgrade init-state --from-current`."
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
    return read_json(root / POLICY_PATH, {"schema_version": 1, "default_action": "preserve", "actions": {}})


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


def latest_report(root: Path) -> Path | None:
    report_root = root / REPORT_ROOT
    if not report_root.exists():
        return None
    reports = sorted(report_root.glob("*/report.json"))
    return reports[-1] if reports else None


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
    else:
        migrations = run_migrations(root, policy, report_path.parent, apply=False)

    report_payload["migrations"] = migrations
    report_path = write_report(root, report_payload)
    print(f"{'Applied' if apply else 'Dry-run'} upgrade report: {report_path}")
    print(f"changes: {len(entries)}")
    print(f"migrations: {len(migrations)}")
    return 0


def status(root: Path) -> int:
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


def doctor(root: Path) -> int:
    ok = True
    install = load_install(root)
    release = load_release(root)
    policy = read_json(root / POLICY_PATH)
    print(f"vault root: {root}")
    if install:
        print(f"install.json: ok ({root / INSTALL_PATH})")
    else:
        print("install.json: missing")
        ok = False
    if policy:
        print(f"policy: ok ({root / POLICY_PATH})")
    else:
        print("policy: missing")
        ok = False
    print(f"release version: {release.get('version') or 'unknown'}")
    if install:
        _state_dir, upstream_git_dir = install_paths(root, install)
        print(f"hidden upstream git: {upstream_git_dir}")
        if upstream_git_dir.exists():
            print("hidden upstream git: ok")
        else:
            print("hidden upstream git: missing")
            ok = False
    dot_git = root / ".git"
    if dot_git.is_dir():
        print(".git: directory inside vault (not recommended for iCloud)")
    elif dot_git.is_file() or dot_git.is_symlink():
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
- Preserve user-owned notes/tasks/declarations unless report says migration should update them.
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    if args.command == "status":
        return status(root)
    if args.command == "doctor":
        return doctor(root)
    if args.command == "repair-prompt":
        return repair_prompt(root)
    if args.command == "init-state":
        return init_state(root, args.from_current, args.repo_url)
    if args.apply:
        return run_upgrade(root, apply=True)
    if args.dry_run:
        return run_upgrade(root, apply=False)
    print("Use `vault upgrade status`, `vault upgrade --dry-run`, or `vault upgrade --apply`.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
