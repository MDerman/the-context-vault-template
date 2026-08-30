#!/usr/bin/env python3
"""Focused tests for portable fleet skill snapshots."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


AGENT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "agents/_package/src"
sys.path.insert(0, str(AGENT_SCRIPTS_DIR))

import skill_snapshots  # noqa: E402


class AgentSkillSnapshotTests(unittest.TestCase):
    def make_skill(self, root: Path, name: str, body: str) -> Path:
        path = root / name
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text(f"---\nname: {name}\n---\n\n{body}\n", encoding="utf-8")
        return path

    def test_apply_installs_real_copies_and_preserves_unmanaged_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            sources = base / "sources"
            home = base / "home"
            sources.mkdir()
            home.mkdir()
            example = self.make_skill(sources, "code-example", "first")
            bundle = skill_snapshots.build_bundle({"code-example": example})
            unmanaged = home / ".agents/skills/unmanaged"
            unmanaged.mkdir(parents=True)
            (unmanaged / "KEEP").write_text("mine\n", encoding="utf-8")

            preview = skill_snapshots.reconcile_local(
                home,
                bundle,
                apply=False,
                verify=False,
                backup_suffix="preview",
                legacy_catalog=None,
            )
            self.assertFalse(preview["ready"])
            applied = skill_snapshots.reconcile_local(
                home,
                bundle,
                apply=True,
                verify=False,
                backup_suffix="apply",
                legacy_catalog=None,
            )
            self.assertTrue(applied["ready"])
            installed = home / ".agents/skills/code-example"
            self.assertTrue(installed.is_dir())
            self.assertFalse(installed.is_symlink())
            self.assertEqual((installed / "SKILL.md").read_text(encoding="utf-8"), (example / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual((unmanaged / "KEEP").read_text(encoding="utf-8"), "mine\n")
            for discovery in (home / ".claude/skills", home / ".kilo/skills"):
                alias = discovery / "code-example"
                self.assertTrue(alias.is_symlink())
                self.assertEqual(alias.resolve(), installed.resolve())

            state = json.loads((home / skill_snapshots.STATE_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(set(state["skills"]), {"code-example"})

    def test_new_snapshot_replaces_managed_content_and_removes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            sources = base / "sources"
            home = base / "home"
            sources.mkdir()
            home.mkdir()
            first = self.make_skill(sources, "code-first", "one")
            initial = skill_snapshots.build_bundle({"code-first": first})
            skill_snapshots.reconcile_local(
                home, initial, apply=True, verify=False, backup_suffix="one", legacy_catalog=None
            )
            second = self.make_skill(sources, "code-second", "two")
            replacement = skill_snapshots.build_bundle({"code-second": second})
            skill_snapshots.reconcile_local(
                home, replacement, apply=True, verify=False, backup_suffix="two", legacy_catalog=None
            )
            self.assertFalse(os.path.lexists(home / ".agents/skills/code-first"))
            self.assertTrue((home / ".agents/skills/code-second/SKILL.md").is_file())

    def test_legacy_catalog_links_are_migrated_to_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = self.make_skill(base / "sources", "code-example", "portable")
            home = base / "home"
            catalog = base / "vault/_system/agents/skills"
            home.mkdir()
            catalog.mkdir(parents=True)
            (catalog / "code-example").symlink_to(source)
            canonical = home / ".agents/skills"
            canonical.mkdir(parents=True)
            (canonical / "code-example").symlink_to(catalog / "code-example")
            bundle = skill_snapshots.build_bundle({"code-example": source})
            skill_snapshots.reconcile_local(
                home,
                bundle,
                apply=True,
                verify=False,
                backup_suffix="migration",
                legacy_catalog=catalog,
            )
            self.assertTrue((canonical / "code-example").is_dir())
            self.assertFalse((canonical / "code-example").is_symlink())


if __name__ == "__main__":
    unittest.main()
