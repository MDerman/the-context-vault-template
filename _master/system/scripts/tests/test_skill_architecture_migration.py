#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "migrations/2026_07_14_skill_source_architecture.py"
SPEC = importlib.util.spec_from_file_location("skill_architecture_migration", MIGRATION)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class SkillArchitectureMigrationTests(unittest.TestCase):
    def test_apply_is_idempotent_and_preserves_unknown_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = root / "_master/agents/skills"
            catalog.mkdir(parents=True)
            known = catalog / "continue"
            known.mkdir()
            (known / "SKILL.md").write_text("---\nname: continue\n---\n")
            unknown = catalog / "my-private-skill"
            unknown.mkdir()
            (unknown / "SKILL.md").write_text("mine\n")
            first = migration.run(root, apply=True)
            second = migration.run(root, apply=True)
            self.assertTrue((root / "_master/agents/auto-skills/_agents/continue/SKILL.md").exists())
            self.assertTrue((unknown / "SKILL.md").exists())
            self.assertEqual(len(first["moved"]), 1)
            self.assertEqual(second["moved"], [])
            self.assertEqual(second["conflicts"][0]["source"], "_master/agents/skills/my-private-skill")


if __name__ == "__main__":
    unittest.main()
