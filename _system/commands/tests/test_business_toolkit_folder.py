#!/usr/bin/env python3
"""Context-folder creation integration tests for the business toolkit."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import folder  # noqa: E402
from business_toolkit import PACK_RELATIVE  # noqa: E402


class NoOpBootstrap:
    def __init__(self, **_kwargs):
        pass

    def run(self) -> None:
        pass


class BusinessToolkitFolderTests(unittest.TestCase):
    def test_business_context_defaults_exclusions_and_opt_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            shutil.copytree(VAULT_ROOT / PACK_RELATIVE, root / PACK_RELATIVE)
            personal = root / "personal"
            personal.mkdir(parents=True)
            (personal / "personal.md").write_text(
                "---\nstatus: active\ncontext_type: personal\ncontext_registered: true\n---\n",
                encoding="utf-8",
            )
            templater = root / ".obsidian/plugins/templater-obsidian/data.json"
            templater.parent.mkdir(parents=True)
            templater.write_text(
                json.dumps(
                    {
                        "trigger_on_file_creation": False,
                        "enable_folder_templates": True,
                        "folder_templates": [],
                    }
                ),
                encoding="utf-8",
            )
            bootstrap_module = types.SimpleNamespace(
                Bootstrap=NoOpBootstrap,
                parse_date=lambda _value: None,
            )

            with (
                patch.object(folder, "resolve_vault_root", return_value=root),
                patch.object(folder, "load_bootstrap", return_value=bootstrap_module),
            ):
                folder.create_main(["-n", "studio", "-s", "active"], register_mode=False)
                folder.create_main(
                    ["-n", "lean-studio", "-s", "active", "--toolkit-exclude", "gtm"],
                    register_mode=False,
                )
                folder.create_main(
                    ["-n", "plain-studio", "-s", "active", "--no-business-toolkit"],
                    register_mode=False,
                )

            full = json.loads(
                (root / "studio/_obsidian/business-toolkit.json").read_text(encoding="utf-8")
            )
            lean = json.loads(
                (root / "lean-studio/_obsidian/business-toolkit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(full["components"]), 16)
            self.assertFalse(any(item.startswith("gtm.") for item in lean["components"]))
            self.assertFalse((root / "plain-studio/_obsidian/business-toolkit.json").exists())
            for name in ("studio", "lean-studio", "plain-studio"):
                self.assertTrue((root / name / "company/.gitkeep").is_file())
                self.assertTrue((root / name / "gtm/campaigns/.gitkeep").is_file())
            self.assertFalse((root / "lean-studio/_obsidian/templates/business-toolkit/gtm").exists())

    def test_register_does_not_backfill_ordinary_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            shutil.copytree(VAULT_ROOT / PACK_RELATIVE, root / PACK_RELATIVE)
            for name, context_type in (("personal", "personal"), ("existing", "business")):
                context = root / name
                context.mkdir(parents=True)
                (context / f"{name}.md").write_text(
                    f"---\nstatus: active\ncontext_type: {context_type}\ncontext_registered: true\n---\n",
                    encoding="utf-8",
                )
            templater = root / ".obsidian/plugins/templater-obsidian/data.json"
            templater.parent.mkdir(parents=True)
            templater.write_text(json.dumps({"folder_templates": []}), encoding="utf-8")
            bootstrap_module = types.SimpleNamespace(Bootstrap=NoOpBootstrap, parse_date=lambda _value: None)
            with (
                patch.object(folder, "resolve_vault_root", return_value=root),
                patch.object(folder, "load_bootstrap", return_value=bootstrap_module),
            ):
                folder.create_main(["existing"], register_mode=True)
            self.assertFalse((root / "existing/company").exists())
            self.assertTrue((root / "existing/_obsidian/templates/business-toolkit").is_dir())


if __name__ == "__main__":
    unittest.main()
