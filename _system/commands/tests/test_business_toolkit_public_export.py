#!/usr/bin/env python3
"""Public-export integration tests for the business toolkit."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from bootstrap_export import BootstrapExporter  # noqa: E402


class BusinessToolkitPublicExportTests(unittest.TestCase):
    def test_pack_installs_in_public_business_without_private_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            export_root = Path(tmp) / "public"
            shutil.copytree(
                VAULT_ROOT / "_library/business_toolkit",
                root / "_library/business_toolkit",
            )
            shutil.copytree(
                VAULT_ROOT / "_system/bootstrap/templates/context-folders/business",
                export_root / "_system/bootstrap/templates/context-folders/business",
            )
            source_context = root / "private-company"
            source_context.mkdir(parents=True)
            (source_context / "private-company.md").write_text(
                "---\nstatus: active\ncontext_registered: true\n---\n",
                encoding="utf-8",
            )
            export_context = export_root / "business"
            export_context.mkdir(parents=True)
            (export_context / "business.md").write_text(
                "---\nstatus: active\ncontext_registered: true\n---\n",
                encoding="utf-8",
            )
            commands = export_root / "_system/commands"
            commands.mkdir(parents=True)
            shutil.copy2(SCRIPT_DIR / "business_toolkit.py", commands / "business_toolkit.py")
            shutil.copy2(SCRIPT_DIR / "script_utils.py", commands / "script_utils.py")
            templater = export_root / ".obsidian/plugins/templater-obsidian/data.json"
            templater.parent.mkdir(parents=True)
            templater.write_text(
                json.dumps(
                    {
                        "enable_folder_templates": True,
                        "folder_templates": [
                            {
                                "folder": "private-company/meetings",
                                "template": "private-company/template.md",
                            },
                            {"folder": "_system/inbox", "template": "_system/template.md"},
                        ],
                        "ignore_folders_on_creation": [
                            {"folder": "private-company/_obsidian/templates/business-toolkit"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            for profile in (".obsidian", ".obsidian-mobile"):
                iconize = export_root / profile / "plugins/obsidian-icon-folder/data.json"
                iconize.parent.mkdir(parents=True, exist_ok=True)
                iconize.write_text(
                    json.dumps(
                        {
                            "settings": {
                                "preserve": True,
                                "rules": [{"icon": "⭐", "rule": "^private-company/meetings"}],
                            },
                            "private-company/meetings": "⭐",
                        }
                    ),
                    encoding="utf-8",
                )
            config = {
                "export_root": str(export_root),
                "copy_obsidian": "exact",
                "context_folders": [{"source": "private-company", "target": "business", "folder_template": "business"}],
                "library_include_paths": ["business_toolkit"],
            }
            exporter = BootstrapExporter(
                root=root,
                config=config,
                export_root=export_root,
                force=True,
                dry_run=False,
            )

            exporter.create_library_and_wiki()
            exporter.install_public_folder_templates()
            exporter.sanitize_public_templater_rules()
            exporter.sanitize_public_iconize_paths()

            state = json.loads(
                (export_root / "business/_obsidian/business-toolkit.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (
                    export_root
                    / "_system/bootstrap/templates/context-folders/business/.business-toolkit.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(len(state["components"]), len(manifest["components"]))
            for component in manifest["components"]:
                self.assertTrue((export_root / "business" / component["destination"]).is_file())
            rules = json.loads(templater.read_text(encoding="utf-8"))["folder_templates"]
            rendered = json.dumps(rules)
            self.assertNotIn("private-company", rendered)
            self.assertIn("business/meetings", rendered)
            self.assertIn("_system/inbox", rendered)
            ignored = json.loads(templater.read_text(encoding="utf-8"))[
                "ignore_folders_on_creation"
            ]
            self.assertNotIn("private-company", json.dumps(ignored))
            self.assertIn("business/_obsidian/templates/business-toolkit", json.dumps(ignored))
            self.assertTrue((export_root / "business/company/.gitkeep").is_file())
            for profile in (".obsidian", ".obsidian-mobile"):
                icons = json.loads(
                    (export_root / profile / "plugins/obsidian-icon-folder/data.json").read_text(encoding="utf-8")
                )
                self.assertNotIn("private-company/meetings", icons)
                self.assertEqual(icons["business/meetings/1-on-1s"], "📋")
                self.assertTrue(icons["settings"]["preserve"])
                self.assertEqual(icons["settings"]["rules"], [])


if __name__ == "__main__":
    unittest.main()
