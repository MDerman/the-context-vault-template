#!/usr/bin/env python3
"""Tests for vault refresh command orchestration."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REFRESH_PATH = SCRIPT_DIR / "refresh.py"
SPEC = importlib.util.spec_from_file_location("refresh", REFRESH_PATH)
assert SPEC and SPEC.loader
refresh = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = refresh
SPEC.loader.exec_module(refresh)


class RefreshTests(unittest.TestCase):
    def test_refresh_skips_brain_dump_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            commands: list[list[str]] = []

            with mock.patch.object(refresh, "run", side_effect=lambda command, _root: commands.append(command)):
                result = refresh.main(["--root", str(root), "--skip-gcal", "--skip-git-maintenance"])

            self.assertEqual(result, 0)
            self.assertTrue(commands)
            self.assertFalse(any("brain_dump.py" in " ".join(command) for command in commands))
            self.assertTrue(any("context.py" in " ".join(command) for command in commands))

    def test_sync_brain_dump_runs_ingest_before_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            commands: list[list[str]] = []

            with mock.patch.object(refresh, "run", side_effect=lambda command, _root: commands.append(command)):
                result = refresh.main(
                    ["--root", str(root), "--sync-brain-dump", "--skip-gcal", "--skip-git-maintenance"]
                )

            self.assertEqual(result, 0)
            self.assertGreaterEqual(len(commands), 2)
            self.assertIn("brain_dump.py", " ".join(commands[0]))
            self.assertIn("context.py", " ".join(commands[1]))


if __name__ == "__main__":
    unittest.main()
