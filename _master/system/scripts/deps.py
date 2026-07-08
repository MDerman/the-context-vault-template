#!/usr/bin/env python3
"""Manage external dependency repos and optional vault projections."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = Path("_master/system/config/deps.json")
BACKUP_ROOT = Path("_master/agents/backups/deps-projections")
SKILL_SYNC = Path("_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh")
MANAGED_MARKER = ".vault-deps-projection.json"


@dataclass(frozen=True)
class Projection:
    repo_id: str
    repo_path: Path
    source: str
    target: str
    type: str
    managed: bool


@dataclass(frozen=True)
class Repo:
    id: str
    url: str
    path: Path
    ref: str
    projections: list[Projection]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"command failed: {' '.join(args)}\n{detail}")
    return result


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing dependency config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def expand_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw)).resolve()


def vault_path(root: Path, raw: str) -> Path:
    path = Path(os.path.expanduser(raw))
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def load_config(root: Path) -> list[Repo]:
    data = read_json(root / CONFIG_PATH)
    repos: list[Repo] = []
    for item in data.get("repos", []):
        repo_id = str(item["id"])
        repo_path = expand_path(str(item["path"]))
        projections = [
            Projection(
                repo_id=repo_id,
                repo_path=repo_path,
                source=str(projection["source"]),
                target=str(projection["target"]),
                type=str(projection.get("type") or "symlink"),
                managed=bool(projection.get("managed", True)),
            )
            for projection in item.get("projections", [])
        ]
        repos.append(
            Repo(
                id=repo_id,
                url=str(item["url"]),
                path=repo_path,
                ref=str(item.get("ref") or "main"),
                projections=projections,
            )
        )
    return repos


def log(message: str) -> None:
    print(message, flush=True)


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def git_status(path: Path) -> str:
    return run(["git", "status", "--porcelain"], cwd=path).stdout.strip()


def git_rev(path: Path, rev: str) -> str | None:
    result = run(["git", "rev-parse", "--verify", rev], cwd=path, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def remote_rev(repo: Repo) -> str | None:
    refs = [
        f"refs/heads/{repo.ref}",
        f"refs/tags/{repo.ref}",
        repo.ref,
    ]
    for ref in refs:
        result = run(["git", "ls-remote", repo.url, ref], check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0]
    return None


def repo_summary(repo: Repo) -> dict[str, Any]:
    exists = repo.path.exists()
    summary: dict[str, Any] = {
        "id": repo.id,
        "url": repo.url,
        "path": str(repo.path),
        "ref": repo.ref,
        "exists": exists,
        "git": False,
        "dirty": None,
        "local_commit": None,
        "remote_commit": remote_rev(repo),
    }
    if exists and is_git_repo(repo.path):
        dirty = bool(git_status(repo.path))
        summary.update(
            {
                "git": True,
                "dirty": dirty,
                "local_commit": git_rev(repo.path, "HEAD"),
            }
        )
    return summary


def projection_marker(path: Path) -> Path:
    return path / MANAGED_MARKER


def read_marker(path: Path) -> dict[str, Any]:
    marker = projection_marker(path)
    if not marker.exists():
        return {}
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def projection_health(root: Path, projection: Projection) -> dict[str, Any]:
    source = projection.repo_path / projection.source
    target = vault_path(root, projection.target)
    marker = read_marker(target)
    return {
        "source": str(source),
        "target": str(target),
        "type": projection.type,
        "managed": projection.managed,
        "source_exists": source.exists(),
        "target_exists": target.exists() or target.is_symlink(),
        "marker": bool(marker),
        "marker_repo_id": marker.get("repo_id"),
    }


def status_payload(root: Path, repos: list[Repo]) -> dict[str, Any]:
    payload_repos: list[dict[str, Any]] = []
    for repo in repos:
        summary = repo_summary(repo)
        projections = []
        for projection in repo.projections:
            health = projection_health(root, projection)
            state = "ok" if health["source_exists"] and health["target_exists"] and health["marker"] else "needs-sync"
            projections.append(
                {
                    **health,
                    "state": state,
                    "repo_id": projection.repo_id,
                }
            )
        up_to_date = None
        if summary.get("local_commit") and summary.get("remote_commit"):
            up_to_date = summary["local_commit"] == summary["remote_commit"]
        payload_repos.append({**summary, "up_to_date": up_to_date, "projections": projections})
    return {"config": str(root / CONFIG_PATH), "repos": payload_repos}


def print_status(root: Path, repos: list[Repo]) -> int:
    for repo in repos:
        summary = repo_summary(repo)
        log(f"{repo.id}")
        log(f"  path: {summary['path']}")
        log(f"  ref: {repo.ref}")
        log(f"  exists: {'yes' if summary['exists'] else 'no'}")
        if summary["exists"]:
            log(f"  git: {'yes' if summary['git'] else 'no'}")
            log(f"  dirty: {'yes' if summary['dirty'] else 'no'}")
            log(f"  local: {short(summary['local_commit'])}")
        log(f"  remote: {short(summary['remote_commit'])}")
        if summary.get("local_commit") and summary.get("remote_commit"):
            log("  up to date: " + ("yes" if summary["local_commit"] == summary["remote_commit"] else "no"))
        for projection in repo.projections:
            health = projection_health(root, projection)
            state = "ok" if health["source_exists"] and health["target_exists"] and health["marker"] else "needs-sync"
            log(f"  projection {projection.target}: {state}")
        log("")
    return 0


def short(value: str | None) -> str:
    return value[:12] if value else "unknown"


def ensure_clean_repo(repo: Repo) -> None:
    if not repo.path.exists():
        return
    if not is_git_repo(repo.path):
        raise SystemExit(f"Dependency path exists but is not a Git repo: {repo.path}")
    dirty = git_status(repo.path)
    if dirty:
        raise SystemExit(f"Dependency repo has uncommitted changes: {repo.path}")


def sync_repo(repo: Repo, apply: bool) -> bool:
    changed = False
    if not repo.path.exists():
        log(f"Clone {repo.url} -> {repo.path}")
        if apply:
            repo.path.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", "--branch", repo.ref, "--single-branch", repo.url, str(repo.path)])
        return True

    ensure_clean_repo(repo)
    if not is_git_repo(repo.path):
        raise SystemExit(f"Dependency path exists but is not a Git repo: {repo.path}")

    local = git_rev(repo.path, "HEAD")
    remote = remote_rev(repo)
    if not remote:
        raise SystemExit(f"Could not resolve remote ref {repo.ref} for {repo.url}")
    if local == remote:
        log(f"Repo current: {repo.id} ({short(local)})")
        return False

    log(f"Fast-forward {repo.id}: {short(local)} -> {short(remote)}")
    if apply:
        run(["git", "fetch", "--prune", "origin"], cwd=repo.path)
        run(["git", "checkout", repo.ref], cwd=repo.path)
        run(["git", "merge", "--ff-only", f"origin/{repo.ref}"], cwd=repo.path)
    return changed or True


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def backup_path(root: Path, path: Path, label: str, apply: bool) -> Path:
    backup = root / BACKUP_ROOT / utc_stamp() / label
    log(f"Back up {path} -> {backup}")
    if apply:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(backup))
    return backup


def marker_payload(projection: Projection) -> dict[str, Any]:
    return {
        "managed_by": "vault deps",
        "repo_id": projection.repo_id,
        "source": projection.source,
        "target": projection.target,
        "type": projection.type,
    }


def manual_skill_metadata() -> str:
    return "policy:\n  allow_implicit_invocation: false\n"


def expected_projection_children(source: Path, *, skip_agents: bool) -> list[Path]:
    skipped = {".DS_Store", MANAGED_MARKER}
    if skip_agents:
        skipped.add("agents")
    return [
        child
        for child in sorted(source.iterdir(), key=lambda p: p.name)
        if child.name not in skipped
    ]


def manual_skill_projection_current(target: Path, source: Path, projection: Projection) -> bool:
    marker = read_marker(target)
    if marker != marker_payload(projection):
        return False
    metadata = target / "agents/openai.yaml"
    if not metadata.exists() or metadata.read_text(encoding="utf-8") != manual_skill_metadata():
        return False
    expected = {child.name: child for child in expected_projection_children(source, skip_agents=True)}
    actual = {
        child.name: child
        for child in target.iterdir()
        if child.name not in {"agents", MANAGED_MARKER, ".DS_Store"}
    }
    if set(actual) != set(expected):
        return False
    for name, target_child in actual.items():
        if not target_child.is_symlink():
            return False
        if target_child.resolve() != expected[name].resolve():
            return False
    return True


def symlink_projection_current(target: Path, source: Path, projection: Projection) -> bool:
    marker = read_marker(target)
    if marker != marker_payload(projection):
        return False
    expected = {child.name: child for child in expected_projection_children(source, skip_agents=False)}
    actual = {
        child.name: child
        for child in target.iterdir()
        if child.name not in {MANAGED_MARKER, ".DS_Store"}
    }
    if set(actual) != set(expected):
        return False
    for name, target_child in actual.items():
        if not target_child.is_symlink():
            return False
        if target_child.resolve() != expected[name].resolve():
            return False
    return True


def create_manual_skill_projection(root: Path, projection: Projection, apply: bool) -> bool:
    source = projection.repo_path / projection.source
    target = vault_path(root, projection.target)
    if not source.exists():
        raise SystemExit(f"Projection source missing: {source}")
    if not (source / "SKILL.md").exists():
        raise SystemExit(f"Manual skill projection source lacks SKILL.md: {source}")

    existing = target.exists() or target.is_symlink()
    marker = read_marker(target)
    if existing:
        if marker.get("managed_by") == "vault deps":
            if target.is_dir() and manual_skill_projection_current(target, source, projection):
                log(f"Projection current: {target}")
                return False
            log(f"Rebuild managed projection: {target}")
            if apply:
                remove_path(target)
        else:
            backup_path(root, target, target.name, apply)

    log(f"Project manual skill {source} -> {target}")
    if not apply:
        return True

    target.mkdir(parents=True, exist_ok=True)
    for child in expected_projection_children(source, skip_agents=True):
        (target / child.name).symlink_to(child)

    agents_dir = target / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "openai.yaml").write_text(manual_skill_metadata(), encoding="utf-8")
    write_json(projection_marker(target), marker_payload(projection))
    return True


def create_active_skill_projection(root: Path, projection: Projection, apply: bool) -> bool:
    source = projection.repo_path / projection.source
    target = vault_path(root, projection.target)
    if not source.exists():
        raise SystemExit(f"Projection source missing: {source}")
    if not (source / "SKILL.md").exists():
        raise SystemExit(f"Active skill projection source lacks SKILL.md: {source}")

    existing = target.exists() or target.is_symlink()
    marker = read_marker(target)
    if existing:
        if marker.get("managed_by") == "vault deps":
            if target.is_dir() and symlink_projection_current(target, source, projection):
                log(f"Projection current: {target}")
                return False
            log(f"Rebuild managed projection: {target}")
            if apply:
                remove_path(target)
        else:
            backup_path(root, target, target.name, apply)

    log(f"Project active skill {source} -> {target}")
    if not apply:
        return True

    target.mkdir(parents=True, exist_ok=True)
    for child in expected_projection_children(source, skip_agents=False):
        (target / child.name).symlink_to(child)
    write_json(projection_marker(target), marker_payload(projection))
    return True


def apply_projection(root: Path, projection: Projection, apply: bool) -> bool:
    if not projection.managed:
        log(f"Skip unmanaged projection: {projection.target}")
        return False
    if projection.type == "manual-skill":
        return create_manual_skill_projection(root, projection, apply)
    if projection.type == "active-skill":
        return create_active_skill_projection(root, projection, apply)
    raise SystemExit(f"Unknown projection type for {projection.target}: {projection.type}")


def run_skill_sync(root: Path, apply: bool) -> None:
    script = root / SKILL_SYNC
    flag = "--apply" if apply else "--dry-run"
    log(f"Run skill sync: {script} {flag}")
    if apply:
        subprocess.run([str(script), flag], cwd=root, check=True)


def sync(root: Path, repos: list[Repo], apply: bool) -> int:
    skill_projection_touched = False
    for repo in repos:
        repo_missing_before = not repo.path.exists()
        sync_repo(repo, apply)
        if repo_missing_before and not apply:
            for projection in repo.projections:
                log(f"Projection pending after clone: {projection.target}")
            continue
        for projection in repo.projections:
            if apply_projection(root, projection, apply) and projection.type in {"manual-skill", "active-skill"}:
                skill_projection_touched = True
    if skill_projection_touched:
        run_skill_sync(root, apply)
    log("Done." if apply else "Dry run complete. Re-run with --apply to make these changes.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    root_arg: str | None = None
    cleaned: list[str] = []
    index = 0
    while index < len(raw_args):
        arg = raw_args[index]
        if arg == "--root":
            if index + 1 >= len(raw_args):
                raise SystemExit("--root requires a value")
            root_arg = raw_args[index + 1]
            index += 2
            continue
        if arg.startswith("--root="):
            root_arg = arg.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(arg)
        index += 1

    parser = argparse.ArgumentParser(description="Manage external vault dependency repos and projections.")
    subparsers = parser.add_subparsers(dest="command")
    status_parser = subparsers.add_parser("status", help="Show dependency repo and projection state.")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable status JSON.")
    sync_parser = subparsers.add_parser("sync", help="Clone/pull repos and rebuild managed projections.")
    mode = sync_parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview changes.")
    mode.add_argument("--apply", action="store_true", help="Apply changes.")
    args = parser.parse_args(cleaned)
    args.root = root_arg
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    repos = load_config(root)
    if args.command == "status":
        if args.json:
            print(json.dumps(status_payload(root, repos), indent=2, sort_keys=True))
            return 0
        return print_status(root, repos)
    if args.command == "sync":
        return sync(root, repos, apply=bool(args.apply))
    print("Use `vault deps status`, `vault deps sync --dry-run`, or `vault deps sync --apply`.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
