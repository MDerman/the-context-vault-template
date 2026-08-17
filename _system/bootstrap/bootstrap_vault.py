#!/usr/bin/env python3
"""
Bootstrap this Obsidian workspace into the context folder layout.

The script is intentionally conservative:
- it only overwrites files that contain a stable managed-file marker;
- it leaves user-owned content untouched;
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

CONTENT_FEATURES = {"blog", "social-content", "newsletters"}
CONTENT_FEATURE_DIRECTORIES = {
    "blog": [
        "_obsidian/content/items/blog-posts",
        "_obsidian/content/publications/blogs",
    ],
    "social-content": [
        "_obsidian/content/items/social-posts",
        "_obsidian/content/items/youtube-videos",
        "_obsidian/content/publications/youtube",
        "_obsidian/content/ideas",
        "_obsidian/content/archive",
    ],
    "newsletters": [
        "_obsidian/content/items/newsletter-issues",
        "_obsidian/content/publications/newsletters",
    ],
}
CONTENT_SCHEDULE_DIRECTORIES = [
    "_obsidian/content",
    "_obsidian/content-schedules",
]
PERIODS = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "quarterly": "quarterly",
    "yearly": "yearly",
}
VALID_CODING_AGENTS = {"codex", "claude"}

GENERATED_MARKER = "vault.bootstrap"
VAULT_PERIODIC_MARKER = "vault.periodic"
TASK_CONTEXT_VIEWS_MARKER = "vault.bootstrap.task-context-views"
BEGIN_TASK_CONTEXT_VIEWS = f"  # BEGIN {TASK_CONTEXT_VIEWS_MARKER}"
END_TASK_CONTEXT_VIEWS = f"  # END {TASK_CONTEXT_VIEWS_MARKER}"
EPIC_VIEWS_MARKER = "vault.epic-views"
BEGIN_EPIC_VIEWS = f"  # BEGIN {EPIC_VIEWS_MARKER}: epic views"
END_EPIC_VIEWS = f"  # END {EPIC_VIEWS_MARKER}: epic views"
BOOTSTRAP_MARKERS = (GENERATED_MARKER,)
VAULT_PERIODIC_MARKERS = (VAULT_PERIODIC_MARKER,)
MANAGED_MARKERS = (GENERATED_MARKER, VAULT_PERIODIC_MARKER)
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
        coding_agents: list[str],
        context_features: dict[str, set[str]],
        content_schedule_entities: list[str],
        install_vault_command_enabled: bool,
        agent_symlinks_enabled: bool,
        dry_run: bool,
        run_date: dt.date,
        folder_templates: dict[str, str] | None = None,
    ) -> None:
        self.root = root
        self.entities = entities
        self.active_entities = active_entities
        self.default_entity = default_entity
        self.coding_agents = coding_agents
        self.context_features = {
            entity: set(context_features.get(entity, set())) for entity in entities
        }
        self.content_schedule_entities = content_schedule_entities
        self.content_entities = [
            entity for entity in entities if self.context_features.get(entity)
        ]
        self.install_vault_command_enabled = install_vault_command_enabled
        self.agent_symlinks_enabled = agent_symlinks_enabled
        self.dry_run = dry_run
        self.run_date = run_date
        self.folder_templates = dict(folder_templates or {})

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

    def ensure_task_kanban_project_swimlanes(
        self,
        path: Path,
        *,
        sync_context_views: bool = False,
        drop_epic_views: bool = False,
    ) -> None:
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        updated = add_project_swimlanes_to_task_kanban_views(text)
        if sync_context_views:
            updated = sync_task_context_views(updated, self.entities, drop_epic_views=drop_epic_views)
        if updated == text:
            return
        self.log(f"patch task view wiring in {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(updated, encoding="utf-8")

    def write_if_missing(self, path: Path, content: str) -> None:
        if path.exists():
            return
        self.ensure_dir(path.parent)
        self.log(f"write {rel(path, self.root)}")
        if not self.dry_run:
            path.write_text(content, encoding="utf-8")

    def write_context_folder_note(self, entity: str, status: str, content_schedules_enabled: bool, default_capture: bool) -> None:
        path = context_folder_note_path(self.root, entity)
        content = context_folder_note(status, content_schedules_enabled, default_capture)
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
        content = update_context_folder_note(existing, status, content_schedules_enabled, default_capture)
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
        system_dirs = [
            "_system/_obsidian/bases",
            "_system/_obsidian/templates/shared/content",
            "_system/_obsidian/templates/shared/entity-notes",
            "_system/_obsidian/excalidraw",
            "_system/_obsidian/excalidraw/Scripts",
            "_system/_obsidian/periodic/monthly",
            "_system/agents",
            "_system/bootstrap",
            "_system/commands",
            "_system/local",
            "_system/local/skills",
            "_system/docs/commands",
            "_system/docs/obsidian",
            "_system/docs/workflows",
            "_system/local/env",
            "_system/inbox",
            "_system/migrations",
            "_system/local/state",
            "_system/sync",
            "_system/tools",
            "_system/_obsidian/attachments",
        ]
        for directory in system_dirs:
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
                "_obsidian/periodic/monthly",
                "_obsidian/periodic/quarterly",
                "_obsidian/periodic/yearly",
                "_obsidian/projects",
                "_obsidian/tasks",
                "_obsidian/tasks/archive",
                "_obsidian/templates",
                "_obsidian/templates/periodic",
            ]:
                self.ensure_dir(self.root / entity / directory)
            for feature in sorted(self.context_features.get(entity, set())):
                for directory in CONTENT_FEATURE_DIRECTORIES[feature]:
                    self.ensure_dir(self.root / entity / directory)
            if entity in self.content_schedule_entities:
                for directory in CONTENT_SCHEDULE_DIRECTORIES:
                    self.ensure_dir(self.root / entity / directory)
        self.setup_folder_templates()

    def setup_folder_templates(self) -> None:
        template_root = self.root / "_system/bootstrap/templates/context-folders"
        for entity, template in sorted(self.folder_templates.items()):
            source_root = template_root / template
            if not source_root.is_dir():
                raise SystemExit(f"Missing folder template: {source_root}")
            for source in sorted(source_root.rglob("*")):
                relative = source.relative_to(source_root)
                if relative == Path(".business-toolkit.json"):
                    continue
                target = self.root / entity / relative
                if source.is_dir():
                    self.ensure_dir(target)
                elif not target.exists():
                    self.copy_file_if_missing(source, target)

    def setup_context_folder_notes(self) -> None:
        active = set(self.active_entities)
        schedules = set(self.content_schedule_entities)
        for entity in self.entities:
            status = "active" if entity in active else "archived"
            self.write_context_folder_note(entity, status, entity in schedules, entity == self.default_entity)

    def setup_agent_infrastructure(self) -> None:
        if self.coding_agents:
            self.ensure_dir(self.root / "_system/agents/skills")
            self.ensure_dir(self.root / "_system/agents/auto-skills")
            self.ensure_dir(self.root / "_system/agents/manual-skills")
            self.ensure_dir(self.root / "_system/agents/gh-skills")
            self.ensure_dir(self.root / "_system/agents/skills-dump")
            self.ensure_dir(self.root / ".agents")
            self.ensure_dir(self.root / ".agents/skills")
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
        shared_excalidraw = self.root / "_system/_obsidian/excalidraw"
        shared_template = shared_excalidraw / "template.excalidraw"
        self.write_if_missing(shared_template, excalidraw_template())

        scripts_source = shared_excalidraw / "Scripts"
        for entity in self.entities:
            entity_scripts = self.root / entity / "_obsidian/excalidraw/Scripts"
            self.copy_tree_contents_preserving(scripts_source, entity_scripts)
            self.copy_file_if_missing(
                shared_template,
                self.root / entity / "_obsidian/excalidraw/template.excalidraw",
            )

    def setup_templates(self) -> None:
        self.safe_remove_generated_path(self.root / "README_PERSONALIZED_QUICKSTART.md", BOOTSTRAP_MARKERS)
        self.safe_remove_generated_path(self.root / "_system" / "README_PERSONALIZED_QUICKSTART.md", BOOTSTRAP_MARKERS)
        self.safe_remove_generated_path(self.root / "_system/_obsidian/templates/shared/entity-notes/personal.md", BOOTSTRAP_MARKERS)
        self.safe_remove_generated_path(self.root / "_system/_obsidian/templates/shared/entity-notes/personal-context-template.md", BOOTSTRAP_MARKERS)
        self.safe_remove_generated_path(self.root / "_system/_obsidian/templates/shared/entity-notes/personal-brand.md", BOOTSTRAP_MARKERS)
        self.safe_remove_generated_path(self.root / "_system/_obsidian/templates/shared/entity-notes/company.md", BOOTSTRAP_MARKERS)
        self.write_managed(self.root / "_system/_obsidian/templates/shared/default-tasks-template.md", shared_task_template())
        self.write_managed(self.root / "_system/_obsidian/templates/shared/content/content-item-template.md", content_item_template())
        self.write_managed(self.root / "_system/_obsidian/templates/shared/content/publication-template.md", publication_template())
        self.write_managed(self.root / "_system/_obsidian/templates/shared/entity-notes/context-template.md", entity_note_template("context"))
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


    def setup_bases(self, *, drop_task_epic_views: bool = False) -> None:
        shared_bases = {
            "epics-all.base": all_epics_base(self.active_entities),
            "tasks-today.base": today_base(),
            "tasks-this-week.base": this_week_base(),
            "content-calendar.base": content_calendar_base(self.content_entities),
            "content-kanban.base": content_kanban_base(self.content_entities),
        }
        for name, content in shared_bases.items():
            self.write_managed(
                self.root / "_system/_obsidian/bases" / name,
                content,
                allow_unmarked_existing=True,
            )

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
            self.remove_path(self.root / "_system/_obsidian/bases" / old_name)
        self.remove_empty_dir(self.root / "_system/tasknotes")
        shared_task_views = self.root / "_system/_obsidian/bases"
        task_view_names = {
            "tasks-agenda.base",
            "tasks-calendar.base",
            "tasks-kanban.base",
            "tasks-mini-calendar.base",
            "tasks-relationships.base",
            "tasks-home.base",
        }
        shared_task_view_names = task_view_names | {"tasks-kanban-v1.base"}
        task_context_view_names = {"tasks-kanban.base", "tasks-kanban-v1.base"}
        for name in shared_task_view_names:
            self.ensure_task_kanban_project_swimlanes(
                shared_task_views / name,
                sync_context_views=name in task_context_view_names,
                drop_epic_views=drop_task_epic_views,
            )

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
            for source in sorted(shared_task_views.glob("*.base")):
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
            if entity in self.content_schedule_entities:
                self.write_if_missing(
                    self.root / entity / "_obsidian/content/content-cadence.json",
                    content_cadence_config(self.run_date),
                )

    def ensure_entity_note(self, entity: str) -> None:
        path = self.root / entity / f"{entity}.md"
        default_capture = entity == self.default_entity
        if not path.exists():
            self.write_managed_if_missing(
                path,
                entity_note_template(
                    entity,
                    status="active" if entity in self.active_entities else "archived",
                    content_schedules_enabled=entity in self.content_schedule_entities,
                    default_capture=default_capture,
                ),
            )
        return

    def install_vault_command(self) -> None:
        import importlib.util

        if not self.install_vault_command_enabled:
            self.log("skip vault command install")
            return
        installer_path = self.root / "_system/bootstrap/install_vault_command.py"
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

    def ensure_agent_file_symlinks(self) -> None:
        import sys

        if not self.agent_symlinks_enabled or not self.coding_agents:
            self.log("skip agent file symlink setup")
            return
        agents_dir = self.root / "_system/agents"
        if str(agents_dir) not in sys.path:
            sys.path.insert(0, str(agents_dir))
        import global_agent_configuration

        report = global_agent_configuration.ensure_agent_paths(self.root, dry_run=self.dry_run)
        for item in report["results"]:
            if item["status"] != "match":
                self.log(f"{item['detail']}: {item['path']}")

    def run_generators(self) -> None:
        import importlib.util
        import sys

        scripts_dir = self.root / "_system/commands"
        refresh_path = scripts_dir / "refresh.py"
        if self.dry_run:
            self.log("skip generators in dry-run")
            return
        scripts_dir_text = str(scripts_dir)
        if scripts_dir_text not in sys.path:
            sys.path.insert(0, scripts_dir_text)
        if not refresh_path.exists():
            raise FileNotFoundError(refresh_path)
        spec = importlib.util.spec_from_file_location("refresh", refresh_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        module.generate_derived_views(
            self.root,
            configured_entities=self.entities,
            day=self.run_date,
        )

    def run(self) -> None:
        self.setup_directories()
        self.setup_context_folder_notes()
        self.setup_agent_infrastructure()
        self.cleanup_obsolete_context_folder_workspace_artifacts()
        self.setup_context_template_dirs()
        self.setup_excalidraw()
        self.setup_templates()
        self.setup_bases()
        self.setup_starter_notes()
        self.ensure_agent_file_symlinks()
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
            index = end
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


TASK_FOLDER_FILTER_RE = re.compile(r'file\.inFolder\("([^"]+)/_obsidian/tasks"\)')
EPIC_LINK_FILTER_RE = re.compile(r'epic\s*==\s*link\("([^"]+)/_obsidian/epics/[^"]+"\)')


def context_label(entity: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_\s]+", entity) if part) or entity


def yaml_double(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def remove_marked_block(lines: list[str], begin: str, end: str) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index] != begin:
            output.append(lines[index])
            index += 1
            continue
        index += 1
        while index < len(lines) and lines[index] != end:
            index += 1
        if index < len(lines):
            index += 1
    return output


def split_base_view_blocks(lines: list[str]) -> tuple[list[list[str]], list[str]]:
    blocks: list[list[str]] = []
    loose: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].startswith("  - type:"):
            start = index
            index += 1
            while index < len(lines) and not lines[index].startswith("  - type:"):
                index += 1
            blocks.append(lines[start:index])
            continue
        if lines[index].strip():
            loose.append(lines[index])
        index += 1
    return blocks, loose


def task_context_entity(block: list[str]) -> str | None:
    match = TASK_FOLDER_FILTER_RE.search("\n".join(block))
    return match.group(1) if match else None


def epic_context_entity(block: list[str]) -> str | None:
    match = EPIC_LINK_FILTER_RE.search("\n".join(block))
    return match.group(1) if match else None


def task_context_view_kind(blocks: list[list[str]]) -> str | None:
    for block in blocks:
        if not block:
            continue
        view_type = block[0].strip()
        if view_type == "- type: tasknotesKanban":
            return "tasknotesKanban"
        if view_type == "- type: kanban-view":
            return "kanban-view"
    return None


def tasknotes_context_view(entity: str) -> list[str]:
    return [
        "  - type: tasknotesKanban",
        f"    name: {yaml_double(context_label(entity))}",
        "    filters:",
        "      and:",
        f'        - file.inFolder("{entity}/_obsidian/tasks")',
        "    groupBy:",
        "      property: status",
        "      direction: ASC",
        "    order:",
        "      - status",
        "      - due",
        "      - scheduled",
        "      - contexts",
        "      - file.tags",
        "      - blockedBy",
        "      - file.tasks",
        "      - projects",
        "      - complete_instances",
        "      - recurrence",
        "    sort:",
        "      - property: tasknotes_manual_order",
        "        direction: DESC",
        "      - property: file.ctime",
        "        direction: DESC",
        "    swimLane: note.projects",
        "    options:",
        "      maxSwimlaneHeight: 99999",
        "      columnWidth: 280",
        "      hideEmptyColumns: false",
        "    columnOrder: '{\"note.status\":[\"backlog\",\"up-next\",\"to-be-resumed\",\"ongoing\",\"in-progress\",\"done\",\"archived\"]}'",
        "    enableSearch: true",
        "    consolidateStatusIcon: true",
    ]


def bases_kanban_context_view(entity: str) -> list[str]:
    return [
        "  - type: kanban-view",
        f"    name: {yaml_double(context_label(entity))}",
        "    filters:",
        "      and:",
        f'        - file.inFolder("{entity}/_obsidian/tasks")',
        "    order:",
        "      - formula.taskBadge",
        "    groupByProperty: status",
        "    swimlaneByProperty: projects",
        "    columnOrders:",
        "      note.status:",
        "        - backlog",
        "        - up-next",
        "        - to-be-resumed",
        "        - ongoing",
        "        - in-progress",
        "        - done",
        "        - archived",
        "    columnColors:",
        "      note.status:",
        "        backlog: yellow",
        "        up-next: cyan",
        "        to-be-resumed: orange",
        "        ongoing: purple",
        "        in-progress: blue",
        "        done: green",
        "        archived: red",
        "    wrapPropertyValues: false",
    ]


def generated_task_context_views(kind: str, entities: list[str]) -> list[str]:
    lines = [BEGIN_TASK_CONTEXT_VIEWS]
    for entity in entities:
        lines.extend(tasknotes_context_view(entity) if kind == "tasknotesKanban" else bases_kanban_context_view(entity))
    lines.append(END_TASK_CONTEXT_VIEWS)
    return lines


def sync_task_context_views(text: str, entities: list[str], *, drop_epic_views: bool = False) -> str:
    lines = remove_marked_block(text.splitlines(), BEGIN_TASK_CONTEXT_VIEWS, END_TASK_CONTEXT_VIEWS)
    try:
        views_index = lines.index("views:")
    except ValueError:
        return text

    prefix = lines[: views_index + 1]
    body = lines[views_index + 1 :]
    epic_suffix: list[str] = []
    if BEGIN_EPIC_VIEWS in body and END_EPIC_VIEWS in body:
        begin = body.index(BEGIN_EPIC_VIEWS)
        end = body.index(END_EPIC_VIEWS, begin) + 1
        epic_suffix = body[begin:end]
        body = body[:begin] + body[end:]
        if drop_epic_views:
            epic_suffix = []

    blocks, loose = split_base_view_blocks(body)
    kind = task_context_view_kind(blocks)
    if kind is None:
        return text

    wanted = set(entities)
    kept_blocks: list[list[str]] = []
    for block in blocks:
        context_entity = task_context_entity(block)
        if context_entity is not None:
            continue

        epic_entity = epic_context_entity(block)
        if epic_entity is not None:
            if not drop_epic_views and epic_entity in wanted:
                kept_blocks.append(block)
            continue

        kept_blocks.append(block)

    output = prefix[:]
    output.extend(loose)
    for block in kept_blocks:
        output.extend(block)
    if entities:
        output.extend(generated_task_context_views(kind, entities))
    output.extend(epic_suffix)
    return "\n".join(output).rstrip() + "\n"


def active_periods(day: dt.date) -> dict[str, str]:
    iso = day.isocalendar()
    quarter = ((day.month - 1) // 3) + 1
    return {
        "daily": day.isoformat(),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "monthly": f"{day.year}-{day.month:02d}",
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


def context_folder_note(status: str, content_schedules_enabled: bool = False, default_capture: bool = False) -> str:
    default_value = "true" if default_capture else "false"
    schedules = "content_schedules_enabled: true\n" if content_schedules_enabled else ""
    return f"""---
status: {status}
{schedules}context_registered: true
default_capture: {default_value}
---
"""


def entity_note_template(
    entity: str,
    *,
    status: str = "active",
    content_schedules_enabled: bool = False,
    default_capture: bool = False,
) -> str:
    default_value = "true" if default_capture else "false"
    schedules = "content_schedules_enabled: true\n" if content_schedules_enabled else ""
    return f"""---
status: {status}
{schedules}context_registered: true
default_capture: {default_value}
{managed_properties()}
---

## Identity

### Declaration

### Source Notes

## Momentum

### Rhythm

### Proof Sources
"""


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


def update_context_folder_note(existing: str, status: str, content_schedules_enabled: bool, default_capture: bool) -> str:
    lines, body = split_frontmatter(existing)
    desired = {
        "status": status,
        "context_registered": "true",
        "default_capture": "true" if default_capture else "false",
    }
    if content_schedules_enabled:
        desired["content_schedules_enabled"] = "true"
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        if ":" in line and not line.startswith(" "):
            key = line.split(":", 1)[0].strip()
            if key in {"context_type", "content_enabled"}:
                continue
            if key == "content_schedules_enabled" and not content_schedules_enabled:
                continue
            if key in desired:
                output.append(f"{key}: {desired[key]}")
                seen.add(key)
                continue
        output.append(line)
    for key in ["status", "content_schedules_enabled", "context_registered", "default_capture"]:
        if key not in seen:
            if key in desired:
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


def parse_feature_entities(value: str | None, entities: list[str], label: str) -> list[str]:
    selected = parse_entities(value) if value else []
    missing = [entity for entity in selected if entity not in entities]
    if missing:
        raise SystemExit(f"{label} context folders are not configured: {missing}")
    return selected


def parse_folder_templates(value: str | None, entities: list[str]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for item in [part.strip() for part in (value or "").split(",") if part.strip()]:
        if ":" not in item:
            raise SystemExit(f"folder template mapping must use CONTEXT_FOLDER:TEMPLATE: {item!r}")
        entity, template = (part.strip() for part in item.split(":", 1))
        if entity not in entities:
            raise SystemExit(f"folder template context folder is not configured: {entity}")
        if template not in {"personal-brand", "business"}:
            raise SystemExit(f"unsupported folder template: {template}")
        templates[entity] = template
    return templates


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
    parser = argparse.ArgumentParser(description="Bootstrap the context folder Obsidian layout.")
    parser.add_argument("--root", default=".", help="Vault root. Defaults to current directory.")
    parser.add_argument("--context-folders", dest="entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders.")
    parser.add_argument("--sub-vaults", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--entities", dest="entities", help=argparse.SUPPRESS)
    parser.add_argument("--active-context-folders", dest="active_entities", metavar="CONTEXT_FOLDERS", help="Comma-separated context folders to mark active in folder notes.")
    parser.add_argument("--active-sub-vaults", dest="active_entities", help=argparse.SUPPRESS)
    parser.add_argument("--active-entities", dest="active_entities", help=argparse.SUPPRESS)
    parser.add_argument("--blog-context-folders", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--social-content-context-folders", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--newsletter-context-folders", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--content-schedule-context-folders", metavar="CONTEXT_FOLDERS")
    parser.add_argument("--folder-templates", metavar="CONTEXT_FOLDER:TEMPLATE", help="Comma-separated creation-time physical folder templates.")
    parser.add_argument("--default-context-folder", dest="default_entity", metavar="CONTEXT_FOLDER", default="personal", help="Default capture context folder.")
    parser.add_argument("--default-sub-vault", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--default-entity", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--coding-agents", default="codex", help="Comma-separated coding agents: codex, claude, or codex,claude.")
    parser.add_argument("--date", help="Run date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--skip-install-vault-command", action="store_true", help="Skip installing ~/.local/bin/vault.")
    parser.add_argument("--skip-agent-symlinks", action="store_true", help="Skip root agent symlink setup.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    entities = parse_entities(args.entities)
    active_entities = parse_entities(args.active_entities) if args.active_entities else DEFAULT_ACTIVE_ENTITIES[:]
    default_entity = args.default_entity
    coding_agents = parse_coding_agents(args.coding_agents)
    context_features = {entity: set() for entity in entities}
    feature_args = {
        "blog": args.blog_context_folders,
        "social-content": args.social_content_context_folders,
        "newsletters": args.newsletter_context_folders,
    }
    for feature, value in feature_args.items():
        for entity in parse_feature_entities(value, entities, feature):
            context_features[entity].add(feature)
    content_schedule_entities = (
        parse_feature_entities(args.content_schedule_context_folders, entities, "content schedule")
        if args.content_schedule_context_folders is not None
        else []
    )
    folder_templates = parse_folder_templates(args.folder_templates, entities)

    if args.interactive:
        entities = parse_entities(prompt(",".join(entities), "Context folders"))
        active_entities = parse_entities(prompt(",".join(active_entities), "Active context folders"))
        for feature in sorted(CONTENT_FEATURES):
            current = [entity for entity in entities if feature in context_features[entity]]
            selected = parse_entities(prompt(",".join(current), f"{feature} context folders"))
            context_features = {
                entity: (features | {feature}) if entity in selected else (features - {feature})
                for entity, features in context_features.items()
            }
        content_schedule_entities = parse_entities(prompt(",".join(content_schedule_entities), "Content schedule context folders"))
        default_entity = prompt(default_entity, "Default capture context folder")
        coding_agents = parse_coding_agents(prompt(",".join(coding_agents), "Coding agents: codex, claude, or codex,claude"))

    if default_entity not in entities:
        raise SystemExit(f"default context folder {default_entity!r} is not in configured context folders: {entities}")
    missing_active = [entity for entity in active_entities if entity not in entities]
    if missing_active:
        raise SystemExit(f"active context folders are not in configured context folders: {missing_active}")
    for entity, features in context_features.items():
        unsupported = sorted(features - CONTENT_FEATURES)
        if unsupported:
            raise SystemExit(f"unsupported content features for {entity}: {unsupported}")

    root = Path(args.root).expanduser().resolve()
    bootstrap = Bootstrap(
        root=root,
        entities=entities,
        active_entities=active_entities,
        default_entity=default_entity,
        coding_agents=coding_agents,
        context_features=context_features,
        content_schedule_entities=content_schedule_entities,
        install_vault_command_enabled=not args.skip_install_vault_command,
        agent_symlinks_enabled=not args.skip_agent_symlinks,
        dry_run=args.dry_run,
        run_date=parse_date(args.date),
        folder_templates=folder_templates,
    )
    bootstrap.run()


if __name__ == "__main__":
    main()
