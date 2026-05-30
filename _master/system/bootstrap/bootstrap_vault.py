#!/usr/bin/env python3
"""
Bootstrap this Obsidian workspace into the lowercase context folder layout.

The script is intentionally conservative:
- it never moves content from legacy dash-prefixed folders;
- it only overwrites files that contain the managed-file marker;
- it leaves the live root Obsidian profile as the source of truth.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
from pathlib import Path


DEFAULT_ENTITIES = [
    "personal",
    "personal-brand",
    "business",
]

DEFAULT_ACTIVE_ENTITIES = [
    "personal",
    "personal-brand",
    "business",
]

DEFAULT_CONTENT_ENTITIES = [
    "personal-brand",
    "business",
]

DEFAULT_CONTEXT_TYPES = {
    "personal": "personal",
    "personal-brand": "personal-brand",
    "business": "business",
}

VALID_CONTEXT_TYPES = {"personal", "personal-brand", "business"}

PERIODS = {
    "daily": "daily",
    "weekly": "weekly",
    "quarterly": "quarterly",
    "yearly": "yearly",
}
VALID_CODING_AGENTS = {"codex", "claude"}

GENERATED_MARKER = "managed-by: _master/system/bootstrap/bootstrap_vault.py"
MASTER_PERIODIC_MARKER = "managed-by: _master/system/scripts/periodic.py"
OLD_GENERATED_MARKERS = (
    "managed-by: _master/system/bootstrap/setup/bootstrap_vault.py",
    "managed-by: _master/bootstrap/setup/bootstrap_vault.py",
)
OLD_MASTER_PERIODIC_MARKERS = (
    "managed-by: _master/system/scripts/generate_master_periodic_notes_for_now.py",
    "managed-by: _master/scripts/generate_master_periodic_notes_for_now.py",
)
BOOTSTRAP_MARKERS = (GENERATED_MARKER, *OLD_GENERATED_MARKERS)
MASTER_PERIODIC_MARKERS = (MASTER_PERIODIC_MARKER, *OLD_MASTER_PERIODIC_MARKERS)
MANAGED_MARKERS = (*BOOTSTRAP_MARKERS, *MASTER_PERIODIC_MARKERS)
OBSOLETE_CONTEXT_FOLDER_WORKSPACE_LINKS = [
    ".agents",
    ".claude",
    "AGENTS.md",
    "CLAUDE.md",
    "_templates_shared",
]


class Bootstrap:
    def __init__(
        self,
        root: Path,
        entities: list[str],
        active_entities: list[str],
        default_entity: str,
        context_types: dict[str, str],
        coding_agents: list[str],
        content_entities: list[str],
        install_vault_command_enabled: bool,
        generate_agents_enabled: bool,
        dry_run: bool,
        run_date: dt.date,
    ) -> None:
        self.root = root
        self.entities = entities
        self.active_entities = active_entities
        self.default_entity = default_entity
        self.context_types = context_types
        self.coding_agents = coding_agents
        self.content_entities = content_entities
        self.install_vault_command_enabled = install_vault_command_enabled
        self.generate_agents_enabled = generate_agents_enabled
        self.dry_run = dry_run
        self.run_date = run_date

    def log(self, message: str) -> None:
        prefix = "[dry-run] " if self.dry_run else ""
        print(f"{prefix}{message}")

    def ensure_dir(self, path: Path) -> None:
        if path.exists():
            return
        self.log(f"mkdir {rel(path, self.root)}")
        if not self.dry_run:
            path.mkdir(parents=True, exist_ok=True)

    def safe_remove_generated_path(self, path: Path, markers: tuple[str, ...]) -> None:
        if not path.exists() and not path.is_symlink():
            return
        if path.is_symlink():
            self.remove_path(path)
            return
        if path.is_file():
            if path.name == ".DS_Store":
                self.remove_path(path)
                return
            text = path.read_text(encoding="utf-8")
            if not any(marker in text for marker in markers):
                self.log(f"skip non-managed file {rel(path, self.root)}")
                return
            self.remove_path(path)
            return
        unmanaged = []
        for item in path.rglob("*"):
            if item.is_dir() or item.is_symlink() or item.name == ".DS_Store":
                continue
            try:
                text = item.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                unmanaged.append(item)
                continue
            if not any(marker in text for marker in markers):
                unmanaged.append(item)
        if unmanaged:
            paths = ", ".join(rel(item, self.root) for item in unmanaged[:5])
            self.log(f"skip non-managed tree {rel(path, self.root)}; unmanaged files include: {paths}")
            return
        self.remove_path(path)

    def remove_path(self, path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        self.log(f"remove {rel(path, self.root)}")
        if self.dry_run:
            return
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)

    def ensure_symlink(self, link: Path, target: str) -> None:
        if link.is_symlink():
            current = link.readlink()
            if str(current) == target:
                return
            self.log(f"replace symlink {rel(link, self.root)} -> {target}")
            if not self.dry_run:
                link.unlink()
                link.symlink_to(target, target_is_directory=True)
            return
        if link.exists():
            if self.dry_run:
                self.log(f"symlink {rel(link, self.root)} -> {target}")
                return
            raise RuntimeError(
                f"Refusing to replace existing non-symlink path {rel(link, self.root)}"
            )
        self.log(f"symlink {rel(link, self.root)} -> {target}")
        if not self.dry_run:
            link.symlink_to(target, target_is_directory=True)

    def ensure_managed_symlink(self, link: Path, target: str) -> None:
        if link.is_symlink():
            current = link.readlink()
            if str(current) == target:
                return
            self.log(f"replace symlink {rel(link, self.root)} -> {target}")
            if not self.dry_run:
                link.unlink()
                link.symlink_to(target)
            return
        if link.exists():
            if link.is_file():
                text = link.read_text(encoding="utf-8", errors="replace")
                if any(marker in text for marker in BOOTSTRAP_MARKERS):
                    self.remove_path(link)
                else:
                    raise RuntimeError(f"Refusing to replace non-managed file {rel(link, self.root)}")
            else:
                raise RuntimeError(f"Refusing to replace non-symlink path {rel(link, self.root)}")
        self.log(f"symlink {rel(link, self.root)} -> {target}")
        if not self.dry_run:
            link.symlink_to(target)

    def write_managed(
        self,
        path: Path,
        content: str,
        marker: str = GENERATED_MARKER,
        allow_unmarked_existing: bool = False,
    ) -> None:
        if marker not in content:
            raise ValueError(f"managed content for {path} is missing marker {marker!r}")
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if (
                not allow_unmarked_existing
                and marker not in existing
                and not any(old_marker in existing for old_marker in BOOTSTRAP_MARKERS)
            ):
                self.log(f"skip existing non-managed file {rel(path, self.root)}")
                return
            if existing == content:
                return
        self.ensure_dir(path.parent)
        self.log(f"write {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(content, encoding="utf-8")

    def write_managed_if_missing(self, path: Path, content: str, marker: str = GENERATED_MARKER) -> None:
        if marker not in content:
            raise ValueError(f"managed content for {path} is missing marker {marker!r}")
        if path.exists():
            return
        self.ensure_dir(path.parent)
        self.log(f"write {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(content, encoding="utf-8")

    def copy_file_if_missing(self, source: Path, target: Path) -> None:
        if not source.exists() or target.exists():
            return
        self.ensure_dir(target.parent)
        self.log(f"copy {rel(source, self.root)} -> {rel(target, self.root)}")
        if not self.dry_run:
            shutil.copy2(source, target)

    def ensure_task_kanban_project_swimlanes(self, path: Path) -> None:
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        updated = add_project_swimlanes_to_task_kanban_views(text)
        if updated == text:
            return
        self.log(f"patch project swimlanes in {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(updated, encoding="utf-8")

    def write_if_missing(self, path: Path, content: str) -> None:
        if path.exists():
            return
        self.ensure_dir(path.parent)
        self.log(f"write {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(content, encoding="utf-8")

    def write_context_folder_note(self, entity: str, status: str, context_type: str, content_enabled: bool, default_capture: bool) -> None:
        path = context_folder_note_path(self.root, entity)
        content = context_folder_note(status, context_type, content_enabled, default_capture)
        if not path.exists():
            self.ensure_dir(path.parent)
            self.log(f"write {rel(path, self.root)}")
            if not self.dry_run:
                path.write_text(content, encoding="utf-8")
            return
        existing = path.read_text(encoding="utf-8")
        if not any(marker in existing for marker in BOOTSTRAP_MARKERS) and not has_frontmatter(existing):
            self.log(f"skip existing non-managed file {rel(path, self.root)}")
            return
        content = update_context_folder_note(existing, status, context_type, content_enabled, default_capture)
        if existing == content:
            return
        self.log(f"write {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(content, encoding="utf-8")

    def copy_tree_contents_preserving(self, source: Path, target: Path) -> None:
        if not source.exists() or source.is_symlink():
            return
        for item in sorted(source.rglob("*")):
            relative = item.relative_to(source)
            destination = target / relative
            if item.is_dir():
                self.ensure_dir(destination)
                continue
            if destination.exists():
                continue
            self.ensure_dir(destination.parent)
            self.log(f"copy {rel(item, self.root)} -> {rel(destination, self.root)}")
            if not self.dry_run:
                shutil.copy2(item, destination)

    def remove_empty_dir(self, path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        if any(path.iterdir()):
            self.log(f"leave non-empty {rel(path, self.root)}")
            return
        self.remove_path(path)

    def remove_symlink_or_skip(self, path: Path) -> None:
        if path.is_symlink():
            self.remove_path(path)
        elif path.exists():
            self.log(f"skip non-symlink obsolete path {rel(path, self.root)}")

    def setup_directories(self) -> None:
        master_dirs = [
            "_master/_obsidian/bases",
            "_master/_obsidian/bases",
            "_master/system/context",
            "_master/_obsidian/notes/operating-methods",
            "_master/_obsidian/templates/shared/content",
            "_master/_obsidian/templates/shared/entity-notes",
            "_master/_obsidian/excalidraw",
            "_master/_obsidian/excalidraw/Scripts",
            "_master/system/scripts",
            "_master/_obsidian/attachments",
        ]
        for directory in master_dirs:
            self.ensure_dir(self.root / directory)

        for entity in self.entities:
            self.remove_empty_dir(self.root / entity / "notes")
            if (self.root / entity / "_templates").is_symlink():
                self.remove_path(self.root / entity / "_templates")
            for directory in [
                "_obsidian/attachments",
                "_obsidian/bases",
                "_obsidian/excalidraw",
                "_obsidian/excalidraw/Scripts",
                "_obsidian/epics",
                "_obsidian/periodic/daily",
                "_obsidian/periodic/weekly",
                "_obsidian/periodic/quarterly",
                "_obsidian/periodic/yearly",
                "_obsidian/projects",
                "_obsidian/tasks",
                "_obsidian/tasks/archive",
                "_obsidian/templates",
                "_obsidian/templates/periodic",
            ]:
                self.ensure_dir(self.root / entity / directory)
            if entity in self.content_entities:
                for directory in content_directories():
                    self.ensure_dir(self.root / entity / directory)

    def cleanup_retired_monthly_periodics(self) -> None:
        for entity in self.entities:
            self.safe_remove_generated_path(self.root / entity / "_obsidian/periodic/monthly", MANAGED_MARKERS)
        self.safe_remove_generated_path(self.root / "_master/_obsidian/periodic/monthly", MANAGED_MARKERS)
        for entity in self.entities:
            self.safe_remove_generated_path(
                self.root / entity / "_obsidian/templates/periodic/monthly-template.md",
                MANAGED_MARKERS,
            )

    def setup_context_folder_notes(self) -> None:
        active = set(self.active_entities)
        content = set(self.content_entities)
        for entity in self.entities:
            status = "active" if entity in active else "archived"
            context_type = self.context_types.get(entity, "business")
            self.write_context_folder_note(entity, status, context_type, entity in content, entity == self.default_entity)

    def setup_agent_infrastructure(self) -> None:
        if self.coding_agents:
            self.ensure_dir(self.root / "_master/agents/skills")
            self.ensure_dir(self.root / "_master/agents/skills-dump")
            self.ensure_dir(self.root / ".agents")
            self.ensure_dir(self.root / ".claude")

    def cleanup_obsolete_context_folder_workspace_artifacts(self) -> None:
        for entity in self.entities:
            entity_root = self.root / entity
            self.remove_path(entity_root / ".obsidian")
            for name in OBSOLETE_CONTEXT_FOLDER_WORKSPACE_LINKS:
                self.remove_symlink_or_skip(entity_root / name)

    def setup_context_template_dirs(self) -> None:
        for entity in self.entities:
            self.ensure_dir(self.root / entity / "_obsidian/templates")
            self.ensure_dir(self.root / entity / "_obsidian/templates/periodic")

    def setup_excalidraw(self) -> None:
        master_excalidraw = self.root / "_master/_obsidian/excalidraw"
        master_template = master_excalidraw / "template.excalidraw"
        self.write_if_missing(master_template, excalidraw_template())

        scripts_source = master_excalidraw / "Scripts"
        for entity in self.entities:
            entity_scripts = self.root / entity / "_obsidian/excalidraw/Scripts"
            self.copy_tree_contents_preserving(scripts_source, entity_scripts)
            self.copy_file_if_missing(
                master_template,
                self.root / entity / "_obsidian/excalidraw/template.excalidraw",
            )

    def setup_templates(self) -> None:
        self.safe_remove_generated_path(self.root / "README_PERSONALIZED_QUICKSTART.md", BOOTSTRAP_MARKERS)
        self.write_managed(
            self.root / "_master/README_PERSONALIZED_QUICKSTART.md",
            personalized_quickstart(self.entities, self.default_entity, self.active_entities, self.content_entities),
        )
        self.write_managed(self.root / "_master/_obsidian/templates/shared/default-tasks-template.md", shared_task_template())
        self.write_managed(self.root / "_master/_obsidian/templates/shared/content/content-item-template.md", content_item_template())
        self.write_managed(self.root / "_master/_obsidian/templates/shared/content/publication-template.md", publication_template())
        self.write_managed(self.root / "_master/_obsidian/templates/shared/entity-notes/personal.md", entity_note_template("personal", "personal"))
        self.write_managed(self.root / "_master/_obsidian/templates/shared/entity-notes/personal-brand.md", entity_note_template("personal-brand", "personal-brand"))
        self.write_managed(self.root / "_master/_obsidian/templates/shared/entity-notes/company.md", entity_note_template("business", "business"))
        legacy_template_dir = self.root / "_master/_obsidian/templates/shared" / ("declara" + "tions")
        for old_template in legacy_template_dir.glob("*.md"):
            self.safe_remove_generated_path(old_template, BOOTSTRAP_MARKERS)
        self.remove_empty_dir(legacy_template_dir)

        personal_periodic = self.root / self.default_entity / "_obsidian/templates/periodic"
        if personal_periodic.is_symlink():
            self.remove_path(personal_periodic)
        self.ensure_dir(personal_periodic)

        for entity in self.entities:
            for period in PERIODS:
                self.write_if_missing(
                    self.root / entity / "_obsidian/templates/periodic" / f"{period}-template.md",
                    "",
                )


    def setup_bases(self) -> None:
        master_bases = {
            "epics-all.base": all_epics_base(self.active_entities),
            "tasks-today.base": today_base(),
            "tasks-this-week.base": this_week_base(),
            "content-calendar.base": content_calendar_base(self.content_entities),
            "content-kanban.base": content_kanban_base(self.content_entities),
        }
        for name, content in master_bases.items():
            self.write_managed(
                self.root / "_master/_obsidian/bases" / name,
                content,
                allow_unmarked_existing=True,
            )

        self.remove_path(self.root / "_master/_obsidian/bases/Master Dashboard.base")
        self.remove_path(self.root / "_master/_obsidian/bases/All Tasks.base")
        for old_name in [
            "All Epics.base",
            "Today.base",
            "This Week.base",
            "Content Kanban.base",
            "agenda-tasks.base",
            "calendar-tasks.base",
            "kanban-tasks.base",
            "kanban-tasks-v1.base",
            "mini-calendar-tasks.base",
            "relationships.base",
            "tasks-home-view.base",
        ]:
            self.remove_path(self.root / "_master/_obsidian/bases" / old_name)
        self.remove_empty_dir(self.root / "_master/tasknotes")
        master_task_views = self.root / "_master/_obsidian/bases"
        task_view_names = {
            "tasks-agenda.base",
            "tasks-calendar.base",
            "tasks-kanban.base",
            "tasks-mini-calendar.base",
            "tasks-relationships.base",
            "tasks-home.base",
        }
        for name in task_view_names:
            self.ensure_task_kanban_project_swimlanes(master_task_views / name)

        for entity in self.entities:
            self.write_managed(self.root / entity / "_obsidian/bases/context-dashboard.base", entity_dashboard_base(entity))
            self.write_managed(self.root / entity / "_obsidian/bases/projects-dashboard.base", entity_projects_base(entity))
            self.write_managed(self.root / entity / "_obsidian/bases/epics-dashboard.base", entity_epics_base(entity))
            for old_name in [
                "dashboard.base",
                "projects.base",
                "epics.base",
                "content.base",
                "agenda-tasks.base",
                "calendar-tasks.base",
                "kanban-tasks.base",
                "mini-calendar-tasks.base",
                "relationships.base",
                "tasks-home-view.base",
            ]:
                self.remove_path(self.root / entity / "_obsidian/bases" / old_name)
            if entity in self.content_entities:
                self.write_managed(self.root / entity / "_obsidian/bases/content-dashboard.base", entity_content_base(entity))
                self.write_managed(self.root / entity / "_obsidian/bases/content-queue.base", entity_content_queue_base(entity))
                self.write_managed(self.root / entity / "_obsidian/bases/content-calendar.base", entity_content_calendar_base(entity))
                self.write_managed(self.root / entity / "_obsidian/bases/content-kanban.base", entity_content_kanban_base(entity))
            entity_views = self.root / entity / "_obsidian/bases"
            for source in sorted(master_task_views.glob("*.base")):
                if source.name not in task_view_names:
                    continue
                target = entity_views / source.name
                self.copy_file_if_missing(source, target)
                self.ensure_task_kanban_project_swimlanes(target)

    def setup_starter_notes(self) -> None:
        for entity in self.entities:
            self.write_managed_if_missing(
                self.root / entity / "_obsidian/tasks/starter-task.md",
                starter_task(entity, self.run_date.isoformat()),
            )
            self.ensure_entity_note(entity)
            if entity in self.content_entities:
                self.write_if_missing(
                    self.root / entity / "_obsidian/content/content-cadence.json",
                    content_cadence_config(self.run_date),
                )

    def ensure_entity_note(self, entity: str) -> None:
        path = self.root / entity / f"{entity}.md"
        context_type = self.context_types.get(entity, "business")
        content_enabled = entity in self.content_entities
        default_capture = entity == self.default_entity
        if not path.exists():
            self.write_managed_if_missing(
                path,
                entity_note_template(
                    entity,
                    context_type,
                    status="active" if entity in self.active_entities else "archived",
                    content_enabled=content_enabled,
                    default_capture=default_capture,
                ),
            )
            return
        text = path.read_text(encoding="utf-8")
        updated = ensure_entity_note_sections(text, context_type)
        if updated != text:
            self.log(f"update entity note sections {rel(path, self.root)}")
            if not self.dry_run:
                path.write_text(updated, encoding="utf-8")

    def install_vault_command(self) -> None:
        import importlib.util

        if not self.install_vault_command_enabled:
            self.log("skip vault command install")
            return
        installer_path = self.root / "_master/system/bootstrap/install_vault_command.py"
        if not installer_path.exists():
            raise FileNotFoundError(installer_path)
        spec = importlib.util.spec_from_file_location("install_vault_command", installer_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        result = module.install_command(
            self.root,
            Path.home() / ".local/bin",
            "vault",
            self.dry_run,
            False,
            True,
        )
        if result != 0:
            raise RuntimeError("Failed to install vault command")

    def generate_agents_file(self) -> None:
        import importlib.util
        import sys

        if not self.generate_agents_enabled or not self.coding_agents:
            self.log("skip AGENTS.md generation")
            return
        generator_path = self.root / "_master/system/bootstrap/generate_agents.py"
        if not generator_path.exists():
            raise FileNotFoundError(generator_path)
        spec = importlib.util.spec_from_file_location("generate_agents", generator_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        args = ["--root", str(self.root)]
        if self.dry_run:
            args.append("--dry-run")
        module.main(args)

    def run_generators(self) -> None:
        import importlib.util
        import sys

        scripts_dir = self.root / "_master/system/scripts"
        periodic_path = scripts_dir / "periodic.py"
        agent_path = scripts_dir / "context.py"
        if self.dry_run:
            self.log("skip generators in dry-run")
            return
        scripts_dir_text = str(scripts_dir)
        if scripts_dir_text not in sys.path:
            sys.path.insert(0, scripts_dir_text)
        for path, module_name in [
            (periodic_path, "periodic"),
            (agent_path, "context"),
        ]:
            if not path.exists():
                raise FileNotFoundError(path)
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            module.main(
                [
                    "--root",
                    str(self.root),
                    "--configured-context-folders",
                    ",".join(self.entities),
                    "--date",
                    self.run_date.isoformat(),
                ]
            )

    def run(self) -> None:
        self.setup_directories()
        self.cleanup_retired_monthly_periodics()
        self.setup_context_folder_notes()
        self.setup_agent_infrastructure()
        self.cleanup_obsolete_context_folder_workspace_artifacts()
        self.setup_context_template_dirs()
        self.setup_excalidraw()
        self.setup_templates()
        self.setup_bases()
        self.setup_starter_notes()
        self.generate_agents_file()
        self.install_vault_command()
        self.run_generators()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def context_folder_note_path(root: Path, entity: str) -> Path:
    return root / entity / f"{entity}.md"


def add_or_update_task_kanban_option(
    lines: list[str],
    view_start: int,
    key: str,
    value: str,
) -> None:
    view_end = view_start + 1
    while view_end < len(lines) and not lines[view_end].startswith("  - type:"):
        view_end += 1

    option_line = f"      {key}: {value}"
    for index in range(view_start + 1, view_end):
        if lines[index].strip().startswith(f"{key}:"):
            lines[index] = option_line
            return

    for index in range(view_start + 1, view_end):
        if lines[index] == "    options:":
            lines.insert(index + 1, option_line)
            return

    for index in range(view_start + 1, view_end):
        if lines[index].strip().startswith("swimLane:"):
            lines[index + 1:index + 1] = ["    options:", option_line]
            return

    lines.insert(view_end, "    options:")
    lines.insert(view_end + 1, option_line)


def add_project_swimlanes_to_task_kanban_views(text: str) -> str:
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        view_type = lines[index].strip()
        if view_type not in {"- type: tasknotesKanban", "- type: kanban-view"}:
            index += 1
            continue

        end = index + 1
        while end < len(lines) and not lines[end].startswith("  - type:"):
            end += 1
        block = lines[index:end]

        if view_type == "- type: tasknotesKanban":
            swimlane_offsets = [i for i, line in enumerate(block) if line.strip().startswith("swimLane:")]
            if swimlane_offsets:
                for offset in reversed(swimlane_offsets):
                    del lines[index + offset]
                end -= len(swimlane_offsets)
                block = lines[index:end]

            group_offset = next((i for i, line in enumerate(block) if line == "    groupBy:"), None)
            if group_offset is not None:
                insert_offset = group_offset + 1
                while insert_offset < len(block) and block[insert_offset].startswith("      "):
                    insert_offset += 1
                lines.insert(index + insert_offset, "    swimLane: note.projects")
                add_or_update_task_kanban_option(lines, index, "maxSwimlaneHeight", "99999")
                index = end + 1
                continue
            options_offset = next((i for i, line in enumerate(block) if line == "    options:"), None)
            if options_offset is not None:
                lines.insert(index + options_offset, "    swimLane: note.projects")
                add_or_update_task_kanban_option(lines, index, "maxSwimlaneHeight", "99999")
                index = end + 1
                continue
            continue

        if view_type == "- type: kanban-view":
            if any(line.strip().startswith("swimlaneByProperty:") for line in block):
                index = end
                continue
            group_offset = next((i for i, line in enumerate(block) if line == "    groupByProperty: status"), None)
            if group_offset is not None:
                lines.insert(index + group_offset + 1, "    swimlaneByProperty: projects")
                index = end + 1
                continue

        index = end
    return "\n".join(lines)


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "quarterly": f"{day.year}-Q{quarter}",
        "yearly": f"{day.year}",
    }


def managed_properties(marker: str = GENERATED_MARKER) -> str:
    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    return f'generated: true\ngenerated_at: {generated_at}\nmanaged_by: "{marker}"'


def base_properties(marker: str = GENERATED_MARKER) -> str:
    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    return f'generated: true\ngenerated_at: {generated_at}\nmanaged_by: "{marker}"'


def yaml_list(items: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in items)


def content_directories() -> list[str]:
    return [
        "_obsidian/content",
        "_obsidian/content-schedules",
        "_obsidian/content/publications/blogs",
        "_obsidian/content/publications/newsletters",
        "_obsidian/content/publications/youtube",
        "_obsidian/content/items/blog-posts",
        "_obsidian/content/items/newsletter-issues",
        "_obsidian/content/items/youtube-videos",
        "_obsidian/content/items/social-posts",
        "_obsidian/content/ideas",
        "_obsidian/content/archive",
    ]


def content_cadence_config(run_date: dt.date) -> str:
    anchor = run_date - dt.timedelta(days=run_date.weekday())
    return f"""{{
  "enabled": false,
  "timezone": "UTC",
  "anchor_date": "{anchor.isoformat()}",
  "window_weeks": 4,
  "schedule_format": "publicationThenByWeek",
  "publication_order": [],
  "publications": {{}}
}}
"""


def inline_code_list(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items)


def context_folder_note(status: str, context_type: str, content_enabled: bool = False, default_capture: bool = False) -> str:
    content_value = "true" if content_enabled else "false"
    default_value = "true" if default_capture else "false"
    return f"""---
status: {status}
context_type: {context_type}
content_enabled: {content_value}
default_capture: {default_value}
---
"""


def entity_note_template(
    entity: str,
    entity_type: str | None = None,
    *,
    status: str = "active",
    content_enabled: bool = False,
    default_capture: bool = False,
) -> str:
    source_type = entity_type or "entity"
    social_section = ""
    if source_type == "personal-brand":
        social_section = """
### Social Selling

#### Method

#### Proof Sources
"""
    content_value = "true" if content_enabled else "false"
    default_value = "true" if default_capture else "false"
    return f"""---
status: {status}
context_type: {source_type}
content_enabled: {content_value}
default_capture: {default_value}
{managed_properties()}
---

# {entity}

## Identity

### Declaration

### Source Notes

## Momentum

### Rhythm

### Proof Sources
{social_section}
"""


def has_markdown_heading(text: str, heading: str) -> bool:
    return re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, flags=re.M) is not None


def ensure_entity_note_sections(text: str, entity_type: str) -> str:
    updated = text.rstrip()
    if not has_markdown_heading(updated, "Identity"):
        updated += "\n\n## Identity\n\n### Source Notes\n"
    if not has_markdown_heading(updated, "Momentum"):
        updated += "\n\n## Momentum\n\n### Rhythm\n\n### Proof Sources\n"
    if entity_type == "personal-brand" and not has_markdown_heading(updated, "Social Selling"):
        updated += "\n\n### Social Selling\n\n#### Method\n\n#### Proof Sources\n"
    return updated.rstrip() + "\n"


def has_frontmatter(existing: str) -> bool:
    return existing.startswith("---\n") and existing.find("\n---", 4) != -1


def split_frontmatter(existing: str) -> tuple[list[str], str]:
    if not has_frontmatter(existing):
        return [], existing
    end = existing.find("\n---", 4)
    marker_end = end + len("\n---")
    if marker_end < len(existing) and existing[marker_end] == "\n":
        body = existing[marker_end + 1 :]
    else:
        body = existing[marker_end:]
    return existing[4:end].splitlines(), body


def update_context_folder_note(existing: str, status: str, context_type: str, content_enabled: bool, default_capture: bool) -> str:
    lines, body = split_frontmatter(existing)
    desired = {
        "status": status,
        "context_type": context_type,
        "content_enabled": "true" if content_enabled else "false",
        "default_capture": "true" if default_capture else "false",
    }
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        if ":" in line and not line.startswith(" "):
            key = line.split(":", 1)[0].strip()
            if key in desired:
                output.append(f"{key}: {desired[key]}")
                seen.add(key)
                continue
        output.append(line)
    for key in ["status", "context_type", "content_enabled", "default_capture"]:
        if key not in seen:
            output.append(f"{key}: {desired[key]}")
    return "---\n" + "\n".join(output) + "\n---\n" + body


def is_frontmatter_only(existing: str) -> bool:
    if existing.startswith("---\n"):
        end = existing.find("\n---", 4)
        if end != -1:
            body_start = existing.find("\n", end + 4)
            body = "" if body_start == -1 else existing[body_start + 1 :]
            return body.strip() == ""
    return existing.strip() == ""


def personalized_quickstart(
    entities: list[str],
    default_entity: str,
    active_entities: list[str],
    content_entities: list[str],
) -> str:
    entity_lines = "\n".join(f"- `{entity}`" for entity in entities)
    active_lines = "\n".join(f"- `{entity}`" for entity in active_entities)
    content_lines = "\n".join(f"- `{entity}`" for entity in content_entities) or "- None"
    return f"""---
{managed_properties()}
---
# Personalized Quickstart

Open this whole folder as the root Obsidian vault. Context folders are content workspaces inside the root vault, not standalone Obsidian vaults.

## Mental Model

- Root vault: master control panel across all context folders.
- Context folders: source-of-truth workspaces.
- `_master`: operating manual, generated dashboards, setup scripts, shared templates, agent context, agent skills, reusable scripts, media, and Mac/dev tools.
- `_library`: learning material, research, swipe files, downloaded examples, lead magnets, and source material.
- `_wiki`: synthesized knowledge built by LLMs using `_wiki/AGENTS.md` and `_wiki/karpathy-initial-proompt.md`.
- `other`: archive/dump zone for excess context folders and miscellaneous files.

## Context Folders

{entity_lines}

Default capture context folder:

- `{default_entity}`

Default active context folders:

{active_lines}

Each context folder has an inside-folder note named after the folder, for example `business/business.md`. Its `status` property controls the default agent periodic rollups:

- `status: active`: included when you run the periodic generator with no context folder args.
- `status: archived`: kept available but excluded from default rollups.
- blank or missing status: not active.

Its `content_enabled` property controls whether bootstrap scaffolds content infrastructure:

- `content_enabled: true`: create content folders, content schedule folders, publication notes, cadence config, and content Bases.
- `content_enabled: false`: no content scaffold by default.

Its `default_capture` property marks the context folder that receives unspecific tasks and periodic capture.

Content-enabled context folders:

{content_lines}

The context folder note can keep a short body, but the frontmatter is the control panel:

```yaml
---
status: active
content_enabled: false
default_capture: true
---
```

Context folder operating folders start with `_` so normal folders can sit directly under each context folder.

```text
<context-folder>/
  <context-folder>.md
  _obsidian/
    attachments/
    bases/
    content/
    excalidraw/
    epics/
    periodic/
      daily/
      weekly/
      quarterly/
      yearly/
    projects/
    tasks/
    templates/
      periodic/
  <real context-specific folders, such as docs or projects/>
```

Content-enabled context folders also get:

```text
<context-folder>/_obsidian/content/content-cadence.json
<context-folder>/_obsidian/content-schedules/
<context-folder>/_obsidian/content/
  publications/
  items/
  ideas/
  archive/
```

`_obsidian/content/content-cadence.json` controls recurring publication cadence, `schedule_format`, and `publication_order`. Normal refresh is create-only for content schedules and maintains the `Current content schedule:` line in the context folder note; run `vault content --force` only when intentionally regenerating an existing managed schedule note.

The context folder note is the entity's durable operating source for Identity and Momentum. For personal-brand entities, Social Selling lives as a third-level section inside Momentum. Each context folder owns its local periodic templates under `_obsidian/templates/periodic`. `_master/_obsidian/templates/shared` is for root-level shared non-periodic templates, entity-note templates, content templates, and the default TaskNotes template.

## Agent Files

- `AGENTS.md`: generated instructions for Codex, Claude, and other coding agents. Edit `_master/system/bootstrap/AGENTS.template.md`, then rerun `python3 _master/system/bootstrap/generate_agents.py`.
- `CLAUDE.md`: symlink to `AGENTS.md`.
- `.agents/skills`: agent skills folder.
- `.claude/skills`: symlink to `.agents/skills`.
- `_master/system/context/CONTEXT.md` and `_master/system/context/context.json`: generated current state for agents.
- `_master/system/context/*.md`: generated readable files for agents plus durable agent operating notes.

Context folders do not carry agent symlinks or their own agent workspaces. Open the root vault when working with agents.

## Root-Only Workflow

Use the root vault as your daily control panel:

1. Create tasks with TaskNotes from the root vault.
2. Choose a context to route the task into the right context folder.
3. Use daily, weekly, quarterly, and yearly periodic notes. Monthly periodic notes are intentionally not used.
4. Open the current flat rollup in `_master/system/context/` for readable rollups across active context folders.
5. Open `_master/_obsidian/bases` and `_master/_obsidian/bases` for dashboards and task views.

Task routing:

```text
No context or default context -> {default_entity}/_obsidian/tasks
@business              -> business/_obsidian/tasks
@dev                     -> dev/_obsidian/tasks
```

Periodic notes:

```text
Context folder source notes: <context-folder>/_obsidian/periodic/<daily|weekly|quarterly|yearly>/
Agent rollups:       _master/system/context/<period-id>.md
```

The generator creates missing context folder periodic notes from each context folder's own `_obsidian/templates/periodic/<period>-template.md` file. Each active context folder can keep lean local prompts for its own operating rhythm.

Agent rollups inline each context folder source note so agents can read them without Obsidian Sync Embeds:

````md
_Source: `business/_obsidian/periodic/quarterly/2026-Q2.md`_
````

Context folder periodic notes remain the editable source of truth. Sync Embeds notes live at `_master/system/obsidian_notes/beta_plugins_docs/README-sync-embeds.md`.

Agent periodic generator:

```bash
vault periodic
vault periodic --all
vault periodic --context-folders dev,claudeche
```

`context.py` calls this generator and the content schedule generator for the default refresh path, so one context refresh updates context, current 4-week content schedules, realized system notes, and current agent periodic rollups.

No args means active context folders from context folder notes. `--all` means all configured context folders. `--context-folders` means only that one-off context folder list.

Periodic cleanup:

```bash
python3 _master/system/scripts/delete_master_periodic_notes_for_now.py
python3 _master/system/scripts/delete_master_periodic_notes_for_now.py --context-folders dev,claudeche
```

No args deletes the current generated master rollups under `_master/system/context`. Use `--context-folders` or `--all` when you also want to clean current context folder source notes.

Add a context folder:

```bash
vault folder -n new-context-folder -s active
vault folder -n new-context-folder -s archived
```

Root Obsidian settings live in the current root `.obsidian` folder. Bootstrap does not copy or patch profile settings.

## Where Things Go

- Active context folder operating material: the matching context folder.
- Tasks: `<context-folder>/_obsidian/tasks`.
- Projects: `<context-folder>/_obsidian/projects`.
- Epics: `<context-folder>/_obsidian/epics`.
- Entity operating note: `<context-folder>/<context-folder>.md`.
- Content assets for content-enabled entities: `<context-folder>/_obsidian/content`.
- Content schedules for content-enabled entities: `<context-folder>/_obsidian/content-schedules`.
- Periodic notes: `<context-folder>/_obsidian/periodic`.
- Learning, research, downloaded templates, lead magnets: `_library`.
- Durable synthesized knowledge: `_wiki`.
- Reusable assets/scripts/media: `_master`.
- Old or uncertain material: `other`.

Context folders are not learning folders. If learning from `_library` or `_wiki` belongs in a context folder, rewrite it as an operating artifact first: SOP, keep-in-mind note, training note, checklist, playbook, decision record, policy, or active reference.

## TaskNotes Shorthand

TaskNotes stores each task as one Markdown note with YAML frontmatter. Its natural language parser can extract structure from the task title/body.

- `#tag`: adds an Obsidian tag.
- `@context`: sets context. In this setup, context also controls which context folder `_obsidian/tasks` folder is used.
- `+project`: links a simple project.
- `+[[Project Name]]`: links a project note, usually from `<context-folder>/_obsidian/projects`.
- `tomorrow`, `next Friday`, `January 15 at 3pm`: parsed as dates/times.
- `high`, `normal`, `low`: parsed as priority words.
- `!`: configurable priority trigger; TaskNotes supports it, but it may need to be enabled in settings.
- `backlog`, `up-next`, `to-be-resumed`, `ongoing`, `in-progress`, `done`, `archived`: configured status words.
- `*`: configurable status trigger.
- `2h`, `30min`, `1h30m`: parsed as time estimates.
- `daily`, `weekly`, `every Monday`: parsed as recurrence.

Examples:

```text
Prepare launch checklist tomorrow @business #marketing high
Review contract next Friday @dev +[[Client Work]] in-progress
Draft weekly reflection @personal 30min
```

Useful docs:

- TaskNotes NLP syntax: https://tasknotes.dev/features/inline-tasks/
- TaskNotes task properties: https://tasknotes.dev/settings/task-properties/

## First Things To Open

- `_master/01-Context.md`
- `_master/system/context/<today>.md`
- `_master/_obsidian/bases/content-kanban.base`
- `_master/_obsidian/bases/tasks-home.base`
- `_master/_obsidian/bases/tasks-today.base`
"""


def shared_task_template() -> str:
    return f"""---
title: <% tp.file.title %>
status: backlog
priority: normal
scheduled: <% tp.date.now("YYYY-MM-DD") %>
contexts:
  - <% tp.file.folder(true).split('/')[0] %>
tags:
  - task
{managed_properties()}
---

# <% tp.file.title %>

## Outcome

## Notes
"""


def content_item_template() -> str:
    return f"""---
type: content
entity: <% tp.file.folder(true).split('/')[0] %>
content_kind: social-post
platform:
publication:
status: idea
publish_date:
source:
repurposed_from:
cta:
conversion_goal:
tags:
  - content
{managed_properties()}
---

# <% tp.file.title %>

## AI Summary

## Draft

## Notes
"""


def publication_template() -> str:
    return f"""---
type: publication
entity: <% tp.file.folder(true).split('/')[0] %>
publication_type:
publication_id:
name: <% tp.file.title %>
status: active
primary_cta:
tags:
  - publication
{managed_properties()}
---

# <% tp.file.title %>

## Purpose

## Audience

## Rules
"""


def excalidraw_template() -> str:
    return """{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [],
  "appState": {
    "gridSize": null,
    "viewBackgroundColor": "#ffffff"
  },
  "files": {}
}
"""


def starter_task(entity: str, scheduled: str) -> str:
    return f"""---
title: Set up {entity} workspace
status: backlog
priority: normal
scheduled: {scheduled}
contexts:
  - {entity}
tags:
  - task
{managed_properties()}
---

# Set up {entity} workspace

Use this starter task to confirm TaskNotes sees this context folder's `_obsidian/tasks` folder.
"""


def all_tasks_base() -> str:
    return f"""# All Tasks
{base_properties()}

filters:
  and:
    - file.hasTag("task")
    - 'status != "done"'

views:
  - type: table
    name: "Open Tasks"
    order:
      - file.name
      - status
      - priority
      - scheduled
      - due
      - contexts
"""


def active_folder_filter(folders: list[str]) -> str:
    if not folders:
        return "    - 'false'"
    lines = ["    - or:"]
    lines.extend(f'      - file.inFolder("{folder}")' for folder in folders)
    return "\n".join(lines)


def all_projects_base(active_entities: list[str]) -> str:
    folders = [f"{entity}/_obsidian/projects" for entity in active_entities]
    return f"""# All Projects
{base_properties()}

filters:
  and:
    - 'type == "project"'
{active_folder_filter(folders)}

views:
  - type: table
    name: "Active Projects"
    order:
      - file.name
      - status
      - contexts
      - epic
      - file.folder
"""


def all_epics_base(active_entities: list[str]) -> str:
    folders = [f"{entity}/_obsidian/epics" for entity in active_entities]
    return f"""# All Epics
{base_properties()}

filters:
  and:
    - 'type == "epic"'
{active_folder_filter(folders)}

views:
  - type: table
    name: "Active Epics"
    order:
      - file.name
      - status
      - contexts
      - file.folder
"""


def today_base() -> str:
    return f"""# Today
{base_properties()}

filters:
  and:
    - file.hasTag("task")
    - or:
      - 'scheduled == today()'
      - 'due == today()'
      - 'status == "in-progress"'

views:
  - type: table
    name: "Today"
    order:
      - file.name
      - status
      - priority
      - scheduled
      - due
      - contexts
"""


def this_week_base() -> str:
    return f"""# This Week
{base_properties()}

filters:
  and:
    - file.hasTag("task")
    - or:
      - 'scheduled >= today() && scheduled <= today() + "7d"'
      - 'due >= today() && due <= today() + "7d"'

views:
  - type: table
    name: "This Week"
    order:
      - file.name
      - status
      - priority
      - scheduled
      - due
      - contexts
"""


def all_periodic_base() -> str:
    return f"""# All Periodic Notes
{base_properties()}

filters:
  and:
    - 'type == "periodic"'
    - 'file.path.contains("/_obsidian/periodic/")'

views:
  - type: table
    name: "Periodic Notes"
    order:
      - file.name
      - context_folder
      - period
      - period_id
      - file.folder
"""


def all_content_base(content_entities: list[str]) -> str:
    folders = [f"{entity}/_obsidian/content" for entity in content_entities]
    return f"""# All Content
{base_properties()}

filters:
  and:
    - or:
      - 'type == "content"'
      - 'type == "publication"'
{active_folder_filter(folders)}

views:
  - type: calendar
    name: "All Content Calendar"
    order:
      - file.name
      - entity
      - platform
      - publication
      - status
      - content_kind
      - cta
    startDate: publish_date
    weekStartDay: monday
  - type: table
    name: "Content Queue"
    order:
      - file.name
      - entity
      - content_kind
      - platform
      - publication
      - status
      - publish_date
      - cta
      - conversion_goal
      - file.folder
  - type: table
    name: "Publication Definitions"
    order:
      - file.name
      - entity
      - publication_type
      - publication_id
      - name
      - status
      - primary_cta
      - file.folder
"""


def content_calendar_filter_block(name: str, filters: str | None = None) -> str:
    filter_block = f"    filters:\n{filters}" if filters else ""
    spacer = "\n" if filters else ""
    return f"""  - type: calendar
    name: "{name}"
{filter_block}{spacer}    order:
      - file.name
      - entity
      - platform
      - publication
      - status
      - content_kind
      - cta
      - conversion_goal
    startDate: publish_date
    weekStartDay: monday
"""


def content_calendar_views(content_entities: list[str]) -> str:
    views = [content_calendar_filter_block("All Content Calendar")]
    views.extend(
        content_calendar_filter_block(
            f"{entity} Calendar",
            f'      and:\n        - \'entity == "{entity}"\'\n',
        )
        for entity in content_entities
    )
    views.extend(
        [
            content_calendar_filter_block("Blog", '      and:\n        - \'platform == "blog"\'\n'),
            content_calendar_filter_block(
                "Newsletter",
                '      or:\n        - \'platform == "newsletter"\'\n        - \'content_kind == "newsletter-issue"\'\n',
            ),
            content_calendar_filter_block("YouTube", '      and:\n        - \'platform == "youtube"\'\n'),
            content_calendar_filter_block(
                "LinkedIn",
                '      or:\n        - \'platform == "linkedin"\'\n        - \'publication == "linkedin"\'\n',
            ),
            content_calendar_filter_block("X", '      or:\n        - \'platform == "x"\'\n        - \'publication == "x"\'\n'),
            content_calendar_filter_block(
                "Substack",
                '      or:\n        - \'platform == "substack"\'\n        - \'publication == "substack-notes"\'\n',
            ),
            content_calendar_filter_block("Social", '      and:\n        - \'platform == "social"\'\n'),
        ]
    )
    return "".join(views)


def content_calendar_base(content_entities: list[str]) -> str:
    folders = [f"{entity}/_obsidian/content/items" for entity in content_entities]
    return f"""# Content Calendar
{base_properties()}

filters:
  and:
    - 'type == "content"'
{active_folder_filter(folders)}

views:
{content_calendar_views(content_entities)}  - type: table
    name: "Publish Dates"
    order:
      - publish_date
      - file.name
      - entity
      - status
      - platform
      - publication
      - content_kind
      - cta
      - conversion_goal
    sort:
      - column: publish_date
        direction: ASC
"""


CONTENT_STATUS_ORDER = [
    "idea",
    "cogs-are-turning",
    "draft",
    "planning-scripting",
    "scheduled",
    "published",
    "cancelled",
]

CONTENT_STATUS_COLORS = {
    "idea": "yellow",
    "cogs-are-turning": "orange",
    "draft": "blue",
    "planning-scripting": "purple",
    "scheduled": "cyan",
    "published": "green",
    "cancelled": "red",
}

CONTENT_PLATFORM_BADGE_FORMULA = (
    'if(publication=="linkedin" || platform=="linkedin","💼 LinkedIn",'
    'if(publication=="x" || platform=="x","𝕏 X",'
    'if(publication=="substack-notes" || platform=="substack","📝 Substack",'
    'if(platform=="youtube","▶ YouTube",'
    'if(platform=="blog","✍ Blog",'
    'if(platform=="newsletter" || content_kind=="newsletter-issue","✉ Newsletter",'
    'if(platform=="social","◇ Social",platform)))))))'
)


def content_kanban_status_config() -> str:
    order = "\n".join(f"        - {status}" for status in CONTENT_STATUS_ORDER)
    colors = "\n".join(f"        {status}: {color}" for status, color in CONTENT_STATUS_COLORS.items())
    return f"""    groupByProperty: status
    columnOrders:
      note.status:
{order}
    columnColors:
      note.status:
{colors}
    order:
      - formula.platformBadge
    wrapPropertyValues: false
"""


def content_kanban_view(name: str, filters: str | None = None) -> str:
    filter_block = f"    filters:\n{filters}" if filters else ""
    spacer = "\n" if filters else ""
    return f"""  - type: kanban-view
    name: "{name}"
{filter_block}{spacer}{content_kanban_status_config()}"""


def content_kanban_views(include_entity: bool) -> str:
    return "".join(
        [
            content_kanban_view("All Content Board"),
            content_kanban_view("Blog", '      and:\n        - \'platform == "blog"\'\n'),
            content_kanban_view(
                "Newsletter",
                '      or:\n        - \'platform == "newsletter"\'\n        - \'content_kind == "newsletter-issue"\'\n',
            ),
            content_kanban_view("YouTube", '      and:\n        - \'platform == "youtube"\'\n'),
            content_kanban_view(
                "LinkedIn",
                '      or:\n        - \'platform == "linkedin"\'\n        - \'publication == "linkedin"\'\n',
            ),
            content_kanban_view("X", '      or:\n        - \'platform == "x"\'\n        - \'publication == "x"\'\n'),
            content_kanban_view(
                "Substack",
                '      or:\n        - \'platform == "substack"\'\n        - \'publication == "substack-notes"\'\n',
            ),
            content_kanban_view("Social", '      and:\n        - \'platform == "social"\'\n'),
        ]
    )


def content_kanban_base(content_entities: list[str]) -> str:
    folders = [f"{entity}/_obsidian/content" for entity in content_entities]
    return f"""# Content Kanban
{base_properties()}

filters:
  and:
    - 'type == "content"'
{active_folder_filter(folders)}

formulas:
  statusRank: 'if(status=="idea",1,if(status=="cogs-are-turning",2,if(status=="draft",3,if(status=="planning-scripting",4,if(status=="scheduled",5,if(status=="published",6,if(status=="cancelled",99,999)))))))'
  platformBadge: '{CONTENT_PLATFORM_BADGE_FORMULA}'

properties:
  formula.platformBadge:
    displayName: Platform

views:
{content_kanban_views(include_entity=True)}"""


def entity_dashboard_base(entity: str) -> str:
    return f"""# {entity} Dashboard
{base_properties()}

filters:
  or:
    - file.inFolder("{entity}/_obsidian/tasks")
    - file.inFolder("{entity}/_obsidian/projects")
    - file.inFolder("{entity}/_obsidian/epics")
    - file.inFolder("{entity}/_obsidian/periodic")

views:
  - type: table
    name: "Context Folder Files"
    order:
      - file.name
      - file.folder
      - type
      - contexts
      - epic
      - period
      - status
      - priority
      - scheduled
      - due
"""


def entity_projects_base(entity: str) -> str:
    return f"""# {entity} Projects
{base_properties()}

filters:
  and:
    - file.inFolder("{entity}/_obsidian/projects")
    - 'type == "project"'

views:
  - type: table
    name: "Projects"
    order:
      - file.name
      - status
      - contexts
      - epic
      - file.folder
"""


def entity_epics_base(entity: str) -> str:
    return f"""# {entity} Epics
{base_properties()}

filters:
  and:
    - file.inFolder("{entity}/_obsidian/epics")
    - 'type == "epic"'

views:
  - type: table
    name: "Epics"
    order:
      - file.name
      - status
      - contexts
      - file.folder
"""


def entity_content_base(entity: str) -> str:
    return f"""# {entity} Content
{base_properties()}

filters:
  and:
    - or:
      - 'type == "content"'
      - 'type == "publication"'
    - file.inFolder("{entity}/_obsidian/content")

views:
  - type: calendar
    name: "Content Calendar"
    order:
      - file.name
      - platform
      - publication
      - status
      - content_kind
      - cta
    startDate: publish_date
    weekStartDay: monday
  - type: table
    name: "Content"
    order:
      - file.name
      - content_kind
      - platform
      - publication
      - status
      - publish_date
      - cta
      - conversion_goal
      - file.folder
  - type: table
    name: "Publications"
    order:
      - file.name
      - publication_type
      - publication_id
      - name
      - status
      - primary_cta
      - file.folder
"""


def entity_content_queue_base(entity: str) -> str:
    return f"""# {entity} Content Queue
{base_properties()}

filters:
  and:
    - 'type == "content"'
    - file.inFolder("{entity}/_obsidian/content/items")

views:
  - type: table
    name: "By Status"
    order:
      - file.name
      - status
      - content_kind
      - platform
      - publication
      - publish_date
      - cta
      - conversion_goal
    sort:
      - column: status
        direction: ASC
      - column: publish_date
        direction: ASC
"""


def entity_content_calendar_base(entity: str) -> str:
    return f"""# {entity} Content Calendar
{base_properties()}

filters:
  and:
    - 'type == "content"'
    - file.inFolder("{entity}/_obsidian/content/items")

views:
  - type: calendar
    name: "Publish Calendar"
    order:
      - file.name
      - platform
      - publication
      - status
      - content_kind
      - cta
      - conversion_goal
    startDate: publish_date
    weekStartDay: monday
  - type: table
    name: "Publish Dates"
    order:
      - publish_date
      - file.name
      - status
      - platform
      - publication
      - content_kind
      - cta
      - conversion_goal
    sort:
      - column: publish_date
        direction: ASC
"""


def entity_content_kanban_base(entity: str) -> str:
    return f"""# {entity} Content Kanban
{base_properties()}

filters:
  and:
    - 'type == "content"'
    - file.inFolder("{entity}/_obsidian/content/items")

formulas:
  statusRank: 'if(status=="idea",1,if(status=="cogs-are-turning",2,if(status=="draft",3,if(status=="planning-scripting",4,if(status=="scheduled",5,if(status=="published",6,if(status=="cancelled",99,999)))))))'
  platformBadge: '{CONTENT_PLATFORM_BADGE_FORMULA}'

properties:
  formula.platformBadge:
    displayName: Platform

views:
{content_kanban_views(include_entity=False)}"""


def parse_date(value: str | None) -> dt.date:
    if not value:
        return dt.date.today()
    return dt.date.fromisoformat(value)


def parse_entities(value: str | None) -> list[str]:
    if not value:
        return DEFAULT_ENTITIES[:]
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_context_types(value: str | None, entities: list[str]) -> dict[str, str]:
    context_types = {entity: DEFAULT_CONTEXT_TYPES.get(entity, "business") for entity in entities}
    if not value:
        return context_types
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise SystemExit(f"context type entry must be folder:type, got {item!r}")
        entity, context_type = [part.strip() for part in item.split(":", 1)]
        if entity not in entities:
            raise SystemExit(f"context type configured for unknown context folder {entity!r}")
        if context_type not in VALID_CONTEXT_TYPES:
            raise SystemExit(f"unsupported context type {context_type!r}; supported: {sorted(VALID_CONTEXT_TYPES)}")
        context_types[entity] = context_type
    return context_types


def parse_coding_agents(value: str | None) -> list[str]:
    if not value:
        return ["codex"]
    agents = [item.strip().lower() for item in value.split(",") if item.strip()]
    unsupported = [agent for agent in agents if agent not in VALID_CODING_AGENTS]
    if unsupported:
        raise SystemExit(f"unsupported coding agents: {unsupported}; supported agents: {sorted(VALID_CODING_AGENTS)}")
    return sorted(set(agents))


def prompt(default: str, label: str) -> str:
    answer = input(f"{label} [{default}]: ").strip()
    return answer or default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the lowercase context folder Obsidian layout.")
    parser.add_argument("--root", default=".", help="Vault root. Defaults to current directory.")
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders.")
    parser.add_argument("--sub-vaults", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--entities", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--active-context-folders", dest="active_entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders to mark active in folder notes.")
    parser.add_argument("--active-sub-vaults", dest="active_entities", help=argparse.SUPPRESS)
    parser.add_argument("--active-entities", dest="active_entities", help=argparse.SUPPRESS)
    parser.add_argument("--content-context-folders", dest="content_entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders to mark content_enabled in folder notes.")
    parser.add_argument("--content-sub-vaults", dest="content_entities", help=argparse.SUPPRESS)
    parser.add_argument("--content-entities", dest="content_entities", help=argparse.SUPPRESS)
    parser.add_argument("--context-types", dest="context_types", metavar="CONTEXT_TYPES", help="Comma-separated folder:type entries. Types: personal, personal-brand, business.")
    parser.add_argument("--default-context-folder", dest="default_entity", metavar="CONTEXT_FOLDER", default="personal", help="Default capture context folder.")
    parser.add_argument("--default-sub-vault", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--default-entity", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--coding-agents", default="codex", help="Comma-separated coding agents: codex, claude, or codex,claude.")
    parser.add_argument("--date", help="Run date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--skip-install-vault-command", action="store_true", help="Skip installing ~/.local/bin/vault.")
    parser.add_argument("--skip-generate-agents", action="store_true", help="Skip root AGENTS.md generation.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    entities = parse_entities(args.entities)
    active_entities = parse_entities(args.active_entities) if args.active_entities else DEFAULT_ACTIVE_ENTITIES[:]
    content_entities = parse_entities(args.content_entities) if args.content_entities else DEFAULT_CONTENT_ENTITIES[:]
    default_entity = args.default_entity
    context_types = parse_context_types(args.context_types, entities)
    coding_agents = parse_coding_agents(args.coding_agents)

    if args.interactive:
        entities = parse_entities(prompt(",".join(entities), "Context folders"))
        active_entities = parse_entities(prompt(",".join(active_entities), "Active context folders"))
        content_entities = parse_entities(prompt(",".join(content_entities), "Content-enabled context folders"))
        context_types = {entity: DEFAULT_CONTEXT_TYPES.get(entity, "business") for entity in entities}
        context_types = parse_context_types(prompt(",".join(f"{entity}:{context_types[entity]}" for entity in entities), "Context folder types"), entities)
        default_entity = prompt(default_entity, "Default capture context folder")
        coding_agents = parse_coding_agents(prompt(",".join(coding_agents), "Coding agents: codex, claude, or codex,claude"))

    if default_entity not in entities:
        raise SystemExit(f"default context folder {default_entity!r} is not in configured context folders: {entities}")
    missing_active = [entity for entity in active_entities if entity not in entities]
    if missing_active:
        raise SystemExit(f"active context folders are not in configured context folders: {missing_active}")
    missing_content = [entity for entity in content_entities if entity not in entities]
    if missing_content:
        raise SystemExit(f"content-enabled context folders are not in configured context folders: {missing_content}")

    root = Path(args.root).expanduser().resolve()
    bootstrap = Bootstrap(
        root=root,
        entities=entities,
        active_entities=active_entities,
        default_entity=default_entity,
        context_types=context_types,
        coding_agents=coding_agents,
        content_entities=content_entities,
        install_vault_command_enabled=not args.skip_install_vault_command,
        generate_agents_enabled=not args.skip_generate_agents,
        dry_run=args.dry_run,
        run_date=parse_date(args.date),
    )
    bootstrap.run()


if __name__ == "__main__":
    main()
