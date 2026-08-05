#!/usr/bin/env python3
"""Manage external dependency repos and optional vault projections."""

from __future__ import annotations

import argparse
import filecmp
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
from vault_layout import AGENTS_DIR, DEPENDENCY_CONFIG_PATH, DEPENDENCY_LOCK_PATH


CONFIG_PATH = DEPENDENCY_CONFIG_PATH
LOCK_PATH = DEPENDENCY_LOCK_PATH
BACKUP_ROOT = AGENTS_DIR / "backups/deps-projections"
SKILL_SYNC = AGENTS_DIR / "sync_skills.py"
MANAGED_MARKER = ".vault-deps-projection.json"


@dataclass(frozen=True)
class Projection:
    repo_id: str
    repo_path: Path
    source: str
    target: str
    type: str
    managed: bool
    title_override: str | None = None
    skill_prefix: str | None = None
    rewrite_skill_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Repo:
    id: str
    url: str
    path: Path
    ref: str
    locked_commit: str | None
    setup_script: str | None
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
        return Path(os.path.abspath(path))
    return Path(os.path.abspath(root / path))


def load_config(root: Path) -> list[Repo]:
    data = read_json(root / CONFIG_PATH)
    lock_data = read_json(root / LOCK_PATH) if (root / LOCK_PATH).exists() else {}
    locked_repos = {
        str(item.get("id")): str(item.get("resolved_commit"))
        for item in lock_data.get("external_repos", [])
        if item.get("id") and item.get("resolved_commit")
    }
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
                title_override=(
                    str(projection["title_override"])
                    if projection.get("title_override") is not None
                    else None
                ),
                skill_prefix=(
                    str(projection["skill_prefix"])
                    if projection.get("skill_prefix") is not None
                    else None
                ),
                rewrite_skill_sources=tuple(
                    str(source) for source in projection.get("rewrite_skill_sources", [])
                ),
            )
            for projection in item.get("projections", [])
        ]
        repos.append(
            Repo(
                id=repo_id,
                url=str(item["url"]),
                path=repo_path,
                ref=str(item.get("ref") or "main"),
                locked_commit=locked_repos.get(repo_id),
                setup_script=(
                    str(item["setup"]["script"])
                    if isinstance(item.get("setup"), dict) and item["setup"].get("script")
                    else None
                ),
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
        "locked_commit": repo.locked_commit,
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


def repo_setup_script(root: Path, repo: Repo) -> Path | None:
    if not repo.setup_script:
        return None
    root = root.resolve()
    raw = Path(os.path.expanduser(repo.setup_script))
    script = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        script.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"Dependency setup script must stay inside vault: {repo.setup_script}") from exc
    if not script.is_file():
        raise SystemExit(f"Dependency setup script missing: {script}")
    return script


def repo_setup_health(root: Path, repo: Repo) -> dict[str, Any] | None:
    script = repo_setup_script(root, repo)
    if not script:
        return None
    if not repo.path.exists():
        return {"script": repo.setup_script, "state": "pending", "detail": "repo missing"}
    result = run(
        [
            sys.executable,
            str(script),
            "--root",
            str(root),
            "--repo",
            str(repo.path),
            "--check",
        ],
        check=False,
    )
    detail = result.stdout.strip() or result.stderr.strip()
    return {
        "script": repo.setup_script,
        "state": "ok" if result.returncode == 0 else "needs-setup",
        "detail": detail,
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
        if summary.get("local_commit") and repo.locked_commit:
            up_to_date = summary["local_commit"] == repo.locked_commit
        elif summary.get("local_commit") and summary.get("remote_commit"):
            up_to_date = summary["local_commit"] == summary["remote_commit"]
        payload_repos.append(
            {
                **summary,
                "up_to_date": up_to_date,
                "projections": projections,
                "setup": repo_setup_health(root, repo),
            }
        )
    return {"config": str(root / CONFIG_PATH), "repos": payload_repos}


def print_status(root: Path, repos: list[Repo]) -> int:
    for repo in repos:
        summary = repo_summary(repo)
        log(f"{repo.id}")
        log(f"  path: {summary['path']}")
        log(f"  ref: {repo.ref}")
        if repo.locked_commit:
            log(f"  locked: {short(repo.locked_commit)}")
        log(f"  exists: {'yes' if summary['exists'] else 'no'}")
        if summary["exists"]:
            log(f"  git: {'yes' if summary['git'] else 'no'}")
            log(f"  dirty: {'yes' if summary['dirty'] else 'no'}")
            log(f"  local: {short(summary['local_commit'])}")
        log(f"  remote: {short(summary['remote_commit'])}")
        if repo.locked_commit and summary.get("local_commit"):
            log("  up to date: " + ("yes" if summary["local_commit"] == repo.locked_commit else "no"))
        elif summary.get("local_commit") and summary.get("remote_commit"):
            log("  up to date: " + ("yes" if summary["local_commit"] == summary["remote_commit"] else "no"))
        for projection in repo.projections:
            health = projection_health(root, projection)
            state = "ok" if health["source_exists"] and health["target_exists"] and health["marker"] else "needs-sync"
            log(f"  projection {projection.target}: {state}")
        setup = repo_setup_health(root, repo)
        if setup:
            log(f"  setup: {setup['state']} ({setup['script']})")
            if setup.get("detail") and setup["state"] != "ok":
                log(f"    {setup['detail']}")
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
            run(["git", "clone", repo.url, str(repo.path)])
            run(["git", "checkout", repo.locked_commit or repo.ref], cwd=repo.path)
        return True

    ensure_clean_repo(repo)
    if not is_git_repo(repo.path):
        raise SystemExit(f"Dependency path exists but is not a Git repo: {repo.path}")

    local = git_rev(repo.path, "HEAD")
    if repo.locked_commit:
        if local == repo.locked_commit:
            log(f"Repo locked current: {repo.id} ({short(local)})")
            return False
        log(f"Checkout locked {repo.id}: {short(local)} -> {short(repo.locked_commit)}")
        if apply:
            run(["git", "fetch", "--prune", "--tags", "origin"], cwd=repo.path)
            run(["git", "checkout", repo.locked_commit], cwd=repo.path)
        return True

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
    payload: dict[str, Any] = {
        "managed_by": "vault deps",
        "repo_id": projection.repo_id,
        "source": projection.source,
        "target": projection.target,
        "type": projection.type,
    }
    if projection.title_override is not None:
        payload["title_override"] = projection.title_override
    if projection.skill_prefix is not None:
        payload["skill_prefix"] = projection.skill_prefix
    if projection.rewrite_skill_sources:
        payload["rewrite_skill_sources"] = list(projection.rewrite_skill_sources)
    return payload


SKILL_NAME_RE = re.compile(r"(?m)^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$")
TITLE_ACRONYMS = {
    "ai",
    "api",
    "cro",
    "gsc",
    "gtm",
    "gws",
    "seo",
    "sms",
    "sxo",
    "ui",
    "ux",
}


def display_title_segment(value: str) -> str:
    return " ".join(
        word.upper() if word in TITLE_ACRONYMS else word.capitalize()
        for word in value.removeprefix("_").split("-")
    )


def projection_title_prefix(target: str) -> str | None:
    parts = Path(target).parts
    source_index = next(
        (index for index, part in enumerate(parts) if part in {"auto-skills", "manual-skills"}),
        None,
    )
    if source_index is None:
        return None
    groups = [part for part in parts[source_index + 1 : -1] if part.startswith("_")]
    root_pack_groups = {
        "_claude-seo",
        "_corey-marketing-skills",
        "_swan-gtm-skills",
    }
    if len(groups) < 2 and (len(groups) != 1 or groups[0] not in root_pack_groups):
        return None
    return " · ".join(display_title_segment(group) for group in groups)


def projected_skill_text(source: Path, projection: Projection) -> str:
    text = source.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"Skill frontmatter missing: {source}")
    frontmatter_end = text.find("\n---", 4)
    if frontmatter_end == -1:
        raise SystemExit(f"Skill frontmatter malformed: {source}")
    frontmatter = text[4:frontmatter_end]
    if not SKILL_NAME_RE.search(frontmatter):
        raise SystemExit(f"Skill frontmatter name missing: {source}")
    local_name = Path(projection.target).name
    frontmatter = SKILL_NAME_RE.sub(f"name: {local_name}", frontmatter, count=1)
    body = text[frontmatter_end + len("\n---") :]
    title_prefix = projection_title_prefix(projection.target)
    if projection.title_override is not None or title_prefix is not None:
        lines = body.splitlines(keepends=True)
        fence: str | None = None
        replaced = False
        for index, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                marker = stripped[:3]
                fence = None if fence == marker else marker if fence is None else fence
                continue
            if fence is None and line.startswith("# "):
                ending = "\n" if line.endswith("\n") else ""
                title = projection.title_override
                if title is None:
                    title = f"{title_prefix} · {line[2:].strip()}"
                lines[index] = f"# {title}{ending}"
                replaced = True
                break
        if replaced:
            body = "".join(lines)
        else:
            display_name = local_name
            if projection.skill_prefix:
                display_name = display_name.removeprefix(projection.skill_prefix)
            title = projection.title_override or (
                f"{title_prefix} · {display_title_segment(display_name)}"
            )
            body = f"\n\n# {title}\n\n" + body.lstrip("\r\n")
    return "---\n" + frontmatter + "\n---" + body


def skill_metadata(source: Path, allowed: bool) -> str:
    metadata = source / "agents/openai.yaml"
    text = metadata.read_text(encoding="utf-8") if metadata.exists() else ""
    value = "true" if allowed else "false"
    policy = re.compile(
        r"(?m)^(\s*allow_implicit_invocation:\s*)(?:true|false)(\s*(?:#.*)?)$"
    )
    if policy.search(text):
        return policy.sub(rf"\g<1>{value}\g<2>", text, count=1)
    heading = re.search(r"(?m)^policy:\s*(?:#.*)?$", text)
    if heading:
        return text[: heading.end()] + f"\n  allow_implicit_invocation: {value}" + text[heading.end() :]
    suffix = "" if not text or text.endswith("\n") else "\n"
    return text + suffix + f"policy:\n  allow_implicit_invocation: {value}\n"


def expected_projection_children(source: Path, *, skip_agents: bool) -> list[Path]:
    skipped = {".DS_Store", MANAGED_MARKER}
    if skip_agents:
        skipped.add("agents")
    return [
        child
        for child in sorted(source.iterdir(), key=lambda p: p.name)
        if child.name not in skipped
    ]


def skill_projection_current(
    target: Path,
    source: Path,
    projection: Projection,
    *,
    allowed: bool,
) -> bool:
    marker = read_marker(target)
    if marker != marker_payload(projection):
        return False
    metadata = target / "agents/openai.yaml"
    if not metadata.exists() or metadata.read_text(encoding="utf-8") != skill_metadata(source, allowed):
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
        source_child = expected[name]
        if target_child.is_symlink():
            return False
        if source_child.is_dir():
            if not target_child.is_dir() or not directories_equal(source_child, target_child):
                return False
        elif not target_child.is_file():
            return False
        elif name == "SKILL.md":
            if target_child.read_text(encoding="utf-8") != projected_skill_text(source_child, projection):
                return False
        elif target_child.read_bytes() != source_child.read_bytes():
            return False
    return True


def directories_equal(source: Path, target: Path) -> bool:
    comparison = filecmp.dircmp(source, target)
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    if any(not filecmp.cmp(source / name, target / name, shallow=False) for name in comparison.common_files):
        return False
    return all(directories_equal(source / name, target / name) for name in comparison.common_dirs)


def create_skill_projection(
    root: Path,
    projection: Projection,
    apply: bool,
    *,
    allowed: bool,
) -> bool:
    source = projection.repo_path / projection.source
    target = vault_path(root, projection.target)
    if not source.exists():
        raise SystemExit(f"Projection source missing: {source}")
    if not (source / "SKILL.md").exists():
        raise SystemExit(f"Skill projection source lacks SKILL.md: {source}")

    existing = target.exists() or target.is_symlink()
    marker = read_marker(target)
    if existing:
        if marker.get("managed_by") == "vault deps":
            if target.is_dir() and skill_projection_current(
                target, source, projection, allowed=allowed
            ):
                log(f"Projection current: {target}")
                return False
            log(f"Rebuild managed projection: {target}")
            if apply:
                remove_path(target)
        else:
            backup_path(root, target, target.name, apply)

    kind = "auto" if allowed else "manual"
    log(f"Project {kind} skill {source} -> {target}")
    if not apply:
        return True

    target.mkdir(parents=True, exist_ok=True)
    for child in expected_projection_children(source, skip_agents=True):
        if child.is_dir():
            shutil.copytree(child, target / child.name)
        elif child.name == "SKILL.md":
            (target / child.name).write_text(projected_skill_text(child, projection), encoding="utf-8")
        else:
            shutil.copy2(child, target / child.name)

    agents_dir = target / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "openai.yaml").write_text(skill_metadata(source, allowed), encoding="utf-8")
    write_json(projection_marker(target), marker_payload(projection))
    return True


def create_manual_skill_projection(root: Path, projection: Projection, apply: bool) -> bool:
    return create_skill_projection(root, projection, apply, allowed=False)


def create_auto_skill_projection(root: Path, projection: Projection, apply: bool) -> bool:
    return create_skill_projection(root, projection, apply, allowed=True)


def pack_skill_sources(source: Path) -> list[Path]:
    skills: list[Path] = []
    for child in sorted(source.iterdir(), key=lambda path: path.name):
        if child.name in {".DS_Store", MANAGED_MARKER} or child.is_file():
            continue
        if child.is_symlink() or not child.is_dir() or not (child / "SKILL.md").is_file():
            raise SystemExit(f"Skill pack contains a non-skill directory: {child}")
        skills.append(child)
    if not skills:
        raise SystemExit(f"Skill pack contains no skills: {source}")
    return skills


def validate_skill_prefix(prefix: str | None) -> str:
    if not prefix or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-", prefix):
        raise SystemExit(f"Skill pack prefix must be lowercase kebab-case ending in '-': {prefix!r}")
    return prefix


def rewrite_pack_markdown(text: str, skill_names: list[str], prefix: str) -> str:
    for name in sorted(skill_names, key=len, reverse=True):
        text = text.replace(f"](./{name}/", f"](./{prefix}{name}/")
        invocation = re.compile(
            rf"(?<![A-Za-z0-9._/-])/{re.escape(name)}(?![A-Za-z0-9-])"
        )
        text = invocation.sub(f"/{prefix}{name}", text)
    return text


def pack_child_projection(projection: Projection, source: Path, target: Path) -> Projection:
    return Projection(
        repo_id=projection.repo_id,
        repo_path=projection.repo_path,
        source=source.relative_to(projection.repo_path).as_posix(),
        target=target.as_posix(),
        type="manual-skill",
        managed=True,
        title_override=None,
        skill_prefix=projection.skill_prefix,
        rewrite_skill_sources=projection.rewrite_skill_sources,
    )


def pack_rewrite_skill_names(projection: Projection, local_skills: list[Path]) -> list[str]:
    if not projection.rewrite_skill_sources:
        return [skill.name for skill in local_skills]
    names: set[str] = set()
    for relative in projection.rewrite_skill_sources:
        source = projection.repo_path / relative
        if not source.is_dir():
            raise SystemExit(f"Skill pack rewrite source missing: {source}")
        names.update(skill.name for skill in pack_skill_sources(source))
    return sorted(names)


def expected_pack_skill_files(
    source: Path,
    projection: Projection,
    skill_names: list[str],
    prefix: str,
) -> dict[Path, bytes]:
    expected: dict[Path, bytes] = {}
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if not relative.parts or relative.parts[0] == "agents" or item.is_dir():
            continue
        if item.name in {".DS_Store", MANAGED_MARKER}:
            continue
        if relative == Path("SKILL.md"):
            text = projected_skill_text(item, projection)
            expected[relative] = rewrite_pack_markdown(text, skill_names, prefix).encode()
        elif item.suffix.lower() == ".md":
            text = item.read_text(encoding="utf-8")
            expected[relative] = rewrite_pack_markdown(text, skill_names, prefix).encode()
        else:
            expected[relative] = item.read_bytes()
    expected[Path("agents/openai.yaml")] = skill_metadata(source, allowed=False).encode()
    return expected


def pack_skill_contents_current(target: Path, expected: dict[Path, bytes]) -> bool:
    if not target.is_dir() or target.is_symlink():
        return False
    actual = {
        item.relative_to(target)
        for item in target.rglob("*")
        if item.is_file() or item.is_symlink()
    }
    if actual != set(expected):
        return False
    return all(
        not (target / relative).is_symlink()
        and (target / relative).read_bytes() == content
        for relative, content in expected.items()
    )


def skill_pack_projection_current(
    target: Path,
    source: Path,
    projection: Projection,
    skills: list[Path],
    prefix: str,
) -> bool:
    if read_marker(target) != marker_payload(projection):
        return False
    skill_names = pack_rewrite_skill_names(projection, skills)
    expected_root_files = {
        item.name: rewrite_pack_markdown(item.read_text(encoding="utf-8"), skill_names, prefix).encode()
        if item.suffix.lower() == ".md"
        else item.read_bytes()
        for item in source.iterdir()
        if item.is_file() and item.name not in {".DS_Store", MANAGED_MARKER}
    }
    expected_root_entries = set(expected_root_files) | {
        f"{prefix}{skill.name}" for skill in skills
    } | {MANAGED_MARKER}
    if {item.name for item in target.iterdir()} != expected_root_entries:
        return False
    for name, content in expected_root_files.items():
        item = target / name
        if item.is_symlink() or not item.is_file() or item.read_bytes() != content:
            return False
    for skill in skills:
        child_target = target / f"{prefix}{skill.name}"
        child_projection = pack_child_projection(
            projection, skill, Path(projection.target) / child_target.name
        )
        expected = expected_pack_skill_files(skill, child_projection, skill_names, prefix)
        if not pack_skill_contents_current(child_target, expected):
            return False
    return True


def create_manual_skill_pack_projection(root: Path, projection: Projection, apply: bool) -> bool:
    source = projection.repo_path / projection.source
    target = vault_path(root, projection.target)
    if not source.is_dir():
        raise SystemExit(f"Skill pack projection source missing: {source}")
    prefix = validate_skill_prefix(projection.skill_prefix)
    skills = pack_skill_sources(source)
    if target.is_dir() and skill_pack_projection_current(
        target, source, projection, skills, prefix
    ):
        log(f"Projection current: {target}")
        return False

    existing = target.exists() or target.is_symlink()
    marker = read_marker(target)
    if existing:
        if marker.get("managed_by") == "vault deps":
            log(f"Rebuild managed projection: {target}")
            if apply:
                remove_path(target)
        else:
            backup_path(root, target, target.name, apply)

    log(f"Project manual skill pack {source} -> {target} ({prefix}*)")
    if not apply:
        return True

    target.mkdir(parents=True, exist_ok=True)
    skill_names = pack_rewrite_skill_names(projection, skills)
    for item in sorted(source.iterdir(), key=lambda path: path.name):
        if not item.is_file() or item.name in {".DS_Store", MANAGED_MARKER}:
            continue
        destination = target / item.name
        if item.suffix.lower() == ".md":
            destination.write_text(
                rewrite_pack_markdown(item.read_text(encoding="utf-8"), skill_names, prefix),
                encoding="utf-8",
            )
        else:
            shutil.copy2(item, destination)
    for skill in skills:
        child_target = target / f"{prefix}{skill.name}"
        child_projection = pack_child_projection(
            projection, skill, Path(projection.target) / child_target.name
        )
        expected = expected_pack_skill_files(skill, child_projection, skill_names, prefix)
        for relative, content in expected.items():
            destination = child_target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    write_json(projection_marker(target), marker_payload(projection))
    return True


def apply_projection(root: Path, projection: Projection, apply: bool) -> bool:
    if not projection.managed:
        log(f"Skip unmanaged projection: {projection.target}")
        return False
    if projection.type == "manual-skill":
        return create_manual_skill_projection(root, projection, apply)
    if projection.type == "auto-skill":
        return create_auto_skill_projection(root, projection, apply)
    if projection.type == "manual-skill-pack":
        return create_manual_skill_pack_projection(root, projection, apply)
    raise SystemExit(f"Unknown projection type for {projection.target}: {projection.type}")


def run_skill_sync(root: Path, apply: bool) -> None:
    script = root / SKILL_SYNC
    flag = "--apply" if apply else "--dry-run"
    log(f"Run skill sync: {script} {flag}")
    if apply:
        subprocess.run(
            [sys.executable, str(script), "sync", "--root", str(root), flag],
            cwd=root,
            check=True,
        )


def run_repo_setup(root: Path, repo: Repo, apply: bool, force_build: bool) -> None:
    script = repo_setup_script(root, repo)
    if not script:
        return
    flag = "--apply" if apply else "--dry-run"
    args = [
        sys.executable,
        str(script),
        "--root",
        str(root),
        "--repo",
        str(repo.path),
        flag,
    ]
    if force_build:
        args.append("--force-build")
    log(f"Run dependency setup: {repo.id} ({flag})")
    result = run(args, cwd=root, check=False)
    if result.stdout.strip():
        log(result.stdout.strip())
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Dependency setup failed for {repo.id}: {detail}")


def sync(root: Path, repos: list[Repo], apply: bool) -> int:
    skill_projection_touched = False
    setup_queue: list[tuple[Repo, bool]] = []
    for repo in repos:
        repo_missing_before = not repo.path.exists()
        repo_changed = sync_repo(repo, apply)
        if repo_missing_before and not apply:
            for projection in repo.projections:
                log(f"Projection pending after clone: {projection.target}")
        else:
            for projection in repo.projections:
                if apply_projection(root, projection, apply) and projection.type in {
                    "manual-skill",
                    "auto-skill",
                    "manual-skill-pack",
                }:
                    skill_projection_touched = True
        setup_queue.append((repo, repo_changed))
    if skill_projection_touched:
        run_skill_sync(root, apply)
    for repo, repo_changed in setup_queue:
        run_repo_setup(root, repo, apply, force_build=repo_changed)
    log("Done." if apply else "Dry run complete. Re-run with --apply to make these changes.")
    return 0


def project_auto_skills(root: Path, repos: list[Repo], apply: bool) -> int:
    """Repair auto-skill projections from existing checkouts without pulling or building repos."""
    touched = False
    for repo in repos:
        for projection in repo.projections:
            if projection.type != "auto-skill" or not projection.managed:
                continue
            source = projection.repo_path / projection.source
            if not source.exists():
                log(f"Skip missing auto-skill source: {source}")
                continue
            touched = apply_projection(root, projection, apply) or touched
    if touched:
        run_skill_sync(root, apply)
    log("Auto-skill projections repaired." if apply else "Auto-skill projection dry run complete.")
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
    sync_parser.add_argument(
        "--repo",
        action="append",
        dest="repo_ids",
        help="Sync only this dependency id; repeat to select multiple dependencies.",
    )
    mode = sync_parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview changes.")
    mode.add_argument("--apply", action="store_true", help="Apply changes.")
    project_parser = subparsers.add_parser(
        "project-auto-skills",
        help="Repair auto-skill projections from existing dependency checkouts without pulling or building.",
    )
    project_mode = project_parser.add_mutually_exclusive_group()
    project_mode.add_argument("--dry-run", action="store_true", help="Preview changes.")
    project_mode.add_argument("--apply", action="store_true", help="Apply changes.")
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
        if args.repo_ids:
            requested = set(args.repo_ids)
            known = {repo.id for repo in repos}
            missing = sorted(requested - known)
            if missing:
                raise SystemExit(f"Unknown dependency repo id: {', '.join(missing)}")
            repos = [repo for repo in repos if repo.id in requested]
        return sync(root, repos, apply=bool(args.apply))
    if args.command == "project-auto-skills":
        return project_auto_skills(root, repos, apply=bool(args.apply))
    print("Use `vault deps status`, `vault deps sync`, or `vault deps project-auto-skills`.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
