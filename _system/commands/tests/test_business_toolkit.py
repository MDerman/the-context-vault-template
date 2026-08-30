#!/usr/bin/env python3
"""Tests for the shared business-context toolkit installer."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from business_toolkit import (  # noqa: E402
    ICONIZE_RELATIVES,
    MANAGED_ICON,
    MANIFEST_NAME,
    PACK_RELATIVE,
    STATE_RELATIVE,
    TEMPLATER_RELATIVE,
    install_scaffold,
    load_pack,
    load_state,
    run_sync,
    run_unconfigure,
    select_components,
    sha256_file,
    sync_context,
)


class BusinessToolkitTests(unittest.TestCase):
    def make_root(self, tmp: str) -> Path:
        root = Path(tmp) / "vault"
        pack_source = VAULT_ROOT / PACK_RELATIVE
        shutil.copytree(pack_source, root / PACK_RELATIVE)
        context = root / "studio"
        context.mkdir(parents=True)
        (context / "studio.md").write_text(
            "---\nstatus: active\ncontext_registered: true\n---\n",
            encoding="utf-8",
        )
        templater = root / TEMPLATER_RELATIVE
        templater.parent.mkdir(parents=True)
        templater.write_text(
            json.dumps(
                {
                    "trigger_on_file_creation": False,
                    "enable_folder_templates": True,
                    "folder_templates": [
                        {"folder": "personal/journal", "template": "personal/template.md"}
                    ],
                    "unrelated_setting": "preserve-me",
                }
            ),
            encoding="utf-8",
        )
        for relative in ICONIZE_RELATIVES:
            iconize = root / relative
            iconize.parent.mkdir(parents=True)
            iconize.write_text(json.dumps({"settings": {"preserve": True}}), encoding="utf-8")
        return root

    def test_component_and_group_selection(self) -> None:
        _version, components = load_pack(VAULT_ROOT)
        meetings = select_components(components, saved=None, includes=["meetings"], excludes=[])
        self.assertEqual({item.group for item in meetings}, {"meetings"})
        without_gtm = select_components(components, saved=None, includes=[], excludes=["gtm"])
        self.assertNotIn("gtm", {item.group for item in without_gtm})
        with self.assertRaises(SystemExit):
            select_components(components, saved=None, includes=["does-not-exist"], excludes=[])

    def test_managed_templates_render_valid_frontmatter_and_runtime_values(self) -> None:
        _version, components = load_pack(VAULT_ROOT)
        for component in components:
            with self.subTest(component=component.id):
                source = (VAULT_ROOT / PACK_RELATIVE / component.source).read_text(
                    encoding="utf-8"
                )
                rendered = re.sub(r"<%\*[\s\S]*?-%>\n", "", source, count=1)
                rendered = rendered.replace("<% date %>", "2030-01-02")
                rendered = rendered.replace("<% tp.file.title %>", "Quarterly planning")
                rendered = re.sub(
                    r"<% defaultTitles\.has\(tp\.file\.title\) \? targetTitle : tp\.file\.title %>",
                    "Quarterly planning",
                    rendered,
                )

                self.assertTrue(rendered.startswith("---\n"))
                self.assertIn("\n---\n", rendered[4:])
                self.assertNotIn("<%", rendered)
                self.assertNotIn("\n***\n", rendered)
                self.assertNotIn("offer-template", rendered)
                self.assertNotIn("user-signal-template", rendered)
                self.assertNotIn("Old quick workout notes", rendered)
                if component.id != "skills.local":
                    self.assertIn("date: 2030-01-02", rendered)

    def test_manifest_rejects_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            manifest = root / PACK_RELATIVE / MANIFEST_NAME
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["components"][0]["destination"] = "../outside.md"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(SystemExit):
                load_pack(root)

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            output = StringIO()
            with redirect_stdout(output):
                result = sync_context(root, "studio", apply=False)
            self.assertGreater(result.changed, 0)
            self.assertIn("[dry-run]", output.getvalue())
            self.assertFalse((root / "studio/_obsidian/business-toolkit.json").exists())
            self.assertFalse((root / "studio/_obsidian/templates/business-toolkit").exists())
            self.assertFalse((root / "studio/meetings").exists())

    def test_apply_saves_profile_and_preserves_unrelated_templater_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            result = sync_context(root, "studio", excludes=["gtm"], apply=True, use_saved=False)
            self.assertFalse(result.conflicts)
            state = load_state(root, "studio")
            self.assertTrue(state["components"])
            self.assertFalse(any(item.startswith("gtm.") for item in state["components"]))
            rules_data = json.loads((root / TEMPLATER_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(rules_data["unrelated_setting"], "preserve-me")
            self.assertIn(
                {"folder": "personal/journal", "template": "personal/template.md"},
                rules_data["folder_templates"],
            )
            self.assertIn(
                {"folder": "studio/_obsidian/templates/business-toolkit"},
                rules_data["ignore_folders_on_creation"],
            )
            first_rules = rules_data["folder_templates"]
            sync_context(root, "studio", apply=True)
            second_rules = json.loads((root / TEMPLATER_RELATIVE).read_text(encoding="utf-8"))[
                "folder_templates"
            ]
            self.assertEqual(first_rules, second_rules)

    def test_drift_is_protected_and_force_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            sync_context(root, "studio", includes=["meetings.one-on-ones"], apply=True, use_saved=False)
            _version, components = load_pack(root)
            component = next(item for item in components if item.id == "meetings.one-on-ones")
            destination = root / "studio" / component.destination
            destination.write_text("local edit\n", encoding="utf-8")

            protected = sync_context(root, "studio", apply=True)
            self.assertTrue(protected.conflicts)
            self.assertEqual(destination.read_text(encoding="utf-8"), "local edit\n")

            forced = sync_context(root, "studio", apply=True, force=True)
            self.assertFalse(forced.conflicts)
            source = root / PACK_RELATIVE / component.source
            self.assertEqual(sha256_file(destination), sha256_file(source))

    def test_exclusion_removes_only_unchanged_managed_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            sync_context(root, "studio", includes=["meetings"], apply=True, use_saved=False)
            _version, components = load_pack(root)
            one_on_one = next(item for item in components if item.id == "meetings.one-on-ones")
            destination = root / "studio" / one_on_one.destination
            operating_folder = root / "studio" / one_on_one.folder
            operating_folder.mkdir(parents=True)
            (operating_folder / "real-note.md").write_text("keep\n", encoding="utf-8")

            result = sync_context(root, "studio", excludes=["meetings.one-on-ones"], apply=True)
            self.assertFalse(result.conflicts)
            self.assertFalse(destination.exists())
            self.assertTrue((operating_folder / "real-note.md").exists())
            rules = json.loads((root / TEMPLATER_RELATIVE).read_text(encoding="utf-8"))[
                "folder_templates"
            ]
            self.assertNotIn(f"studio/{one_on_one.folder.as_posix()}", {rule.get("folder") for rule in rules})

    def test_scaffold_creation_and_conservative_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            install_scaffold(root, "studio", apply=True)
            self.assertTrue((root / "studio/company/.gitkeep").is_file())
            self.assertTrue((root / "studio/gtm/campaigns/.gitkeep").is_file())
            self.assertFalse(list((root / "studio").rglob("README*.md")))
            self.assertFalse((root / "studio" / MANIFEST_NAME).exists())
            self.assertFalse((root / "studio/_obsidian/templates/business-toolkit").exists())

            shutil.rmtree(root / "studio/product")
            sync_context(root, "studio", includes=["product"], apply=True, use_saved=False)
            self.assertFalse((root / "studio/product").exists())

    def test_icons_are_managed_in_both_profiles_and_custom_drift_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            folder = root / "studio/meetings/1-on-1s"
            folder.mkdir(parents=True)
            sync_context(root, "studio", includes=["meetings.one-on-ones"], apply=True, use_saved=False)
            key = "studio/meetings/1-on-1s"
            for relative in ICONIZE_RELATIVES:
                data = json.loads((root / relative).read_text(encoding="utf-8"))
                self.assertEqual(data[key], MANAGED_ICON)
                self.assertTrue(data["settings"]["preserve"])

            desktop = root / ICONIZE_RELATIVES[0]
            data = json.loads(desktop.read_text(encoding="utf-8"))
            data[key] = "⭐"
            desktop.write_text(json.dumps(data), encoding="utf-8")
            protected = sync_context(root, "studio", apply=True)
            self.assertTrue(any("changed managed icon" in item for item in protected.conflicts))
            self.assertEqual(json.loads(desktop.read_text(encoding="utf-8"))[key], "⭐")
            sync_context(root, "studio", apply=True, force=True)
            self.assertEqual(json.loads(desktop.read_text(encoding="utf-8"))[key], MANAGED_ICON)

    def test_multi_context_apply_aborts_atomically_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            agency = root / "agency"
            agency.mkdir()
            (agency / "agency.md").write_text(
                "---\nstatus: active\ncontext_registered: true\n---\n",
                encoding="utf-8",
            )
            for context in ("studio", "agency"):
                sync_context(root, context, includes=["meetings.one-on-ones"], apply=True, use_saved=False)
            _version, components = load_pack(root)
            component = next(item for item in components if item.id == "meetings.one-on-ones")
            changed = root / "studio" / component.destination
            changed.write_text("local edit\n", encoding="utf-8")
            agency_state = (root / "agency" / STATE_RELATIVE).read_bytes()
            templater_state = (root / TEMPLATER_RELATIVE).read_bytes()

            exit_code = run_sync(
                root,
                ["studio", "agency"],
                includes=[],
                excludes=["meetings.one-on-ones"],
                apply=True,
                force=False,
                use_saved=False,
                allow_prompt=False,
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(changed.read_text(encoding="utf-8"), "local edit\n")
            self.assertEqual((root / "agency" / STATE_RELATIVE).read_bytes(), agency_state)
            self.assertEqual((root / TEMPLATER_RELATIVE).read_bytes(), templater_state)

    def test_unconfigure_removes_managed_state_but_keeps_operating_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            operating = root / "studio/meetings/1-on-1s"
            operating.mkdir(parents=True)
            sync_context(root, "studio", includes=["meetings.one-on-ones"], apply=True, use_saved=False)
            destination = root / "studio/_obsidian/templates/business-toolkit/meetings/one-on-one-template.md"
            self.assertTrue(destination.is_file())
            self.assertEqual(run_unconfigure(root, ["studio"], apply=True, force=False), 0)
            self.assertFalse(destination.exists())
            self.assertFalse((root / "studio" / STATE_RELATIVE).exists())
            self.assertTrue(operating.is_dir())


if __name__ == "__main__":
    unittest.main()
