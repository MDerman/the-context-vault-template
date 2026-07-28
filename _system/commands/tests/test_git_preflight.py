#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("git_preflight", SCRIPT_DIR / "git_preflight.py")
assert SPEC and SPEC.loader
git_preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = git_preflight
SPEC.loader.exec_module(git_preflight)


class GitPreflightTests(unittest.TestCase):
    def shell(self, cwd: Path, *args: str) -> str:
        return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="preflight-")
        base = Path(self.temp.name)
        self.remote = base / "remote.git"
        self.seed = base / "seed"
        self.clone = base / "clone"
        self.shell(base, "git", "init", "--bare", str(self.remote))
        self.shell(base, "git", "init", "-b", "master", str(self.seed))
        self.shell(self.seed, "git", "config", "user.name", "Test")
        self.shell(self.seed, "git", "config", "user.email", "test@example.com")
        (self.seed / "note.md").write_text("one\n")
        self.shell(self.seed, "git", "add", "note.md")
        self.shell(self.seed, "git", "commit", "-m", "one")
        self.shell(self.seed, "git", "remote", "add", "origin", str(self.remote))
        self.shell(self.seed, "git", "push", "-u", "origin", "master")
        self.shell(base, "git", "clone", str(self.remote), str(self.clone))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def advance_remote(self, text: str) -> str:
        (self.seed / "note.md").write_text(text)
        self.shell(self.seed, "git", "commit", "-am", text.strip())
        self.shell(self.seed, "git", "push", "origin", "master")
        return self.shell(self.seed, "git", "rev-parse", "HEAD")

    def test_current_and_behind_fast_forward(self) -> None:
        self.assertEqual(git_preflight.preflight(self.clone, "origin", "master", sync_skills=False), "current")
        expected = self.advance_remote("two\n")
        self.assertEqual(git_preflight.preflight(self.clone, "origin", "master", sync_skills=False), "updated")
        self.assertEqual(self.shell(self.clone, "git", "rev-parse", "HEAD"), expected)

    def test_dirty_current_checkout_is_allowed(self) -> None:
        (self.clone / "note.md").write_text("dirty\n")
        self.assertEqual(git_preflight.preflight(self.clone, "origin", "master", sync_skills=False), "current")
        self.assertEqual((self.clone / "note.md").read_text(), "dirty\n")

    def test_dirty_unrelated_file_survives_fast_forward(self) -> None:
        scratch = self.clone / "scratch.md"
        scratch.write_text("local draft\n")
        expected = self.advance_remote("two\n")

        self.assertEqual(git_preflight.preflight(self.clone, "origin", "master", sync_skills=False), "updated")

        self.assertEqual(self.shell(self.clone, "git", "rev-parse", "HEAD"), expected)
        self.assertEqual(scratch.read_text(), "local draft\n")

    def test_overlapping_dirty_file_blocks_fast_forward_without_changing_head(self) -> None:
        original_head = self.shell(self.clone, "git", "rev-parse", "HEAD")
        (self.clone / "note.md").write_text("local draft\n")
        self.advance_remote("remote update\n")

        with self.assertRaisesRegex(git_preflight.PreflightError, "safe fast-forward blocked"):
            git_preflight.preflight(self.clone, "origin", "master", sync_skills=False)

        self.assertEqual(self.shell(self.clone, "git", "rev-parse", "HEAD"), original_head)
        self.assertEqual((self.clone / "note.md").read_text(), "local draft\n")

    def test_diverged_stops(self) -> None:
        self.shell(self.clone, "git", "config", "user.name", "Test")
        self.shell(self.clone, "git", "config", "user.email", "test@example.com")
        (self.clone / "local.md").write_text("local\n")
        self.shell(self.clone, "git", "add", "local.md")
        self.shell(self.clone, "git", "commit", "-m", "local")
        self.advance_remote("remote\n")
        with self.assertRaisesRegex(git_preflight.PreflightError, "diverged"):
            git_preflight.preflight(self.clone, "origin", "master", sync_skills=False)

    def test_missing_remote_is_inactive(self) -> None:
        self.shell(self.clone, "git", "remote", "remove", "origin")
        self.assertEqual(git_preflight.preflight(self.clone, "origin", "master", sync_skills=False), "inactive")


if __name__ == "__main__":
    unittest.main()
