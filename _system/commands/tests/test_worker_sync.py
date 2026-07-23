#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("post_commit_worker_sync", SCRIPT_DIR / "post_commit_worker_sync.py")
assert SPEC and SPEC.loader
worker_sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker_sync
SPEC.loader.exec_module(worker_sync)


class WorkerSyncTests(unittest.TestCase):
    def shell(self, cwd: Path, *args: str) -> str:
        return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="worker-sync-")
        base = Path(self.temp.name)
        self.root = base / "vault"
        git_dir = base / "external.git"
        self.root.mkdir()
        self.shell(base, "git", "init", "-b", "master", "--separate-git-dir", str(git_dir), str(self.root))
        self.shell(self.root, "git", "config", "user.name", "Test")
        self.shell(self.root, "git", "config", "user.email", "test@example.com")
        (self.root / "note.md").write_text("one\n")
        self.shell(self.root, "git", "add", "note.md")
        self.shell(self.root, "git", "commit", "-m", "one")
        self.state = base / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_enqueue_returns_after_writing_latest_master(self) -> None:
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state)}):
            with mock.patch.object(worker_sync, "spawn_background") as spawn:
                worker_sync.enqueue(self.root)
                (self.root / "note.md").write_text("two\n")
                self.shell(self.root, "git", "commit", "-am", "two")
                worker_sync.enqueue(self.root)
                pending = worker_sync.state_dir(self.root) / "pending"
                self.assertEqual(pending.read_text().strip(), self.shell(self.root, "git", "rev-parse", "HEAD"))
        self.assertEqual(spawn.call_count, 2)

    def test_versioned_hooks_work_with_external_git_directory(self) -> None:
        hooks = self.root / ".githooks"
        hooks.mkdir()
        for name in ("post-commit", "post-checkout", "post-merge", "post-rewrite", "pre-push"):
            (hooks / name).write_text("#!/bin/sh\nexit 0\n")
        worker_sync.install_hooks(self.root, apply=True)
        self.assertEqual(self.shell(self.root, "git", "config", "--get", "core.hooksPath"), ".githooks")
        self.assertTrue(all((hooks / name).stat().st_mode & 0o111 for name in ("post-commit", "pre-push")))


if __name__ == "__main__":
    unittest.main()
