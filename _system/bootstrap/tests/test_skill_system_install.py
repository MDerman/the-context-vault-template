from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BOOTSTRAP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOOTSTRAP))

from install_skill_system import SkillSystemInstallError, install_tree


class SkillSystemBootstrapTests(unittest.TestCase):
    def source_repo(self, root: Path) -> Path:
        source = root / "source"
        defaults = source / "_system/agents/_package/defaults/instance"
        defaults.mkdir(parents=True)
        (defaults / "profile.json").write_text("{}\n", encoding="utf-8")
        skill = source / "_system/agents/skills/auto/_test/example"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: example\ndescription: Test.\n---\n", encoding="utf-8")
        return source

    def test_opt_out_leaves_agents_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            vault.mkdir()
            self.assertFalse((vault / "_system/agents").exists())

    def test_opt_in_copies_public_tree_and_initializes_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            install_tree(self.source_repo(root), vault, source_url="test", release_version="0.1.0", commit="abc")
            self.assertTrue((vault / "_system/agents/skills/auto/_test/example/SKILL.md").is_file())
            self.assertTrue((vault / "_system/agents/_package/instance/profile.json").is_file())
            self.assertTrue((vault / "_system/local/state/skill-system-install.json").is_file())

    def test_existing_agents_tree_is_preserved_and_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            existing = vault / "_system/agents"
            existing.mkdir(parents=True)
            marker = existing / "keep.txt"
            marker.write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(SkillSystemInstallError, "refusing to overwrite"):
                install_tree(self.source_repo(root), vault, source_url="test", release_version="0.1.0", commit="abc")
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")


if __name__ == "__main__":
    unittest.main()
