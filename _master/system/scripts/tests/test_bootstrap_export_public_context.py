#!/usr/bin/env python3
"""Tests for public context folder bootstrap export."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from bootstrap_export import BootstrapExporter  # noqa: E402


class PublicContextExportTests(unittest.TestCase):
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
            source_context = root / "business"
            (source_context / "_obsidian/content").mkdir(parents=True)
            (source_context / "_obsidian/content" / "content-cadence.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source_context / "business.md").write_text(
                """---
status: active
context_type: business
content_enabled: true
---
# business

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
                        "source": "business",
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


if __name__ == "__main__":
    unittest.main()
