#!/usr/bin/env python3
"""Tests for the core-first context-frontmatter upgrade migration."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


VAULT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION = VAULT_ROOT / "_system/migrations/001-core-first-context-features.py"
SPEC = importlib.util.spec_from_file_location("context_features_migration", MIGRATION)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class ContextFeaturesMigrationTests(unittest.TestCase):
    def run_migration(self, root: Path, report: Path, mode: str) -> None:
        with patch.object(sys, "argv", [str(MIGRATION), "--root", str(root), "--report", str(report), mode]):
            self.assertEqual(migration.main(), 0)

    def test_apply_maps_true_to_schedules_removes_false_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, enabled in (("enabled", "true"), ("plain", "false")):
                context = root / name
                context.mkdir()
                (context / f"{name}.md").write_text(
                    f"---\nstatus: active\ncontext_type: business\ncontent_enabled: {enabled}\n---\n\nBody\n",
                    encoding="utf-8",
                )
            first_report = root / "first.json"
            second_report = root / "second.json"
            self.run_migration(root, first_report, "--apply")
            enabled_text = (root / "enabled/enabled.md").read_text(encoding="utf-8")
            plain_text = (root / "plain/plain.md").read_text(encoding="utf-8")
            self.assertIn("content_schedules_enabled: true", enabled_text)
            self.assertNotIn("context_type", enabled_text + plain_text)
            self.assertNotIn("content_enabled", enabled_text + plain_text)
            self.run_migration(root, second_report, "--apply")
            self.assertEqual(json.loads(second_report.read_text(encoding="utf-8"))["changed_count"], 0)

    def test_dry_run_reports_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "legacy"
            context.mkdir()
            note = context / "legacy.md"
            original = "---\nstatus: active\ncontext_type: personal\ncontent_enabled: true\n---\n"
            note.write_text(original, encoding="utf-8")
            report = root / "report.json"
            self.run_migration(root, report, "--dry-run")
            self.assertEqual(note.read_text(encoding="utf-8"), original)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["changed_count"], 1)


if __name__ == "__main__":
    unittest.main()
