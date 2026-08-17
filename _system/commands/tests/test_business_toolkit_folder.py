#!/usr/bin/env python3
"""Context-folder creation tests for core-first capabilities and physical packs."""

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


class RecordingBootstrap:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls.append(kwargs)

    def run(self) -> None:
        root = self.kwargs["root"]
        for context in self.kwargs["entities"]:
            for relative in ("attachments", "bases", "epics", "projects", "tasks/archive"):
                (root / context / "_obsidian" / relative).mkdir(parents=True, exist_ok=True)
        for context, features in self.kwargs["context_features"].items():
            for feature in features:
                for relative in folder.FEATURE_DIRECTORIES[feature]:
                    (root / context / relative).mkdir(parents=True, exist_ok=True)


class ContextFolderCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        RecordingBootstrap.calls.clear()

    def fixture(self, root: Path) -> types.SimpleNamespace:
        shutil.copytree(VAULT_ROOT / PACK_RELATIVE, root / PACK_RELATIVE)
        shutil.copytree(
            VAULT_ROOT / "_system/bootstrap/templates/context-folders/personal-brand",
            root / "_system/bootstrap/templates/context-folders/personal-brand",
        )
        personal = root / "personal"
        personal.mkdir(parents=True)
        (personal / "personal.md").write_text(
            "---\nstatus: active\ncontext_registered: true\ndefault_capture: true\n---\n",
            encoding="utf-8",
        )
        templater = root / ".obsidian/plugins/templater-obsidian/data.json"
        templater.parent.mkdir(parents=True)
        templater.write_text(json.dumps({"folder_templates": []}), encoding="utf-8")
        return types.SimpleNamespace(Bootstrap=RecordingBootstrap, parse_date=lambda _value: None)

    def create(self, root: Path, bootstrap_module: object, args: list[str], *, register: bool = False) -> None:
        with (
            patch.object(folder, "resolve_vault_root", return_value=root),
            patch.object(folder, "load_bootstrap", return_value=bootstrap_module),
        ):
            folder.create_main(args, register_mode=register)

    def test_core_only_and_each_independent_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            bootstrap_module = self.fixture(root)
            cases = [
                ("core", [], set()),
                ("blogger", ["--blog"], {"blog"}),
                ("social", ["--social-content"], {"social-content"}),
                ("letters", ["--newsletters"], {"newsletters"}),
            ]
            for name, flags, expected in cases:
                self.create(root, bootstrap_module, ["-n", name, "-s", "active", *flags])
                call = RecordingBootstrap.calls[-1]
                self.assertEqual(call["context_features"][name], expected)
                self.assertTrue((root / name / "_obsidian/attachments").is_dir())
            self.assertFalse((root / "core/_obsidian/content").exists())
            self.assertTrue((root / "blogger/_obsidian/content/items/blog-posts").is_dir())
            self.assertFalse((root / "blogger/_obsidian/content-schedules").exists())

    def test_combined_capabilities_schedule_and_minimal_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            bootstrap_module = self.fixture(root)
            self.create(
                root,
                bootstrap_module,
                ["-n", "creator", "-s", "active", "--blog", "--social-content", "--newsletters", "--content-schedules"],
            )
            call = RecordingBootstrap.calls[-1]
            self.assertEqual(call["context_features"]["creator"], {"blog", "social-content", "newsletters"})
            self.assertIn("creator", call["content_schedule_entities"])
            note = (root / "creator/creator.md").read_text(encoding="utf-8")
            self.assertIn("content_schedules_enabled: true", note)
            self.assertNotIn("content_enabled", note)
            self.assertNotIn("context_type", note)

    def test_both_physical_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            bootstrap_module = self.fixture(root)
            self.create(root, bootstrap_module, ["-n", "creator", "-s", "active", "--folder-template", "personal-brand"])
            self.create(root, bootstrap_module, ["-n", "studio", "-s", "active", "--folder-template", "business"])
            for relative in ("brand", "audience", "offers", "products", "writing", "media", "relationships"):
                self.assertTrue((root / "creator" / relative).is_dir())
            self.assertTrue((root / "studio/company/.gitkeep").is_file())
            self.assertTrue((root / "studio/_obsidian/business-toolkit.json").is_file())

    def test_registration_adds_capabilities_but_rejects_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            bootstrap_module = self.fixture(root)
            existing = root / "existing"
            existing.mkdir()
            (existing / "existing.md").write_text("---\nstatus: active\ncontext_registered: true\n---\n", encoding="utf-8")
            self.create(root, bootstrap_module, ["existing", "--blog"], register=True)
            self.assertTrue((existing / "_obsidian/content/items/blog-posts").is_dir())
            with self.assertRaises(SystemExit):
                self.create(root, bootstrap_module, ["existing", "--folder-template", "business"], register=True)

    def test_removed_flags_fail_with_replacement_guidance(self) -> None:
        for flag in ("--context-type", "--content-enabled"):
            with self.subTest(flag=flag), self.assertRaisesRegex(SystemExit, "independent capability flags"):
                folder.main(["-n", "legacy", "-s", "active", flag])


if __name__ == "__main__":
    unittest.main()
