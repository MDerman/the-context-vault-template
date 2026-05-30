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
    def test_context_folder_note_and_declaration_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            source_context = root / "business"
            (source_context / "DECLARATION").mkdir(parents=True)
            (source_context / "DECLARATION" / "content-cadence.json").write_text(
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
""",
                encoding="utf-8",
            )
            (source_context / "DECLARATION.md").write_text(
                """---
type: declaration
entity: business
entity_type: company
---
# business Declaration

Private declaration intro should not be exported.

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
            self.assertFalse((export_root / "business" / "HOME.md").exists())

            declaration = (export_root / "business" / "DECLARATION.md").read_text(
                encoding="utf-8",
            )
            self.assertIn("entity: business", declaration)
            self.assertIn("# business Declaration", declaration)
            self.assertIn("## Identity", declaration)
            self.assertIn("## Momentum", declaration)
            self.assertNotIn("### Purpose", declaration)
            self.assertNotIn("Private declaration intro", declaration)
            self.assertNotIn("Private identity body", declaration)
            self.assertNotIn("Private purpose detail", declaration)

            self.assertFalse((export_root / "business" / "DECLARATION").exists())


if __name__ == "__main__":
    unittest.main()
