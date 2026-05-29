#!/usr/bin/env python3
"""Export a public bootstrap vault from the current vault state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import json
import os
import shutil
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


DEFAULT_CONFIG = "master/system/bootstrap/bootstrap-export.json"
DEFAULT_MANIFEST_NAME = "master/system/bootstrap/state/export-manifest.json"
MANIFEST_VERSION = 1


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
        self.context_pairs = [
            (item["source"], item["target"])
            for item in config.get("context_folders", [])
        ]
        self.rewrite_pairs = sorted(self.context_pairs, key=lambda pair: len(pair[0]), reverse=True)
        self.generated_exclude_paths = set(config.get("generated_exclude_paths", []))
        self.generated_exclude_globs = list(config.get("generated_exclude_globs", []))
        self.global_exclude_names = set(config.get("global_exclude_names", []))
        self.sensitive_exclude_names = {name.lower() for name in config.get("sensitive_exclude_names", [])}
        self.text_rewrite_suffixes = set(config.get("text_rewrite_suffixes", []))
        self.repo_preserve_names = set(config.get("repo_preserve_names", []))
        self.obsidian_exclude_globs = list(config.get("obsidian_exclude_globs", []))
        self.obsidian_plugin_full_copy_plugins = set(config.get("obsidian_plugin_full_copy_plugins", []))
        self.obsidian_plugin_public_files = set(
            config.get("obsidian_plugin_public_files", ["manifest.json", "styles.css"])
        )
        self.manifest_name = config.get("manifest_name", DEFAULT_MANIFEST_NAME)
        self.exported_paths: set[str] = set()
        self.explicit_root_names = self.collect_explicit_root_names()

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
        self.copy_master_or_shared("master")
        self.copy_context_folders()
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
            if not self.force:
                raise SystemExit(f"Export directory is not empty; pass --force to replace it: {self.export_root}")
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
        for link_name, target in self.config.get("root_symlinks", {}).items():
            self.create_symlink(self.export_root / link_name, target)

    def copy_obsidian(self) -> None:
        source = self.root / ".obsidian"
        target = self.export_root / ".obsidian"
        if not source.is_dir():
            raise SystemExit(f"Missing root .obsidian folder: {source}")
        self.copy_obsidian_tree(source, target)

    def copy_obsidian_tree(self, source_root: Path, target_root: Path) -> None:
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(source_root)
            vault_relative = Path(".obsidian") / relative
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
        if item.name in self.global_exclude_names or self.is_sensitive_path(relative):
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
        if len(parts) < 3 or parts[0] != ".obsidian" or parts[1] != "plugins":
            return False
        if item.is_dir():
            return False
        plugin_name = parts[2]
        if plugin_name in self.obsidian_plugin_full_copy_plugins:
            return False
        if len(parts) != 4:
            return True
        return parts[-1] not in self.obsidian_plugin_public_files

    def copy_master_or_shared(self, name: str) -> None:
        source_root = self.root / name
        target_root = self.export_root / name
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(self.root)
            if self.should_skip_master_shared(relative, item.is_dir()):
                continue
            target = self.export_root / relative
            if item.is_symlink():
                self.create_symlink(target, os.readlink(item))
            elif item.is_dir():
                self.ensure_dir(target)
            elif item.is_file():
                self.copy_file(item, target)

    def should_skip_master_shared(self, relative: Path, is_dir: bool) -> bool:
        rel = posix(relative)
        name = relative.name
        if name in self.global_exclude_names or any(part in self.global_exclude_names for part in relative.parts):
            return True
        if self.is_sensitive_path(relative):
            return True
        if rel == "master/env":
            self.ensure_dir(self.export_root / relative)
            return False
        if rel.startswith("master/env/"):
            return True
        if rel in self.generated_exclude_paths:
            return True
        for pattern in self.generated_exclude_globs:
            if fnmatch.fnmatch(rel, pattern):
                return True
            if pattern.endswith("/**"):
                base = pattern[:-3]
                if rel == base or rel.startswith(base + "/"):
                    return True
        return False

    def is_sensitive_path(self, relative: Path) -> bool:
        parts = [part.lower() for part in relative.parts]
        if any(part in self.sensitive_exclude_names for part in parts):
            return True
        return any(part.startswith(".env") for part in parts)

    def copy_context_folders(self) -> None:
        for source_name, target_name in self.context_pairs:
            source = self.root / source_name
            target = self.export_root / target_name
            self.ensure_dir(target)
            for root_file in ["HOME.md", "DECLARATION.md"]:
                path = source / root_file
                if path.exists():
                    self.copy_file(path, target / root_file)
            declaration_dir = source / "DECLARATION"
            if declaration_dir.is_dir():
                self.copy_tree_all(declaration_dir, target / "DECLARATION")
            obsidian = source / "_obsidian"
            if obsidian.is_dir():
                self.copy_context_obsidian(obsidian, target / "_obsidian")

    def copy_tree_all(self, source_root: Path, target_root: Path) -> None:
        self.ensure_dir(target_root)
        for item in sorted(source_root.rglob("*")):
            relative = item.relative_to(source_root)
            if item.name in self.global_exclude_names or self.is_sensitive_path(relative):
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
            if item.name in self.global_exclude_names or self.is_sensitive_path(relative):
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

    def create_library_and_wiki(self) -> None:
        self.ensure_dir(self.export_root / "library")
        wiki = self.export_root / "wiki"
        self.ensure_dir(wiki)
        source = self.root / "wiki/AGENTS.md"
        if source.exists():
            self.copy_file(source, wiki / "AGENTS.md")

    def copy_file(self, source: Path, target: Path) -> None:
        if not source.exists():
            raise SystemExit(f"Missing file: {source}")
        self.ensure_dir(target.parent)
        self.record_export_path(target)
        self.log(f"copy {self.rel(source)} -> {target}")
        if self.dry_run:
            return
        if self.should_rewrite_text(source):
            try:
                text = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(source, target)
                return
            target.write_text(self.rewrite_text(text), encoding="utf-8")
            shutil.copystat(source, target)
            return
        shutil.copy2(source, target)

    def should_rewrite_text(self, source: Path) -> bool:
        return source.suffix in self.text_rewrite_suffixes

    def rewrite_text(self, text: str) -> str:
        for source, target in self.rewrite_pairs:
            text = text.replace(source, target)
        return text

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
