#!/usr/bin/env python3
"""Export a public bootstrap vault from the current vault state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from script_utils import context_folder_note_path, resolve_vault_root
from vault_layout import BOOTSTRAP_DIR, DEPENDENCY_CONFIG_PATH, EXPORT_MANIFEST_PATH


DEFAULT_CONFIG = str(BOOTSTRAP_DIR / "bootstrap-export.json")
DEFAULT_MANIFEST_NAME = str(EXPORT_MANIFEST_PATH)
PUBLIC_WORKSPACE_FILE = "README.md"
MANIFEST_VERSION = 1
GLOBAL_EXCLUDE_SUFFIXES = (".bak",)
PRIVATE_EXPORT_DROP_LINE_MARKER = "private-export: drop-line"
PRIVATE_EXPORT_DROP_LINKS = (
    "[[personal/Daily What To Do|Daily What To Do]]",
)
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|secret[_-]?key)\b"
            r"\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{24,}['\"]"
        ),
    ),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def posix(path: Path) -> str:
    return path.as_posix()


def is_nonempty_dir(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def split_yaml_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[: index + 1]).rstrip() + "\n", "".join(lines[index + 1 :])
    return "", text


def parse_frontmatter(text: str) -> dict[str, str]:
    frontmatter, _body = split_yaml_frontmatter(text)
    if not frontmatter:
        return {}
    lines = frontmatter.splitlines()[1:-1]
    result: dict[str, str] = {}
    for line in lines:
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def bool_frontmatter(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "1"}


def join_frontmatter_and_body(frontmatter: str, body: str) -> str:
    body = body.strip() + "\n" if body.strip() else ""
    if not frontmatter:
        return body
    if not body:
        return frontmatter.rstrip() + "\n"
    return frontmatter.rstrip() + "\n\n" + body


def public_description_text(description: list[str]) -> str:
    lines = [line.strip() for line in description if isinstance(line, str) and line.strip()]
    if not lines:
        return "Use this folder for notes, tasks, projects, and reference material for this area."
    return "\n\n".join(lines)


class BootstrapExporter:
    def __init__(
        self,
        *,
        root: Path,
        config: dict[str, Any],
        export_root: Path | None,
        force: bool,
        dry_run: bool,
    ) -> None:
        self.root = root
        self.config = config
        self.export_root = (export_root or Path(config["export_root"])).expanduser().resolve()
        self.force = force
        self.dry_run = dry_run
        self.context_configs = config.get("context_folders", [])
        self.context_pairs = [
            (item["source"], item["target"])
            for item in self.context_configs
        ]
        self.public_context_scaffold_dirs = config.get("public_context_scaffold_dirs", {})
        self.rewrite_pairs = sorted(self.context_pairs, key=lambda pair: len(pair[0]), reverse=True)
        self.generated_exclude_paths = set(config.get("generated_exclude_paths", []))
        self.generated_exclude_globs = list(config.get("generated_exclude_globs", []))
        self.system_root_markdown_allow_paths = set(
            config.get("system_root_markdown_allow_paths", [])
        )
        self.global_exclude_names = set(config.get("global_exclude_names", []))
        self.sensitive_exclude_names = {name.lower() for name in config.get("sensitive_exclude_names", [])}
        self.text_rewrite_suffixes = set(config.get("text_rewrite_suffixes", []))
        self.repo_preserve_names = set(config.get("repo_preserve_names", []))
        self.obsidian_exclude_globs = list(config.get("obsidian_exclude_globs", []))
        self.obsidian_plugin_full_copy_plugins = set(
            config.get("obsidian_plugin_exact_copy_plugins")
            or config.get("obsidian_plugin_full_copy_plugins", [])
        )
        self.obsidian_plugin_public_files = set(
            config.get("obsidian_plugin_public_files", ["manifest.json", "styles.css"])
        )
        self.manifest_name = config.get("manifest_name", DEFAULT_MANIFEST_NAME)
        self.exported_paths: set[str] = set()
        self.explicit_root_names = self.collect_explicit_root_names()
        self.dependency_projection_targets = self.load_dependency_projection_targets()

    def load_dependency_projection_targets(self) -> set[Path]:
        config_path = self.root / DEPENDENCY_CONFIG_PATH
        if not config_path.is_file():
            return set()
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        targets: set[Path] = set()
        for repo in data.get("repos", []):
            for projection in repo.get("projections", []):
                if not projection.get("managed", True):
                    continue
                target = Path(str(projection.get("target", "")))
                if not target.parts or target.is_absolute() or ".." in target.parts:
                    continue
                targets.add(target)
        return targets

    def log(self, message: str) -> None:
        prefix = "[dry-run] " if self.dry_run else ""
        print(f"{prefix}{message}")

    def rel(self, path: Path) -> str:
        try:
            return posix(path.relative_to(self.root))
        except ValueError:
            try:
                return posix(path.relative_to(self.export_root))
            except ValueError:
                return str(path)

    def run(self) -> None:
        self.validate()
        self.prepare_export_root()
        self.copy_root_files()
        self.copy_obsidian()
        self.copy_system_or_shared("_system")
        self.copy_context_folders()
        self.regenerate_public_bases()
        self.validate_public_base_contexts()
        self.create_library_and_wiki()
        self.write_manifest()
        self.log(f"export ready: {self.export_root}")

    def validate(self) -> None:
        if self.export_root == self.root or is_relative_to(self.export_root, self.root):
            raise SystemExit(f"Refusing to export inside the source vault: {self.export_root}")
        for source, _target in self.context_pairs:
            source_path = self.root / source
            if not source_path.is_dir():
                raise SystemExit(f"Missing source context folder: {source}")
        if self.config.get("copy_obsidian") != "exact":
            raise SystemExit("Only copy_obsidian='exact' is supported.")

    def prepare_export_root(self) -> None:
        if is_nonempty_dir(self.export_root):
            if not self.force and not self.dry_run:
                raise SystemExit(f"Export directory is not empty; pass --force to replace it: {self.export_root}")
            if self.force or self.dry_run:
                self.clean_existing_export()
        self.ensure_dir(self.export_root)

    def collect_explicit_root_names(self) -> set[str]:
        names = {self.manifest_name}
        for item in self.config.get("root_files", []):
            target = item.get("target") if isinstance(item, dict) else item
            if target:
                names.add(Path(target).parts[0])
        for link_name in self.config.get("root_symlinks", {}):
            names.add(Path(link_name).parts[0])
        return names

    def clean_existing_export(self) -> None:
        manifest_paths = self.load_existing_manifest_paths()
        if manifest_paths:
            self.log(f"mirror cleanup from {self.manifest_name}")
            self.remove_manifest_paths(manifest_paths)
            return

        self.log("legacy mirror cleanup")
        for item in sorted(self.export_root.iterdir(), key=lambda path: path.name):
            relative = item.relative_to(self.export_root)
            if self.is_preserved_repo_path(relative):
                self.log(f"preserve {self.rel(item)}")
                continue
            self.remove_export_path(item)

    def load_existing_manifest_paths(self) -> list[str]:
        manifest_path = self.export_root / self.manifest_name
        if not manifest_path.is_file():
            return []
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.log(f"ignore unreadable manifest {manifest_path}")
            return [self.manifest_name]
        paths = data.get("paths", [])
        if not isinstance(paths, list):
            return [self.manifest_name]
        return [path for path in paths if isinstance(path, str)] + [self.manifest_name]

    def remove_manifest_paths(self, paths: list[str]) -> None:
        for rel in sorted(set(paths), key=lambda value: (value.count("/"), value), reverse=True):
            relative = Path(rel)
            if relative.is_absolute() or ".." in relative.parts:
                self.log(f"skip unsafe manifest path {rel}")
                continue
            if self.is_preserved_repo_path(relative):
                self.log(f"preserve {rel}")
                continue
            self.remove_export_path(self.export_root / relative)

    def remove_export_path(self, path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        self.log(f"remove {self.rel(path)}")
        if self.dry_run:
            return
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)

    def is_preserved_repo_path(self, relative: Path) -> bool:
        if not relative.parts:
            return False
        root_name = relative.parts[0]
        return root_name in self.repo_preserve_names and root_name not in self.explicit_root_names

    def ensure_dir(self, path: Path) -> None:
        self.record_export_path(path)
        if path.exists():
            return
        self.log(f"mkdir {path}")
        if not self.dry_run:
            path.mkdir(parents=True, exist_ok=True)

    def copy_root_files(self) -> None:
        for item in self.config.get("root_files", []):
            if isinstance(item, dict):
                source = item["source"]
                target = item["target"]
            else:
                source = target = item
            self.copy_file(self.root / source, self.export_root / target)
        for directory in self.config.get("root_dirs", []):
            self.ensure_dir(self.export_root / directory)
        for link_name, target in self.config.get("root_symlinks", {}).items():
            self.create_symlink(self.export_root / link_name, target)

    def copy_obsidian(self) -> None:
        for profile_name, required in [(".obsidian", True), (".obsidian-mobile", False)]:
            source = self.root / profile_name
            target = self.export_root / profile_name
            if not source.is_dir():
                if required:
                    raise SystemExit(f"Missing root {profile_name} folder: {source}")
                continue
            self.copy_obsidian_tree(source, target, profile_name)

    def copy_obsidian_tree(self, source_root: Path, target_root: Path, profile_name: str) -> None:
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(source_root)
            vault_relative = Path(profile_name) / relative
            target = target_root / relative
            if self.should_skip_obsidian(vault_relative, item):
                continue
            if item.is_symlink():
                self.create_symlink(target, os.readlink(item))
            elif item.is_dir():
                self.ensure_dir(target)
            elif item.is_file():
                self.copy_file(item, target)

    def should_skip_obsidian(self, relative: Path, item: Path) -> bool:
        if self.is_global_exclude_path(relative) or self.is_sensitive_path(relative):
            self.log(f"skip sensitive/config {posix(relative)}")
            return True
        if self.is_blocked_plugin_file(relative, item):
            self.log(f"skip plugin code/config {posix(relative)}")
            return True
        rel = posix(relative)
        for pattern in self.obsidian_exclude_globs:
            if fnmatch.fnmatch(rel, pattern):
                self.log(f"skip sensitive/config {rel}")
                return True
        return False

    def is_blocked_plugin_file(self, relative: Path, item: Path) -> bool:
        parts = relative.parts
        if len(parts) < 3 or parts[0] not in {".obsidian", ".obsidian-mobile"} or parts[1] != "plugins":
            return False
        if item.is_dir():
            return False
        plugin_name = parts[2]
        if plugin_name in self.obsidian_plugin_full_copy_plugins:
            return False
        if len(parts) != 4:
            return True
        return parts[-1] not in self.obsidian_plugin_public_files

    def copy_system_or_shared(self, name: str) -> None:
        source_root = self.root / name
        target_root = self.export_root / name
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(self.root)
            if self.should_skip_system_shared(relative, item.is_dir()):
                continue
            if (
                item.is_symlink()
                and len(relative.parts) == 4
                and relative.parts[:3] == ("_system", "agents", "skills")
                and self.should_skip_catalog_link(item)
            ):
                continue
            target = self.export_root / relative
            if item.is_symlink():
                self.create_symlink(target, os.readlink(item))
            elif item.is_dir():
                self.ensure_dir(target)
            elif item.is_file():
                self.copy_file(item, target)

    def should_skip_catalog_link(self, item: Path) -> bool:
        raw = os.readlink(item)
        if raw.startswith("../manual-skills/") or raw.startswith("../gh-skills/"):
            return True
        resolved = item.resolve(strict=False)
        return any(
            resolved == (self.root / target).resolve(strict=False)
            for target in self.dependency_projection_targets
        )

    def should_skip_system_shared(self, relative: Path, is_dir: bool) -> bool:
        rel = posix(relative)
        if any(relative == target or is_relative_to(relative, target) for target in self.dependency_projection_targets):
            return True
        if self.is_global_exclude_path(relative):
            return True
        if self.is_sensitive_path(relative):
            return True
        if rel == "_system/config/env":
            self.ensure_dir(self.export_root / relative)
            return False
        if rel.startswith("_system/config/env/"):
            return True
        if (
            len(relative.parts) == 2
            and relative.parts[0] == "_system"
            and relative.suffix.lower() == ".md"
            and rel not in self.system_root_markdown_allow_paths
        ):
            return True
        if rel in self.generated_exclude_paths:
            return True
        if len(relative.parts) >= 4 and relative.parts[:3] == ("_system", "agents", "skills"):
            wrapper_root = self.root.joinpath(*relative.parts[:4])
            if (wrapper_root / ".manual-skill-wrapper.json").exists():
                return True
        for pattern in self.generated_exclude_globs:
            if fnmatch.fnmatch(rel, pattern):
                return True
            if pattern.endswith("/**"):
                base = pattern[:-3]
                if fnmatch.fnmatch(rel, base) or rel == base or rel.startswith(base + "/"):
                    return True
        return False

    def is_global_exclude_path(self, relative: Path) -> bool:
        return any(
            part in self.global_exclude_names
            or part.endswith(GLOBAL_EXCLUDE_SUFFIXES)
            for part in relative.parts
        )

    def is_sensitive_path(self, relative: Path) -> bool:
        parts = [part.lower() for part in relative.parts]
        if any(part in self.sensitive_exclude_names for part in parts):
            return True
        return any(part.startswith(".env") for part in parts)

    def copy_context_folders(self) -> None:
        for item in self.context_configs:
            source_name = item["source"]
            target_name = item["target"]
            source = self.root / source_name
            target = self.export_root / target_name
            self.ensure_dir(target)
            folder_note_path = context_folder_note_path(source)
            if folder_note_path.exists():
                self.write_public_context_folder_note(
                    folder_note_path,
                    target / f"{target_name}.md",
                    target_name,
                    item.get("public_home_description", []),
                )
            obsidian = source / "_obsidian"
            if obsidian.is_dir():
                self.copy_context_obsidian(obsidian, target / "_obsidian")
            self.write_public_context_scaffold(target_name, target)

    def write_public_context_folder_note(
        self,
        source: Path,
        target: Path,
        target_name: str,
        description: list[str],
    ) -> None:
        text = source.read_text(encoding="utf-8")
        frontmatter, body = split_yaml_frontmatter(text)
        public_headings = {"## Identity", "## Momentum", "### Social Selling"}
        heading_lines = [
            line.rstrip()
            for line in body.splitlines()
            if line.rstrip() in public_headings
        ]
        rendered_body = f"# {target_name}\n\n{public_description_text(description)}"
        if heading_lines:
            rendered_body += "\n\n" + "\n\n".join(heading_lines)
        rendered_body += "\n"
        rendered = join_frontmatter_and_body(frontmatter, rendered_body)
        self.write_generated_text(target, rendered, f"write public context folder note {target}")

    def write_generated_text(self, target: Path, text: str, message: str) -> None:
        self.ensure_dir(target.parent)
        self.record_export_path(target)
        self.log(message)
        if self.dry_run:
            return
        target.write_text(self.rewrite_text(text), encoding="utf-8")

    def copy_tree_all(self, source_root: Path, target_root: Path) -> None:
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(source_root)
            if self.is_global_exclude_path(relative) or self.is_sensitive_path(relative):
                continue
            target = target_root / relative
            if item.is_symlink():
                self.create_symlink(target, os.readlink(item))
            elif item.is_dir():
                self.ensure_dir(target)
            elif item.is_file():
                self.copy_file(item, target)

    def copy_context_obsidian(self, source_root: Path, target_root: Path) -> None:
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(source_root)
            target = target_root / relative
            if self.is_global_exclude_path(relative) or self.is_sensitive_path(relative):
                continue
            if item.is_symlink():
                continue
            if item.is_dir():
                self.ensure_dir(target)
                continue
            rel_text = posix(relative)
            keep_file = (
                rel_text.startswith("bases/") and item.suffix == ".base"
            ) or (
                rel_text.startswith("templates/") and item.suffix == ".md"
            )
            if keep_file and item.is_file():
                self.copy_file(item, target)

    def write_public_context_scaffold(self, target_name: str, target_root: Path) -> None:
        dirs = self.public_context_scaffold_dirs.get(target_name, [])
        if not isinstance(dirs, list):
            return
        for rel_dir in dirs:
            if not isinstance(rel_dir, str) or not rel_dir.strip():
                continue
            relative = Path(rel_dir)
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"Unsafe public scaffold path for {target_name}: {rel_dir}")
            marker = target_root / relative / ".gitkeep"
            self.write_generated_text(marker, "", f"write public scaffold {marker}")

    def load_bootstrap_module(self):
        path = self.root / "_system/bootstrap/bootstrap_vault.py"
        if not path.exists():
            raise SystemExit(f"Missing bootstrap script: {path}")
        spec = importlib.util.spec_from_file_location("bootstrap_vault_public_export", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def context_metadata(self, item: dict[str, Any]) -> dict[str, str]:
        target = item["target"]
        target_note = self.export_root / target / f"{target}.md"
        source_note = context_folder_note_path(self.root / item["source"])
        for path in [target_note, source_note]:
            if path.exists():
                return parse_frontmatter(path.read_text(encoding="utf-8"))
        return {}

    def target_context_names(self) -> list[str]:
        return [item["target"] for item in self.context_configs]

    def public_default_context(self) -> str:
        for item in self.context_configs:
            metadata = self.context_metadata(item)
            if bool_frontmatter(metadata.get("default_capture")):
                return item["target"]
        targets = self.target_context_names()
        if "personal" in targets:
            return "personal"
        if not targets:
            raise SystemExit("Public export has no configured context folders.")
        return targets[0]

    def public_active_contexts(self) -> list[str]:
        active: list[str] = []
        for item in self.context_configs:
            metadata = self.context_metadata(item)
            if (metadata.get("status") or "active").strip().lower() == "active":
                active.append(item["target"])
        return active

    def public_content_contexts(self) -> list[str]:
        content: list[str] = []
        for item in self.context_configs:
            target = item["target"]
            source = item["source"]
            metadata = self.context_metadata(item)
            if (
                bool_frontmatter(metadata.get("content_enabled"))
                or (self.export_root / target / "_obsidian/content").exists()
                or (self.root / source / "_obsidian/content").exists()
            ):
                content.append(target)
        return content

    def public_context_types(self, bootstrap_module) -> dict[str, str]:
        context_types: dict[str, str] = {}
        defaults = getattr(bootstrap_module, "DEFAULT_CONTEXT_TYPES", {})
        for item in self.context_configs:
            target = item["target"]
            metadata = self.context_metadata(item)
            context_types[target] = metadata.get("context_type") or defaults.get(target, "business")
        return context_types

    def regenerate_public_bases(self) -> None:
        if not self.context_configs:
            return
        bootstrap_module = self.load_bootstrap_module()
        targets = self.target_context_names()
        bootstrap = bootstrap_module.Bootstrap(
            root=self.export_root,
            entities=targets,
            active_entities=self.public_active_contexts(),
            default_entity=self.public_default_context(),
            context_types=self.public_context_types(bootstrap_module),
            coding_agents=[],
            content_entities=self.public_content_contexts(),
            install_vault_command_enabled=False,
            agent_symlinks_enabled=False,
            dry_run=self.dry_run,
            run_date=datetime.now(timezone.utc).date(),
        )
        bootstrap.setup_bases(drop_task_epic_views=True)

    def discovered_source_context_names(self) -> set[str]:
        names = {item["source"] for item in self.context_configs}
        for child in self.root.iterdir():
            if child.is_dir() and context_folder_note_path(child).exists():
                names.add(child.name)
        return names

    def validate_public_base_contexts(self) -> None:
        if self.dry_run:
            return
        allowed = set(self.target_context_names())
        blocked = sorted(self.discovered_source_context_names() - allowed)
        if not blocked:
            return
        leaks: list[str] = []
        for path in sorted(self.export_root.rglob("*.base")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for name in blocked:
                needles = [
                    f'{name}/_obsidian/',
                    f'entity == "{name}"',
                    f"entity == '{name}'",
                ]
                if any(needle in text for needle in needles):
                    leaks.append(f"{path.relative_to(self.export_root)} contains {name}")
        if leaks:
            rendered = "\n".join(f"- {leak}" for leak in leaks[:20])
            raise SystemExit(f"Refusing to export .base files with source context-folder references:\n{rendered}")

    def create_library_and_wiki(self) -> None:
        self.ensure_dir(self.export_root / "_library")
        wiki = self.export_root / "_wiki"
        self.ensure_dir(wiki)
        source = self.root / "_wiki/AGENTS.md"
        if source.exists():
            self.copy_file(source, wiki / "AGENTS.md")

    def copy_file(self, source: Path, target: Path) -> None:
        if not source.exists():
            raise SystemExit(f"Missing file: {source}")
        self.scan_exact_plugin_file(source)
        self.ensure_dir(target.parent)
        self.record_export_path(target)
        self.log(f"copy {self.rel(source)} -> {target}")
        if self.dry_run:
            return
        if self.should_sanitize_workspace(source):
            self.write_public_workspace(source, target)
            return
        if self.should_rewrite_text(source):
            try:
                text = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(source, target)
                return
            target.write_text(self.rewrite_text(text, source=source), encoding="utf-8")
            shutil.copystat(source, target)
            return
        shutil.copy2(source, target)

    def should_rewrite_text(self, source: Path) -> bool:
        return source.suffix in self.text_rewrite_suffixes

    def should_sanitize_workspace(self, source: Path) -> bool:
        try:
            return posix(source.relative_to(self.root)) == ".obsidian/workspace.json"
        except ValueError:
            return False

    def write_public_workspace(self, source: Path, target: Path) -> None:
        data = json.loads(source.read_text(encoding="utf-8"))
        self.sanitize_main_workspace(data)
        self.sanitize_workspace_node(data)
        rendered = json.dumps(data, indent=2) + "\n"
        for source_name, target_name in self.rewrite_pairs:
            rendered = rendered.replace(source_name, target_name)
        if "_private" in rendered:
            raise SystemExit("Refusing to export workspace.json with private file history.")
        target.write_text(rendered, encoding="utf-8")
        shutil.copystat(source, target)

    def sanitize_main_workspace(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        main = data.get("main")
        if not isinstance(main, dict):
            return
        main["type"] = "tabs"
        main["children"] = [self.public_readme_leaf(self.first_leaf_id(main))]
        main["currentTab"] = 0
        main.pop("direction", None)

    def public_readme_leaf(self, leaf_id: str | None = None) -> dict[str, Any]:
        return {
            "id": leaf_id or "public-readme",
            "type": "leaf",
            "state": {
                "type": "markdown",
                "state": {
                    "file": PUBLIC_WORKSPACE_FILE,
                    "mode": "source",
                    "source": False,
                },
                "icon": "lucide-file",
                "title": "README",
            },
        }

    def first_leaf_id(self, value: Any) -> str | None:
        if isinstance(value, dict):
            if value.get("type") == "leaf" and isinstance(value.get("id"), str):
                return value["id"]
            for child in value.values():
                found = self.first_leaf_id(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = self.first_leaf_id(child)
                if found:
                    return found
        return None

    def sanitize_workspace_node(self, value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("lastOpenFiles"), list):
                value["lastOpenFiles"] = [PUBLIC_WORKSPACE_FILE]

            state = value.get("state")
            if value.get("type") == "leaf" and isinstance(state, dict):
                inner_state = state.get("state")
                if isinstance(inner_state, dict) and isinstance(inner_state.get("file"), str):
                    inner_state["file"] = PUBLIC_WORKSPACE_FILE
                    state["icon"] = "lucide-file"
                    state["title"] = "README"

            for child in value.values():
                self.sanitize_workspace_node(child)
        elif isinstance(value, list):
            for child in value:
                self.sanitize_workspace_node(child)

    def scan_exact_plugin_file(self, source: Path) -> None:
        try:
            relative = source.relative_to(self.root)
        except ValueError:
            return
        parts = relative.parts
        if len(parts) < 4 or parts[0] not in {".obsidian", ".obsidian-mobile"} or parts[1] != "plugins":
            return
        if parts[2] not in self.obsidian_plugin_full_copy_plugins:
            return
        if source.suffix.lower() not in {".js", ".json", ".css"}:
            return
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise SystemExit(f"Refusing to export possible {label} in exact-copy plugin file: {posix(relative)}")

    def rewrite_text(self, text: str, *, source: Path | None = None) -> str:
        for source_name, target_name in self.rewrite_pairs:
            text = text.replace(source_name, target_name)
        if source is not None and source.suffix == ".md":
            text = self.strip_private_export_drop_lines(text)
        return text

    def strip_private_export_drop_lines(self, text: str) -> str:
        if PRIVATE_EXPORT_DROP_LINE_MARKER not in text and not any(
            link in text for link in PRIVATE_EXPORT_DROP_LINKS
        ):
            return text
        lines = text.splitlines()
        kept = [
            line
            for line in lines
            if PRIVATE_EXPORT_DROP_LINE_MARKER not in line
            and not any(link in line for link in PRIVATE_EXPORT_DROP_LINKS)
        ]
        rendered = "\n".join(kept)
        if text.endswith("\n"):
            rendered += "\n"
        return rendered

    def create_symlink(self, link: Path, target: str) -> None:
        self.ensure_dir(link.parent)
        self.record_export_path(link)
        self.log(f"symlink {link} -> {target}")
        if not self.dry_run:
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(target)

    def record_export_path(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.export_root)
        except ValueError:
            return
        if not relative.parts:
            return
        self.exported_paths.add(posix(relative))

    def write_manifest(self) -> None:
        path = self.export_root / self.manifest_name
        self.record_export_path(path)
        payload = {
            "version": MANIFEST_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "paths": sorted(self.exported_paths),
        }
        rendered = json.dumps(payload, indent=2) + "\n"
        self.log(f"write {path}")
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a public bootstrap vault from the current vault.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Config path relative to root. Defaults to {DEFAULT_CONFIG}.")
    parser.add_argument("--export-root", default=None, help="Override export root from config.")
    parser.add_argument("--force", action="store_true", help="Replace a non-empty export directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned copy operations without writing files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_vault_root(args.root, __file__)
    config_path = root / args.config
    config = load_json(config_path)
    export_root = Path(args.export_root).expanduser() if args.export_root else None
    exporter = BootstrapExporter(
        root=root,
        config=config,
        export_root=export_root,
        force=args.force,
        dry_run=args.dry_run,
    )
    exporter.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
