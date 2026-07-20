#!/usr/bin/env python3
"""Tests for generated vault skill catalog sync."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
sys.path.insert(0, str(AGENTS_DIR))

import sync_skills  # noqa: E402


class SkillSyncTests(unittest.TestCase):
    def roots(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp) / "vault"
        home = Path(tmp) / "home"
        for name in ("auto-skills", "manual-skills", "gh-skills", "skills"):
            (root / "_system/agents" / name).mkdir(parents=True)
        home.mkdir()
        return root, home

    def skill(self, root: Path, source: str, relative: str, name: str | None = None) -> Path:
        path = root / "_system/agents" / source / relative
        path.mkdir(parents=True)
        declared = name or path.name
        (path / "SKILL.md").write_text(f"---\nname: {declared}\n---\n", encoding="utf-8")
        return path

    def test_recursive_groups_are_flattened(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            source = self.skill(root, "auto-skills", "_code/_python/example")
            sync_skills.sync(root, home, apply=True)
            link = root / "_system/agents/skills/example"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), source.resolve())

    def test_group_and_frontmatter_names_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "auto-skills", "Code/example")
            with self.assertRaisesRegex(sync_skills.SyncError, "_lower-kebab"):
                sync_skills.scan_source(root / "_system/agents/auto-skills", "auto")
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "auto-skills", "_code/example", name="wrong")
            with self.assertRaisesRegex(sync_skills.SyncError, "mismatch"):
                sync_skills.scan_source(root / "_system/agents/auto-skills", "auto")

    def test_duplicate_names_fail_before_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "auto-skills", "_one/example")
            self.skill(root, "manual-skills", "_two/example")
            with self.assertRaisesRegex(sync_skills.SyncError, "Duplicate skill"):
                sync_skills.sync(root, home, apply=True)
            self.assertEqual(list((root / "_system/agents/skills").iterdir()), [])

    def test_dry_run_is_pure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            skill = self.skill(root, "manual-skills", "_code/example")
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            sync_skills.sync(root, home, apply=False)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertFalse((skill / "agents/openai.yaml").exists())

    def test_policy_is_created_and_existing_metadata_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            auto = self.skill(root, "auto-skills", "_code/auto-example")
            manual = self.skill(root, "manual-skills", "_code/manual-example")
            metadata = auto / "agents/openai.yaml"
            metadata.parent.mkdir()
            metadata.write_text("interface:\n  display_name: Example\npolicy:\n  allow_implicit_invocation: false\n")
            sync_skills.sync(root, home, apply=True)
            self.assertIn("display_name: Example", metadata.read_text())
            self.assertIn("allow_implicit_invocation: true", metadata.read_text())
            self.assertIn("allow_implicit_invocation: false", (manual / "agents/openai.yaml").read_text())

    def test_stale_links_removed_and_real_collision_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "auto-skills", "_code/example")
            stale = root / "_system/agents/skills/stale"
            stale.symlink_to("../auto-skills/_code/missing")
            sync_skills.sync(root, home, apply=True)
            self.assertFalse(stale.is_symlink())
            collision = root / "_system/agents/skills/real-content"
            collision.mkdir()
            with self.assertRaisesRegex(sync_skills.SyncError, "Unexpected real content"):
                sync_skills.sync(root, home, apply=False)

    def test_global_links_migrate_without_ingesting_or_deleting_unmanaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "auto-skills", "_code/example")
            catalog = root / "_system/agents/skills"
            claude = home / ".claude"
            claude.mkdir()
            (claude / "skills").symlink_to(catalog)
            agents = home / ".agents/skills"
            agents.mkdir(parents=True)
            unrelated = agents / "unrelated"
            unrelated.mkdir()
            (unrelated / "KEEP").write_text("mine\n")
            sync_skills.sync(root, home, apply=True)
            self.assertTrue((claude / "skills").is_dir())
            self.assertFalse((claude / "skills").is_symlink())
            self.assertTrue((claude / "skills/example").is_symlink())
            self.assertEqual((unrelated / "KEEP").read_text(), "mine\n")
            self.assertFalse((root / "_system/agents/auto-skills/unrelated").exists())

    def test_moved_dependency_updates_config_marker_type_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            skill = self.skill(root, "auto-skills", "_creative/example")
            marker = {
                "managed_by": "vault deps",
                "repo_id": "example",
                "source": "skills/example",
                "target": "_system/agents/manual-skills/example",
                "type": "manual-skill",
            }
            (skill / sync_skills.MARKER).write_text(json.dumps(marker) + "\n")
            config = root / "_system/config/deps.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"repos": [{"id": "example", "projections": [marker.copy()]}]}) + "\n")
            sync_skills.sync(root, home, apply=True)
            projection = json.loads(config.read_text())["repos"][0]["projections"][0]
            self.assertEqual(projection["type"], "auto-skill")
            self.assertEqual(projection["target"], "_system/agents/auto-skills/_creative/example")
            updated_marker = json.loads((skill / sync_skills.MARKER).read_text())
            self.assertEqual(updated_marker["type"], "auto-skill")

    def test_duplicate_dependency_projection_names_fail_without_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            config = root / "_system/config/deps.json"
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "repos": [
                            {
                                "id": "one",
                                "projections": [
                                    {"source": "skills/a", "target": "_system/agents/auto-skills/_one/example", "type": "auto-skill"}
                                ],
                            },
                            {
                                "id": "two",
                                "projections": [
                                    {"source": "skills/b", "target": "_system/agents/manual-skills/_two/example", "type": "manual-skill"}
                                ],
                            },
                        ]
                    }
                )
                + "\n"
            )
            with self.assertRaisesRegex(sync_skills.SyncError, "Duplicate dependency skill"):
                sync_skills.sync(root, home, apply=True)
            self.assertEqual(list((root / "_system/agents/skills").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
