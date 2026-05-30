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


if __name__ == "__main__":
    unittest.main()
