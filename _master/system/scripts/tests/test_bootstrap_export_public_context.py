#!/usr/bin/env python3
"""Tests for public context folder bootstrap export."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
import shutil


SCRIPT_DIR = Path(__file__).resolve().parents[1]
BOOTSTRAP_DIR = SCRIPT_DIR.parent / "bootstrap"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BOOTSTRAP_DIR))

from bootstrap_export import BootstrapExporter  # noqa: E402
from bootstrap_vault import sync_task_context_views  # noqa: E402
from folder import has_content_structure  # noqa: E402


class PublicContextExportTests(unittest.TestCase):
    def test_managed_dependency_projection_is_not_exported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            config_dir = root / "_master/system/config"
            projection = root / "_master/agents/skills/agent-canvas"
            checkout = Path(tmp) / "checkout/skills/agent-canvas"
            config_dir.mkdir(parents=True)
            checkout.mkdir(parents=True)
            (checkout / "SKILL.md").write_text("external\n")
            projection.parent.mkdir(parents=True)
            projection.symlink_to(checkout)
            (config_dir / "deps.json").write_text(
                '{"repos":[{"projections":[{"target":"_master/agents/skills/agent-canvas","managed":true}]}]}\n'
            )
            config = {"export_root": str(export_root), "copy_obsidian": "exact"}
            exporter = BootstrapExporter(root=root, config=config, export_root=export_root, force=True, dry_run=False)
            exporter.copy_master_or_shared("_master")
            self.assertFalse((export_root / "_master/agents/skills/agent-canvas").exists())

    def test_patched_simple_folder_note_bundle_is_exported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            patched = root / ".obsidian" / "plugins" / "simple-folder-note"
            third_party = root / ".obsidian" / "plugins" / "ordinary-plugin"
            patched.mkdir(parents=True)
            third_party.mkdir(parents=True)
            (patched / "manifest.json").write_text('{"id":"simple-folder-note"}\n', encoding="utf-8")
            (patched / "main.js").write_text("module.exports = {};\n", encoding="utf-8")
            (third_party / "manifest.json").write_text('{"id":"ordinary-plugin"}\n', encoding="utf-8")
            (third_party / "main.js").write_text("module.exports = {};\n", encoding="utf-8")
            config = {
                "export_root": str(export_root),
                "copy_obsidian": "exact",
                "obsidian_plugin_exact_copy_plugins": ["simple-folder-note"],
                "obsidian_plugin_public_files": ["manifest.json", "styles.css"],
            }

            exporter = BootstrapExporter(
                root=root,
                config=config,
                export_root=export_root,
                force=True,
                dry_run=False,
            )
            exporter.copy_obsidian()

            self.assertTrue((export_root / ".obsidian/plugins/simple-folder-note/main.js").exists())
            self.assertTrue((export_root / ".obsidian/plugins/simple-folder-note/manifest.json").exists())
            self.assertFalse((export_root / ".obsidian/plugins/ordinary-plugin/main.js").exists())
            self.assertTrue((export_root / ".obsidian/plugins/ordinary-plugin/manifest.json").exists())

    def test_context_folder_note_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            source_context = root / "impression"
            (source_context / "_obsidian/content").mkdir(parents=True)
            (source_context / "_obsidian/content" / "content-cadence.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source_context / "impression.md").write_text(
                """---
status: active
context_type: business
content_enabled: true
---
# impression

## Start Here

Private routing map should not be exported.

## Identity

Private identity body should not be exported.

### Purpose

Private purpose detail should not be exported.

## Momentum
""",
                encoding="utf-8",
            )
            config = {
                "export_root": str(export_root),
                "context_folders": [
                    {
                        "source": "impression",
                        "target": "business",
                        "public_home_description": [
                            "This is your business home.",
                            "Use it for tasks, projects, team notes, leads, resources, and operating docs.",
                        ],
                    }
                ],
                "copy_obsidian": "exact",
            }

            exporter = BootstrapExporter(
                root=root,
                config=config,
                export_root=export_root,
                force=True,
                dry_run=False,
            )
            exporter.copy_context_folders()

            context_note = (export_root / "business" / "business.md").read_text(encoding="utf-8")
            self.assertIn("status: active", context_note)
            self.assertIn("# business", context_note)
            self.assertIn("This is your business home.", context_note)
            self.assertNotIn("Start Here", context_note)
            self.assertNotIn("Private routing map", context_note)
            self.assertIn("## Identity", context_note)
            self.assertIn("## Momentum", context_note)
            self.assertNotIn("### Purpose", context_note)
            self.assertNotIn("Private identity body", context_note)
            self.assertNotIn("Private purpose detail", context_note)
            self.assertFalse((export_root / "business" / "HOME.md").exists())
            self.assertFalse((export_root / "business" / ("DECLARATION" + ".md")).exists())
            self.assertFalse((export_root / "business" / "DECLARATION").exists())

    def test_private_export_drop_lines_are_removed_from_exported_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            source_context = root / "personal"
            template = source_context / "_obsidian/templates/periodic/daily-template.md"
            template.parent.mkdir(parents=True)
            (source_context / "personal.md").write_text(
                """---
status: active
context_type: personal
content_enabled: false
default_capture: true
---
# personal
""",
                encoding="utf-8",
            )
            template.write_text(
                """## Links
- [[personal/Private Note|Private Note]] %% private-export: drop-line %%
- [[personal#Momentum|Personal Momentum]]
""",
                encoding="utf-8",
            )
            config = {
                "export_root": str(export_root),
                "context_folders": [
                    {"source": "personal", "target": "personal"},
                ],
                "copy_obsidian": "exact",
                "text_rewrite_suffixes": [".md"],
            }

            exporter = BootstrapExporter(
                root=root,
                config=config,
                export_root=export_root,
                force=True,
                dry_run=False,
            )
            exporter.copy_context_folders()

            exported_template = (
                export_root / "personal/_obsidian/templates/periodic/daily-template.md"
            ).read_text(encoding="utf-8")
            self.assertNotIn("Private Note", exported_template)
            self.assertNotIn("private-export: drop-line", exported_template)
            self.assertIn("[[personal#Momentum|Personal Momentum]]", exported_template)

    def test_personal_daily_what_to_do_link_is_removed_from_exported_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            source_context = root / "personal"
            template = source_context / "_obsidian/templates/periodic/daily-template.md"
            template.parent.mkdir(parents=True)
            (source_context / "personal.md").write_text(
                """---
status: active
context_type: personal
content_enabled: false
default_capture: true
---
# personal
""",
                encoding="utf-8",
            )
            template.write_text(
                """## Links
- [[personal/Daily What To Do|Daily What To Do]]
- [[personal#Momentum|Personal Momentum]]
""",
                encoding="utf-8",
            )
            config = {
                "export_root": str(export_root),
                "context_folders": [
                    {"source": "personal", "target": "personal"},
                ],
                "copy_obsidian": "exact",
                "text_rewrite_suffixes": [".md"],
            }

            exporter = BootstrapExporter(
                root=root,
                config=config,
                export_root=export_root,
                force=True,
                dry_run=False,
            )
            exporter.copy_context_folders()

            exported_template = (
                export_root / "personal/_obsidian/templates/periodic/daily-template.md"
            ).read_text(encoding="utf-8")
            self.assertNotIn("Daily What To Do", exported_template)
            self.assertIn("[[personal#Momentum|Personal Momentum]]", exported_template)

    def test_task_context_views_are_regenerated_for_public_contexts(self) -> None:
        source_brand = "matt" + "-derman"
        source_business = "im" + "pression"
        source = f"""filters:
  and:
    - file.hasTag("task")
views:
  - type: tasknotesKanban
    name: Open Tasks
    filters:
      and:
        - status != "done"
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Matt Brand
    filters:
      and:
        - file.inFolder("{source_brand}/_obsidian/tasks")
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Impression
    filters:
      and:
        - file.inFolder("{source_business}/_obsidian/tasks")
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Dev
    filters:
      and:
        - file.inFolder("dev/_obsidian/tasks")
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Impression - Growth
    filters:
      and:
        - epic == link("{source_business}/_obsidian/epics/Growth")
"""

        updated = sync_task_context_views(
            source,
            ["personal", "personal-brand", "business"],
            drop_epic_views=True,
        )

        self.assertIn('file.inFolder("personal/_obsidian/tasks")', updated)
        self.assertIn('file.inFolder("personal-brand/_obsidian/tasks")', updated)
        self.assertIn('file.inFolder("business/_obsidian/tasks")', updated)
        self.assertIn('name: "Personal Brand"', updated)
        self.assertNotIn(f"{source_brand}/_obsidian", updated)
        self.assertNotIn(f"{source_business}/_obsidian", updated)
        self.assertNotIn("dev/_obsidian", updated)
        self.assertNotIn("Matt Brand", updated)
        self.assertNotIn("Impression - Growth", updated)

    def test_public_export_regenerates_master_bases_for_target_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            source_brand = "matt" + "-derman"
            source_business = "im" + "pression"
            source_bootstrap = BOOTSTRAP_DIR / "bootstrap_vault.py"
            target_bootstrap = root / "_master/system/bootstrap/bootstrap_vault.py"
            target_bootstrap.parent.mkdir(parents=True)
            shutil.copy2(source_bootstrap, target_bootstrap)

            bases = root / "_master/_obsidian/bases"
            bases.mkdir(parents=True)
            (bases / "tasks-kanban-v1.base").write_text(
                f"""filters:
  and:
    - file.hasTag("task")
views:
  - type: tasknotesKanban
    name: Open Tasks
    filters:
      and:
        - status != "done"
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Matt Brand
    filters:
      and:
        - file.inFolder("{source_brand}/_obsidian/tasks")
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Impression
    filters:
      and:
        - file.inFolder("{source_business}/_obsidian/tasks")
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Dev
    filters:
      and:
        - file.inFolder("dev/_obsidian/tasks")
    groupBy:
      property: status
      direction: ASC
  - type: tasknotesKanban
    name: Impression - Growth
    filters:
      and:
        - epic == link("{source_business}/_obsidian/epics/Growth")
""",
                encoding="utf-8",
            )
            (bases / "tasks-kanban.base").write_text(
                f"""filters:
  and:
    - file.hasTag("task")
views:
  - type: kanban-view
    name: Open Tasks
    filters:
      and:
        - status != "done"
    groupByProperty: status
  - type: kanban-view
    name: Impression
    filters:
      and:
        - file.inFolder("{source_business}/_obsidian/tasks")
    groupByProperty: status
""",
                encoding="utf-8",
            )

            for name, context_type, content_enabled in [
                ("personal", "personal", False),
                (source_brand, "personal-brand", True),
                (source_business, "business", True),
                ("dev", "business", False),
            ]:
                context_root = root / name
                (context_root / "_obsidian/bases").mkdir(parents=True)
                if content_enabled:
                    (context_root / "_obsidian/content").mkdir(parents=True)
                (context_root / f"{name}.md").write_text(
                    f"""---
status: active
context_type: {context_type}
content_enabled: {"true" if content_enabled else "false"}
default_capture: {"true" if name == "personal" else "false"}
---
""",
                    encoding="utf-8",
                )

            config = {
                "export_root": str(export_root),
                "context_folders": [
                    {"source": "personal", "target": "personal"},
                    {"source": source_brand, "target": "personal-brand"},
                    {"source": source_business, "target": "business"},
                ],
                "copy_obsidian": "exact",
                "text_rewrite_suffixes": [".base", ".md", ".py"],
            }

            exporter = BootstrapExporter(
                root=root,
                config=config,
                export_root=export_root,
                force=True,
                dry_run=False,
            )
            exporter.prepare_export_root()
            exporter.copy_master_or_shared("_master")
            exporter.copy_context_folders()
            exporter.regenerate_public_bases()
            exporter.validate_public_base_contexts()

            kanban_v1 = (export_root / "_master/_obsidian/bases/tasks-kanban-v1.base").read_text(encoding="utf-8")
            self.assertIn('file.inFolder("personal/_obsidian/tasks")', kanban_v1)
            self.assertIn('file.inFolder("personal-brand/_obsidian/tasks")', kanban_v1)
            self.assertIn('file.inFolder("business/_obsidian/tasks")', kanban_v1)
            self.assertNotIn(f"{source_brand}/_obsidian", kanban_v1)
            self.assertNotIn(f"{source_business}/_obsidian", kanban_v1)
            self.assertNotIn("dev/_obsidian", kanban_v1)
            self.assertNotIn("Matt Brand", kanban_v1)
            self.assertNotIn("Impression - Growth", kanban_v1)

            content_calendar = (export_root / "_master/_obsidian/bases/content-calendar.base").read_text(encoding="utf-8")
            self.assertIn('file.inFolder("personal-brand/_obsidian/content/items")', content_calendar)
            self.assertIn('file.inFolder("business/_obsidian/content/items")', content_calendar)
            self.assertIn('entity == "personal-brand"', content_calendar)
            self.assertIn('entity == "business"', content_calendar)
            self.assertNotIn(f"{source_brand}/_obsidian", content_calendar)
            self.assertNotIn(f"{source_business}/_obsidian", content_calendar)

    def test_existing_content_folder_counts_as_content_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context_root = Path(tmp) / "shared-context"
            (context_root / "_obsidian/content").mkdir(parents=True)

            self.assertTrue(has_content_structure(context_root))


if __name__ == "__main__":
    unittest.main()
