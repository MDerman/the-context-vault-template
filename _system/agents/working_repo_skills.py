#!/usr/bin/env python3
"""Plan and materialize selected working-repository skills into the Vault."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


MARKER = ".vault-working-repo-projection.json"
LEGACY_MARKER = ".vault-local-repo-projection.json"
REGISTRY = Path(
    "_system/local/skills/infra-code-folder-and-computer-topology/private/repositories.json"
)
WORKING_ROOT = Path("_system/agents/working-repos")
LEGACY_ROOT = Path("_system/agents/local-repos")
SKILL_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCAL_NAME_RE = re.compile(r"^l-[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_RE = re.compile(r"(?m)^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$")
POLICY_RE = re.compile(
    r"(?m)^(\s*allow_implicit_invocation:\s*)(?:true|false)(\s*(?:#.*)?)$"
)
LOCAL_REFERENCE_RE = re.compile(r"\$(l-[a-z0-9]+(?:-[a-z0-9]+)*)")
TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml"}
IGNORED_NAMES = {".DS_Store", "__pycache__", MARKER, LEGACY_MARKER}


class ProjectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectionSpec:
    repo_id: str
    repo_path: Path
    source: PurePosixPath
    mode: str
    local_name: str
    name: str
    target: Path


@dataclass(frozen=True)
class ProjectedFile:
    relative: PurePosixPath
    content: bytes
    executable: bool


@dataclass(frozen=True)
class ProjectionAction:
    kind: str
    target: Path
    files: tuple[ProjectedFile, ...] = ()


@dataclass(frozen=True)
class ProjectedSkill:
    name: str
    path: Path
    mode: str


@dataclass(frozen=True)
class ProjectionPlan:
    skills: tuple[ProjectedSkill, ...]
    actions: tuple[ProjectionAction, ...]
    warnings: tuple[str, ...]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProjectionError(f"Repository registry missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectionError(f"Repository registry is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectionError(f"Repository registry must contain an object: {path}")
    return value


def repo_title(repo_id: str) -> str:
    return " ".join("K3s" if part == "k3s" else part.title() for part in repo_id.split("-"))


def capability_title(local_name: str) -> str:
    words = local_name.removeprefix("l-").split("-")
    return " ".join("AI" if word == "ai" else word.title() for word in words)


def safe_source(value: object, repo_id: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ProjectionError(f"Repository {repo_id!r} skill projection needs a source")
    source = PurePosixPath(value)
    if source.is_absolute() or ".." in source.parts or source.as_posix() in {"", "."}:
        raise ProjectionError(f"Repository {repo_id!r} has unsafe skill source: {value!r}")
    return source


def load_specs(root: Path) -> list[ProjectionSpec]:
    if not (root / REGISTRY).is_file():
        return []
    registry = read_json(root / REGISTRY)
    repositories = registry.get("repositories")
    if not isinstance(repositories, dict):
        raise ProjectionError("Repository registry needs a repositories object")

    specs: list[ProjectionSpec] = []
    names: dict[str, ProjectionSpec] = {}
    targets: set[Path] = set()
    for repo_id, raw_repo in repositories.items():
        if not isinstance(repo_id, str) or not SKILL_RE.fullmatch(repo_id):
            raise ProjectionError(f"Invalid repository ID: {repo_id!r}")
        if not isinstance(raw_repo, dict):
            raise ProjectionError(f"Repository entry must be an object: {repo_id}")
        projections = raw_repo.get("skill_projections", [])
        if not isinstance(projections, list):
            raise ProjectionError(f"Repository {repo_id!r} skill_projections must be a list")
        raw_path = raw_repo.get("path")
        if projections and (not isinstance(raw_path, str) or not raw_path):
            raise ProjectionError(f"Repository {repo_id!r} needs a path for skill projections")
        repo_path = Path(os.path.expanduser(str(raw_path))).resolve() if raw_path else Path("/__missing__")

        for raw_projection in projections:
            if not isinstance(raw_projection, dict):
                raise ProjectionError(f"Repository {repo_id!r} skill projection must be an object")
            source = safe_source(raw_projection.get("source"), repo_id)
            mode = raw_projection.get("mode", "auto")
            if mode not in {"auto", "manual"}:
                raise ProjectionError(
                    f"Repository {repo_id!r} projection {source} has invalid mode {mode!r}"
                )
            local_name = source.name
            if not LOCAL_NAME_RE.fullmatch(local_name):
                raise ProjectionError(
                    f"Projected repository skill folder must use l-<capability>: {repo_id}:{source}"
                )
            name = f"{repo_id}-{local_name.removeprefix('l-')}"
            if not SKILL_RE.fullmatch(name) or len(name) > 64:
                raise ProjectionError(f"Derived projected skill name is invalid or over 64 characters: {name}")
            target = root / WORKING_ROOT / repo_id / name
            spec = ProjectionSpec(repo_id, repo_path, source, mode, local_name, name, target)
            if name in names:
                raise ProjectionError(
                    f"Duplicate projected skill name {name!r}: {names[name].source} and {source}"
                )
            if target in targets:
                raise ProjectionError(f"Duplicate projected skill target: {target}")
            names[name] = spec
            targets.add(target)
            specs.append(spec)
    return specs


def read_source_name(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ProjectionError(f"Repository skill frontmatter missing: {skill_file}")
    end = text.find("\n---", 4)
    if end == -1:
        raise ProjectionError(f"Repository skill frontmatter malformed: {skill_file}")
    match = NAME_RE.search(text[4:end])
    if not match:
        raise ProjectionError(f"Repository skill frontmatter name missing: {skill_file}")
    return match.group(1).strip()


def policy_text(text: str, allowed: bool) -> str:
    value = "true" if allowed else "false"
    if POLICY_RE.search(text):
        return POLICY_RE.sub(rf"\g<1>{value}\g<2>", text, count=1)
    policy = re.search(r"(?m)^policy:\s*(?:#.*)?$", text)
    if policy:
        insert = policy.end()
        return text[:insert] + f"\n  allow_implicit_invocation: {value}" + text[insert:]
    suffix = "" if not text or text.endswith("\n") else "\n"
    return text + suffix + f"policy:\n  allow_implicit_invocation: {value}\n"


def transform_references(text: str, sibling_names: dict[str, str], source: Path) -> str:
    dangling: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        local_name = match.group(1)
        projected = sibling_names.get(local_name)
        if projected is None:
            dangling.add(local_name)
            return match.group(0)
        return f"${projected}"

    result = LOCAL_REFERENCE_RE.sub(replace, text)
    if dangling:
        values = ", ".join(f"${name}" for name in sorted(dangling))
        raise ProjectionError(
            f"Projected skill {source} references unprojected repository skills: {values}"
        )
    return result


def transform_skill_text(text: str, spec: ProjectionSpec, source: Path) -> str:
    text, count = NAME_RE.subn(f"name: {spec.name}", text, count=1)
    if count != 1:
        raise ProjectionError(f"Could not rewrite projected skill name: {source}")
    heading = f"# {repo_title(spec.repo_id)} · {capability_title(spec.local_name)}"
    text, count = re.subn(r"(?m)^# .+$", heading, text, count=1)
    if count != 1:
        raise ProjectionError(f"Repository skill needs one H1: {source}")
    return text


def source_entries(source: Path) -> list[Path]:
    entries: list[Path] = []
    for path in sorted(source.rglob("*")):
        if any(part in IGNORED_NAMES for part in path.relative_to(source).parts):
            continue
        if path.is_symlink():
            raise ProjectionError(f"Repository skill projections do not follow symlinks: {path}")
        if path.is_file():
            entries.append(path)
    return entries


def digest_files(files: list[ProjectedFile]) -> str:
    digest = hashlib.sha256()
    for item in sorted(files, key=lambda value: value.relative.as_posix()):
        digest.update(item.relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(b"1" if item.executable else b"0")
        digest.update(b"\0")
        digest.update(item.content)
        digest.update(b"\0")
    return digest.hexdigest()


def build_projected_files(spec: ProjectionSpec, sibling_names: dict[str, str]) -> tuple[ProjectedFile, ...]:
    source = spec.repo_path.joinpath(*spec.source.parts)
    skill_file = source / "SKILL.md"
    if not skill_file.is_file():
        raise ProjectionError(f"Repository skill source lacks SKILL.md: {source}")
    declared = read_source_name(skill_file)
    if declared != spec.local_name:
        raise ProjectionError(
            f"Repository skill folder/name mismatch: {source} declares {declared!r}"
        )

    files: list[ProjectedFile] = []
    metadata_found = False
    for path in source_entries(source):
        relative = PurePosixPath(path.relative_to(source).as_posix())
        content = path.read_bytes()
        executable = bool(path.stat().st_mode & stat.S_IXUSR)
        if relative.as_posix() == "SKILL.md":
            text = transform_skill_text(content.decode("utf-8"), spec, path)
            text = transform_references(text, sibling_names, path)
            content = text.encode("utf-8")
        elif relative.as_posix() == "agents/openai.yaml":
            metadata_found = True
            text = policy_text(content.decode("utf-8"), spec.mode == "auto")
            content = transform_references(text, sibling_names, path).encode("utf-8")
        elif path.suffix.lower() in TEXT_SUFFIXES:
            text = transform_references(content.decode("utf-8"), sibling_names, path)
            content = text.encode("utf-8")
        files.append(ProjectedFile(relative, content, executable))

    if not metadata_found:
        metadata = policy_text("", spec.mode == "auto").encode("utf-8")
        files.append(ProjectedFile(PurePosixPath("agents/openai.yaml"), metadata, False))

    files.append(projection_marker(spec, digest_files(files)))
    return tuple(sorted(files, key=lambda value: value.relative.as_posix()))


def projection_marker(spec: ProjectionSpec, content_digest: str) -> ProjectedFile:
    marker = {
        "managed_by": "vault skills sync",
        "repo_id": spec.repo_id,
        "source": spec.source.as_posix(),
        "mode": spec.mode,
        "local_name": spec.local_name,
        "name": spec.name,
        "target": (
            WORKING_ROOT / spec.repo_id / spec.name
        ).as_posix(),
        "content_digest": content_digest,
    }
    return ProjectedFile(
        PurePosixPath(MARKER),
        (json.dumps(marker, indent=2) + "\n").encode("utf-8"),
        False,
    )


def actual_files(target: Path) -> tuple[ProjectedFile, ...]:
    files: list[ProjectedFile] = []
    for path in sorted(target.rglob("*")):
        if path.is_symlink():
            return ()
        if path.is_file():
            files.append(
                ProjectedFile(
                    PurePosixPath(path.relative_to(target).as_posix()),
                    path.read_bytes(),
                    bool(path.stat().st_mode & stat.S_IXUSR),
                )
            )
    return tuple(files)


def read_marker(target: Path, marker_name: str = MARKER) -> dict[str, Any]:
    marker = target / marker_name
    if not marker.is_file():
        return {}
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def marker_matches_spec(marker: dict[str, Any], spec: ProjectionSpec) -> bool:
    return all(
        marker.get(key) == value
        for key, value in {
            "managed_by": "vault skills sync",
            "repo_id": spec.repo_id,
            "source": spec.source.as_posix(),
            "mode": spec.mode,
            "local_name": spec.local_name,
            "name": spec.name,
            "target": (
                WORKING_ROOT / spec.repo_id / spec.name
            ).as_posix(),
        }.items()
    )


def legacy_marker_matches_spec(marker: dict[str, Any], spec: ProjectionSpec) -> bool:
    expected_target = (
        LEGACY_ROOT
        / spec.repo_id
        / ("auto-skills" if spec.mode == "auto" else "manual-skills")
        / spec.name
    ).as_posix()
    return all(
        marker.get(key) == value
        for key, value in {
            "managed_by": "vault skills sync",
            "repo_id": spec.repo_id,
            "source": spec.source.as_posix(),
            "mode": spec.mode,
            "local_name": spec.local_name,
            "name": spec.name,
            "target": expected_target,
        }.items()
    )


def migrate_legacy_files(spec: ProjectionSpec, target: Path) -> tuple[ProjectedFile, ...]:
    marker = read_marker(target, LEGACY_MARKER)
    if not legacy_marker_matches_spec(marker, spec):
        raise ProjectionError(f"Legacy managed projection is invalid: {target}")
    skill_file = target / "SKILL.md"
    if not skill_file.is_file() or read_source_name(skill_file) != spec.name:
        raise ProjectionError(f"Legacy managed projection SKILL.md is invalid: {skill_file}")
    files = [
        item
        for item in actual_files(target)
        if item.relative.as_posix() != LEGACY_MARKER
    ]
    files.append(projection_marker(spec, digest_files(files)))
    return tuple(sorted(files, key=lambda value: value.relative.as_posix()))


def validate_existing_projection(spec: ProjectionSpec, target: Path | None = None) -> None:
    target = target or spec.target
    marker = read_marker(target)
    if not marker_matches_spec(marker, spec):
        raise ProjectionError(
            f"Repository checkout is unavailable and managed projection is missing or invalid: {target}"
        )
    skill_file = target / "SKILL.md"
    if not skill_file.is_file() or read_source_name(skill_file) != spec.name:
        raise ProjectionError(f"Managed projection SKILL.md is invalid: {skill_file}")


def plan(root: Path, *, require_sources: bool = False) -> ProjectionPlan:
    specs = load_specs(root)
    by_repo: dict[str, dict[str, str]] = {}
    for spec in specs:
        by_repo.setdefault(spec.repo_id, {})[spec.local_name] = spec.name

    actions: list[ProjectionAction] = []
    warnings: list[str] = []
    skills: list[ProjectedSkill] = []
    desired_targets = {spec.target for spec in specs}
    working_root = root / WORKING_ROOT

    if working_root.is_dir():
        for marker_path in sorted(working_root.rglob(MARKER)):
            target = marker_path.parent
            if target not in desired_targets:
                marker = read_marker(target)
                if marker.get("managed_by") != "vault skills sync":
                    raise ProjectionError(f"Unmanaged working repository projection marker: {marker_path}")
                actions.append(ProjectionAction("remove", target))
        for skill_file in sorted(working_root.rglob("SKILL.md")):
            if not (skill_file.parent / MARKER).is_file():
                raise ProjectionError(f"Unmanaged skill inside generated working-repos tree: {skill_file.parent}")

    legacy_root = root / LEGACY_ROOT
    legacy_by_name: dict[str, Path] = {}
    if legacy_root.is_dir():
        for skill_file in sorted(legacy_root.rglob("SKILL.md")):
            target = skill_file.parent
            marker_path = target / LEGACY_MARKER
            if not marker_path.is_file():
                raise ProjectionError(
                    f"Unmanaged skill inside legacy generated local-repos tree: {target}"
                )
            marker = read_json(marker_path)
            if marker.get("managed_by") != "vault skills sync":
                raise ProjectionError(f"Unmanaged legacy repository projection marker: {marker_path}")
            name = marker.get("name")
            if not isinstance(name, str) or name in legacy_by_name:
                raise ProjectionError(f"Invalid or duplicate legacy repository projection: {target}")
            legacy_by_name[name] = target
            actions.append(ProjectionAction("remove", target))

    for spec in specs:
        source = spec.repo_path.joinpath(*spec.source.parts)
        if not spec.repo_path.exists():
            if spec.target.exists():
                validate_existing_projection(spec)
            else:
                legacy_target = legacy_by_name.get(spec.name)
                if legacy_target is None:
                    validate_existing_projection(spec)
                files = migrate_legacy_files(spec, legacy_target)
                actions.append(ProjectionAction("replace", spec.target, files))
            if require_sources:
                raise ProjectionError(
                    f"Required repository checkout is unavailable: {spec.repo_id}:{spec.repo_path}"
                )
            warnings.append(
                f"Repository checkout unavailable; preserving tracked projection: {spec.repo_id}:{spec.source}"
            )
        else:
            if not source.exists():
                if spec.target.exists():
                    validate_existing_projection(spec)
                else:
                    legacy_target = legacy_by_name.get(spec.name)
                    if legacy_target is None:
                        validate_existing_projection(spec)
                    files = migrate_legacy_files(spec, legacy_target)
                    actions.append(ProjectionAction("replace", spec.target, files))
                if require_sources:
                    raise ProjectionError(
                        f"Required projected skill source is missing: {source}"
                    )
                warnings.append(
                    f"Repository source unavailable; preserving tracked projection: {spec.repo_id}:{spec.source}"
                )
            else:
                files = build_projected_files(spec, by_repo[spec.repo_id])
                if spec.target.exists() and not read_marker(spec.target):
                    raise ProjectionError(f"Unmanaged content blocks working projection target: {spec.target}")
                if actual_files(spec.target) != files:
                    actions.append(ProjectionAction("replace", spec.target, files))
        skills.append(ProjectedSkill(spec.name, spec.target, spec.mode))

    return ProjectionPlan(tuple(skills), tuple(actions), tuple(warnings))


def write_projection(target: Path, files: tuple[ProjectedFile, ...]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    backup: Path | None = None
    try:
        for item in files:
            destination = staged.joinpath(*item.relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item.content)
            destination.chmod(0o755 if item.executable else 0o644)
        if target.exists():
            if read_marker(target).get("managed_by") != "vault skills sync":
                raise ProjectionError(f"Refusing to replace unmanaged projection target: {target}")
            backup = target.with_name(f".{target.name}.backup")
            if backup.exists():
                raise ProjectionError(f"Projection backup path already exists: {backup}")
            target.rename(backup)
        os.replace(staged, target)
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        if backup is not None and backup.exists() and not target.exists():
            backup.rename(target)
        raise


def apply(plan_value: ProjectionPlan, root: Path) -> None:
    for action in plan_value.actions:
        if action.kind == "replace":
            write_projection(action.target, action.files)
        elif action.kind == "remove":
            marker = read_marker(action.target)
            if not marker:
                marker = read_marker(action.target, LEGACY_MARKER)
            if marker.get("managed_by") != "vault skills sync":
                raise ProjectionError(f"Refusing to remove unmanaged projection target: {action.target}")
            shutil.rmtree(action.target)
        else:
            raise AssertionError(action.kind)

    for generated_root in (root / WORKING_ROOT, root / LEGACY_ROOT):
        if not generated_root.is_dir():
            continue
        for folder in sorted(
            (path for path in generated_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(folder.iterdir()):
                folder.rmdir()
        if generated_root.is_dir() and not any(generated_root.iterdir()):
            generated_root.rmdir()
