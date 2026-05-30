#!/usr/bin/env python3
"""Tests for legacy context folder note migration."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "2026_05_30_context_folder_notes.py"
SPEC = importlib.util.spec_from_file_location("context_folder_notes_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migration
SPEC.loader.exec_module(migration)


class ContextFolderNotesMigrationTests(unittest.TestCase):
    def test_moves_legacy_home_to_inside_folder_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "business"
            context.mkdir()
            (context / "HOME.md").write_text("---\nstatus: active\n---\n# business\n", encoding="utf-8")

            result = migration.run(root, apply=True)

            self.assertEqual(result["moved_count"], 1)
            self.assertFalse((context / "HOME.md").exists())
            self.assertTrue((context / "business.md").exists())
            self.assertIn("# business", (context / "business.md").read_text(encoding="utf-8"))

    def test_reports_conflict_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "business"
            context.mkdir()
            (context / "HOME.md").write_text("old\n", encoding="utf-8")
            (context / "business.md").write_text("new\n", encoding="utf-8")

            result = migration.run(root, apply=True)

            self.assertEqual(result["moved_count"], 0)
            self.assertEqual(result["conflict_count"], 1)
            self.assertEqual((context / "HOME.md").read_text(encoding="utf-8"), "old\n")
            self.assertEqual((context / "business.md").read_text(encoding="utf-8"), "new\n")

    def test_moves_legacy_operating_sections_to_empty_entity_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "business"
            context.mkdir()
            (context / "business.md").write_text(
                "---\nstatus: active\ncontext_type: business\n---\n# business\n## Identity\n\n## Momentum\n",
                encoding="utf-8",
            )
            legacy_note = context / ("DECLARATION" + ".md")
            legacy_note.write_text(
                """---
generated: true
managed_by: "managed-by: test"
---
# business

## Identity

Durable identity.

## Momentum

Operating rhythm.
""",
                encoding="utf-8",
            )

            result = migration.run(root, apply=True)

            self.assertEqual(result["section_move_count"], 2)
            entity_note = (context / "business.md").read_text(encoding="utf-8")
            self.assertIn("Durable identity.", entity_note)
            self.assertIn("Operating rhythm.", entity_note)
            self.assertFalse(legacy_note.exists())

    def test_reports_section_conflict_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "business"
            context.mkdir()
            (context / "business.md").write_text(
                "---\nstatus: active\ncontext_type: business\n---\n# business\n## Identity\n\nCurrent identity.\n",
                encoding="utf-8",
            )
            legacy_note = context / ("DECLARATION" + ".md")
            legacy_note.write_text("# business\n\n## Identity\n\nOld identity.\n", encoding="utf-8")

            result = migration.run(root, apply=True)

            self.assertEqual(result["conflict_count"], 1)
            entity_note = (context / "business.md").read_text(encoding="utf-8")
            self.assertIn("Current identity.", entity_note)
            self.assertNotIn("Old identity.", entity_note)
            self.assertTrue(legacy_note.exists())

    def test_moves_cadence_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "business"
            old_dir = context / "DECLARATION"
            old_dir.mkdir(parents=True)
            (context / "business.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
            (old_dir / "content-cadence.json").write_text('{"enabled": true}\n', encoding="utf-8")

            result = migration.run(root, apply=True)

            self.assertEqual(result["cadence_move_count"], 1)
            self.assertTrue((context / "_obsidian/content/content-cadence.json").exists())

    def test_renames_support_folder_and_rewrites_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "personal-brand"
            old_dir = context / "DECLARATION"
            old_dir.mkdir(parents=True)
            (context / "personal-brand.md").write_text(
                "---\nstatus: active\n---\n[[" + "DECLARATION" + "/01-brand]]\n",
                encoding="utf-8",
            )
            (old_dir / "01-brand.md").write_text("brand\n", encoding="utf-8")

            result = migration.run(root, apply=True)

            self.assertEqual(result["support_folder_move_count"], 1)
            self.assertTrue((context / "brand-strategy-and-vision/01-brand.md").exists())
            text = (context / "personal-brand.md").read_text(encoding="utf-8")
            self.assertIn("[[brand-strategy-and-vision/01-brand]]", text)


if __name__ == "__main__":
    unittest.main()
