#!/usr/bin/env python3
"""Validate skill sources and rebuild vault/global discovery links."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GROUP_RE = re.compile(r"^_[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_RE = re.compile(r"(?m)^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$")
POLICY_RE = re.compile(r"(?m)^(\s*allow_implicit_invocation:\s*)(?:true|false)(\s*(?:#.*)?)$")
MARKER = ".vault-deps-projection.json"
IGNORED = {".DS_Store", ".gitkeep", "README.md"}


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    source: str


@dataclass(frozen=True)
class Change:
    description: str
    action: str
    path: Path
    value: str | None = None


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def read_skill_name(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SyncError(f"Skill frontmatter missing: {skill_file}")
    end = text.find("\n---", 4)
    if end == -1:
        raise SyncError(f"Skill frontmatter malformed: {skill_file}")
    match = NAME_RE.search(text[4:end])
    if not match:
        raise SyncError(f"Skill frontmatter name missing: {skill_file}")
    return match.group(1).strip()


def scan_source(root: Path, source: str) -> list[Skill]:
    if not root.is_dir():
        raise SyncError(f"Skill source missing: {root}")
    found: list[Skill] = []

    def walk(folder: Path) -> None:
        for child in sorted(folder.iterdir(), key=lambda item: item.name):
            if child.name in IGNORED:
                continue
            if child.is_symlink() or not child.is_dir():
                raise SyncError(f"Malformed source entry; expected group or skill directory: {child}")
            skill_file = child / "SKILL.md"
            if skill_file.is_file():
                if not SKILL_RE.fullmatch(child.name):
                    raise SyncError(f"Invalid skill folder name: {child}")
                declared = read_skill_name(skill_file)
                if declared != child.name:
                    raise SyncError(
                        f"Skill folder/name mismatch: {child} declares {declared!r}; rename folder or frontmatter"
                    )
                found.append(Skill(child.name, child, source))
                continue
            if not GROUP_RE.fullmatch(child.name):
                raise SyncError(
                    f"Organizer folder must use _lower-kebab and skill folders need SKILL.md: {child}"
                )
            walk(child)

    walk(root)
    return found


def policy_text(path: Path, allowed: bool) -> str:
    value = "true" if allowed else "false"
    if not path.exists():
        return f"policy:\n  allow_implicit_invocation: {value}\n"
    text = path.read_text(encoding="utf-8")
    if POLICY_RE.search(text):
        return POLICY_RE.sub(rf"\g<1>{value}\g<2>", text, count=1)
    policy = re.search(r"(?m)^policy:\s*(?:#.*)?$", text)
    if policy:
        insert = policy.end()
        return text[:insert] + f"\n  allow_implicit_invocation: {value}" + text[insert:]
    suffix = "" if not text or text.endswith("\n") else "\n"
    return text + suffix + f"policy:\n  allow_implicit_invocation: {value}\n"


def marker_key(payload: dict[str, Any]) -> tuple[str, str] | None:
    repo_id = payload.get("repo_id")
    source = payload.get("source")
    if not repo_id or not source:
        return None
    return str(repo_id), str(source)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dependency_changes(root: Path, skills: list[Skill]) -> list[Change]:
    config_path = root / "_master/system/config/deps.json"
    if not config_path.exists():
        return []
    config = load_json(config_path)
    projections: dict[tuple[str, str], dict[str, Any]] = {}
    projection_names: dict[str, tuple[str, str]] = {}
    skill_markers: dict[str, tuple[str, str]] = {}
    skill_by_name = {skill.name: skill for skill in skills}
    for skill in skills:
        marker_path = skill.path / MARKER
        if marker_path.is_file():
            key = marker_key(load_json(marker_path))
            if key:
                skill_markers[skill.name] = key
    for repo in config.get("repos", []):
        repo_id = str(repo.get("id", ""))
        for projection in repo.get("projections", []):
            key = (repo_id, str(projection.get("source", "")))
            projections[key] = projection
            if projection.get("type") not in {"manual-skill", "auto-skill", "active-skill"}:
                continue
            name = Path(str(projection.get("target", ""))).name
            if not SKILL_RE.fullmatch(name):
                raise SyncError(f"Invalid dependency skill target name: {projection.get('target')}")
            if name in projection_names and projection_names[name] != key:
                raise SyncError(f"Duplicate dependency skill name {name!r}: {projection_names[name]} and {key}")
            projection_names[name] = key
            if name in skill_by_name and skill_markers.get(name) != key:
                raise SyncError(
                    f"Dependency skill name {name!r} collides with unmanaged source: {skill_by_name[name].path}"
                )

    changes: list[Change] = []
    config_changed = False
    for skill in skills:
        marker_path = skill.path / MARKER
        if not marker_path.is_file():
            continue
        marker = load_json(marker_path)
        key = marker_key(marker)
        if not key or key not in projections:
            raise SyncError(f"Dependency projection marker has no deps.json match: {marker_path}")
        projection = projections[key]
        expected_target = skill.path.relative_to(root).as_posix()
        expected_type = "auto-skill" if skill.source == "auto" else "manual-skill"
        if projection.get("target") != expected_target:
            projection["target"] = expected_target
            config_changed = True
        if projection.get("type") != expected_type:
            projection["type"] = expected_type
            config_changed = True
        expected_marker = {
            "managed_by": "vault deps",
            "repo_id": key[0],
            "source": key[1],
            "target": expected_target,
            "type": expected_type,
        }
        marker_rendered = json.dumps(expected_marker, indent=2) + "\n"
        if marker_path.read_text(encoding="utf-8") != marker_rendered:
            changes.append(Change(f"Update dependency marker: {marker_path}", "write", marker_path, marker_rendered))
    if config_changed:
        rendered = json.dumps(config, indent=2) + "\n"
        changes.insert(0, Change(f"Update dependency config: {config_path}", "write", config_path, rendered))
    return changes


def resolved_target(link: Path) -> Path:
    raw = Path(os.readlink(link))
    return (link.parent / raw).resolve(strict=False) if not raw.is_absolute() else raw.resolve(strict=False)


def owned_global_link(link: Path, catalog: Path) -> bool:
    if not link.is_symlink():
        return False
    target = resolved_target(link)
    return target == catalog or is_relative_to(target, catalog)


def plan_catalog(catalog: Path, skills: list[Skill]) -> list[Change]:
    desired = {skill.name: skill.path for skill in skills}
    changes: list[Change] = []
    if catalog.exists() and not catalog.is_dir():
        raise SyncError(f"Active skill catalog must be directory: {catalog}")
    if not catalog.exists():
        changes.append(Change(f"Create active skill catalog: {catalog}", "mkdir", catalog))
        existing: list[Path] = []
    else:
        existing = list(catalog.iterdir())
    for entry in sorted(existing, key=lambda item: item.name):
        if entry.name in {".DS_Store", ".gitkeep"}:
            changes.append(Change(f"Remove catalog housekeeping entry: {entry}", "remove", entry))
            continue
        target = desired.get(entry.name)
        if target is None:
            if entry.is_symlink():
                changes.append(Change(f"Remove stale active link: {entry}", "remove", entry))
                continue
            raise SyncError(
                f"Unexpected real content in generated catalog: {entry}; move it into auto-skills or manual-skills"
            )
        expected = os.path.relpath(target, catalog)
        if entry.is_symlink():
            if os.readlink(entry) != expected:
                changes.append(Change(f"Rebuild active link: {entry} -> {expected}", "symlink", entry, expected))
        else:
            raise SyncError(
                f"Unmanaged catalog collision: {entry}; move it into a source folder before syncing"
            )
    for name, target in sorted(desired.items()):
        entry = catalog / name
        if not (entry.exists() or entry.is_symlink()):
            changes.append(Change(f"Create active link: {entry}", "symlink", entry, os.path.relpath(target, catalog)))
    return changes


def plan_discovery(home: Path, catalog: Path, names: set[str]) -> list[Change]:
    changes: list[Change] = []
    legacy_codex = home / ".codex/skills"
    if legacy_codex.is_symlink() and resolved_target(legacy_codex) == catalog.resolve(strict=False):
        changes.append(Change(f"Remove owned legacy Codex skill link: {legacy_codex}", "remove", legacy_codex))

    targets = [home / ".agents/skills", home / ".claude/skills", home / ".kilo/skills"]
    if (home / ".kilocode").exists():
        targets.append(home / ".kilocode/skills")

    for directory in targets:
        if directory.is_symlink():
            if resolved_target(directory) != catalog.resolve(strict=False):
                raise SyncError(f"Unmanaged discovery directory symlink blocks sync: {directory}")
            changes.append(Change(f"Replace owned whole-directory link with directory: {directory}", "replace-dir", directory))
            entries: list[Path] = []
        elif directory.exists():
            if not directory.is_dir():
                raise SyncError(f"Discovery path is not directory: {directory}")
            entries = list(directory.iterdir())
        else:
            changes.append(Change(f"Create discovery directory: {directory}", "mkdir", directory))
            entries = []

        by_name = {entry.name: entry for entry in entries}
        for entry in entries:
            if owned_global_link(entry, catalog) and entry.name not in names:
                changes.append(Change(f"Remove stale managed discovery link: {entry}", "remove", entry))
        for name in sorted(names):
            entry = by_name.get(name)
            expected = catalog / name
            if entry is None:
                changes.append(Change(f"Create discovery link: {directory / name}", "symlink", directory / name, str(expected)))
            elif entry.is_symlink() and resolved_target(entry) == expected.resolve(strict=False):
                continue
            elif owned_global_link(entry, catalog):
                changes.append(Change(f"Rebuild discovery link: {entry}", "symlink", entry, str(expected)))
            else:
                raise SyncError(f"Unmanaged global skill collision: {entry}; rename or remove it, then rerun sync")
    return changes


def apply_changes(changes: list[Change]) -> None:
    for change in changes:
        path = change.path
        if change.action == "mkdir":
            path.mkdir(parents=True, exist_ok=True)
        elif change.action == "remove":
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
            elif path.exists():
                shutil.rmtree(path)
        elif change.action == "replace-dir":
            path.unlink()
            path.mkdir(parents=True, exist_ok=True)
        elif change.action == "write":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(change.value or "", encoding="utf-8")
        elif change.action == "symlink":
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(change.value or "", target_is_directory=True)
        else:
            raise AssertionError(change.action)


def sync(root: Path, home: Path, apply: bool) -> int:
    agents = root / "_master/agents"
    catalog = agents / "skills"
    skills = [
        *scan_source(agents / "auto-skills", "auto"),
        *scan_source(agents / "manual-skills", "manual"),
        *scan_source(agents / "gh-skills", "gh"),
    ]
    names: dict[str, Skill] = {}
    for skill in skills:
        if skill.name in names:
            raise SyncError(f"Duplicate skill name {skill.name!r}: {names[skill.name].path} and {skill.path}")
        names[skill.name] = skill

    changes = dependency_changes(root, skills)
    for skill in skills:
        if skill.source not in {"auto", "manual"}:
            continue
        metadata = skill.path / "agents/openai.yaml"
        rendered = policy_text(metadata, skill.source == "auto")
        current = metadata.read_text(encoding="utf-8") if metadata.exists() else None
        if current != rendered:
            changes.append(Change(f"Enforce {skill.source} policy: {metadata}", "write", metadata, rendered))
    changes.extend(plan_catalog(catalog, skills))
    changes.extend(plan_discovery(home, catalog, set(names)))

    for change in changes:
        print(("APPLY " if apply else "PLAN  ") + change.description)
    if apply:
        apply_changes(changes)
        print(f"Synced {len(skills)} skills; {len(changes)} changes applied.")
    else:
        print(f"Validated {len(skills)} skills; {len(changes)} changes planned.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and sync vault skill sources.")
    parser.add_argument("command", choices=["sync"])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview changes (default).")
    mode.add_argument("--apply", action="store_true", help="Apply changes.")
    parser.add_argument("--root", type=Path, help="Vault root override.")
    parser.add_argument("--home", type=Path, help="Home directory override for tests.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    home = (args.home or Path.home()).resolve()
    try:
        return sync(root, home, args.apply)
    except (SyncError, json.JSONDecodeError, OSError) as exc:
        print(f"Skill sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
