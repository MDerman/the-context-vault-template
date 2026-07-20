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
            with mock.patch.object(refresh, "run") as run:
                with mock.patch.object(refresh, "generate_derived_views") as generate:
                    result = refresh.main(["--root", str(root), "--skip-gcal", "--skip-git-maintenance"])

            self.assertEqual(result, 0)
            run.assert_not_called()
            generate.assert_called_once()

    def test_sync_brain_dump_runs_ingest_before_derived_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            events: list[str] = []

            def record_run(command: list[str], _root: Path) -> None:
                self.assertIn("brain_dump.py", " ".join(command))
                events.append("brain-dump")

            with mock.patch.object(refresh, "run", side_effect=record_run):
                with mock.patch.object(refresh, "generate_derived_views", side_effect=lambda *args, **kwargs: events.append("views")):
                    result = refresh.main(
                        ["--root", str(root), "--sync-brain-dump", "--skip-gcal", "--skip-git-maintenance"]
                    )

            self.assertEqual(result, 0)
            self.assertEqual(events, ["brain-dump", "views"])

    def test_refresh_forwards_selection_and_date_to_derived_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            with mock.patch.object(refresh, "generate_derived_views") as generate:
                result = refresh.main(
                    [
                        "--root",
                        str(root),
                        "--skip-gcal",
                        "--skip-git-maintenance",
                        "--context-folders",
                        "personal,business",
                        "--date",
                        "2026-07-20",
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(generate.call_args.kwargs["explicit_entities"], ["personal", "business"])
        self.assertEqual(generate.call_args.kwargs["day"].isoformat(), "2026-07-20")

    def test_derived_view_failure_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            with mock.patch.object(refresh, "generate_derived_views", side_effect=RuntimeError("dashboard failed")):
                with self.assertRaisesRegex(RuntimeError, "dashboard failed"):
                    refresh.main(["--root", str(root), "--skip-gcal", "--skip-git-maintenance"])


if __name__ == "__main__":
    unittest.main()
