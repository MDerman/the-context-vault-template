#!/usr/bin/env python3
"""Tests for daily refresh LaunchAgent wrapper."""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REFRESH_SCHEDULE_PATH = SCRIPT_DIR / "refresh_schedule.py"
SPEC = importlib.util.spec_from_file_location("refresh_schedule", REFRESH_SCHEDULE_PATH)
assert SPEC and SPEC.loader
refresh_schedule = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = refresh_schedule
SPEC.loader.exec_module(refresh_schedule)


def write_config(root: Path, **refresh_schedule_config: object) -> None:
    config_path = root / "_master/system/config.json"
    config_path.parent.mkdir(parents=True)
    config = {
        "refresh_schedule": {
            "enabled": True,
            "label": "com.obsidian-context-vault.refresh",
            "timezone": "UTC",
            "hour": 2,
            "minute": 0,
            "catchup_interval_seconds": 60,
            "retry_attempts": 3,
            "retry_delay_seconds": 0,
            **refresh_schedule_config,
        }
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")


def today_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


class RefreshScheduleTests(unittest.TestCase):
    def test_launch_agent_plist_includes_load_calendar_and_catchup_interval(self) -> None:
        config = {
            "label": "com.example.refresh",
            "hour": 2,
            "minute": 0,
            "catchup_interval_seconds": 60,
        }

        plist = refresh_schedule.launch_agent_plist(Path("/tmp/vault"), config)

        self.assertTrue(plist["RunAtLoad"])
        self.assertEqual(plist["StartCalendarInterval"], {"Hour": 2, "Minute": 0})
        self.assertEqual(plist["StartInterval"], 60)

    def test_register_dry_run_does_not_run_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root)
            with mock.patch.object(refresh_schedule.sys, "platform", "darwin"):
                with mock.patch.object(refresh_schedule, "run_launchctl") as launchctl:
                    with mock.patch.object(refresh_schedule, "run_due") as run_due:
                        with contextlib.redirect_stdout(io.StringIO()) as stdout:
                            result = refresh_schedule.register(root, dry_run=True)

            self.assertEqual(result, 0)
            self.assertIn("would write", stdout.getvalue())
            launchctl.assert_not_called()
            run_due.assert_not_called()

    def test_run_due_skips_when_today_stamp_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            state = Path(tmp) / "state"
            write_config(root)
            state.mkdir()
            (state / "last-refresh-date.txt").write_text(today_utc() + "\n", encoding="utf-8")
            with mock.patch.object(refresh_schedule, "STATE_DIR", state):
                with mock.patch.object(refresh_schedule.subprocess, "run") as run:
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = refresh_schedule.run_due(root)

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "")
            run.assert_not_called()

    def test_run_due_retries_three_times_and_leaves_stamp_stale_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            state = Path(tmp) / "state"
            write_config(root, retry_attempts=3, retry_delay_seconds=0)
            calls: list[list[str]] = []

            def fail(command: list[str], cwd: Path) -> SimpleNamespace:
                calls.append(command)
                return SimpleNamespace(returncode=1)

            with mock.patch.object(refresh_schedule, "STATE_DIR", state):
                with mock.patch.object(refresh_schedule.subprocess, "run", side_effect=fail):
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = refresh_schedule.run_due(root)

            self.assertEqual(result, 1)
            self.assertEqual(len(calls), 3)
            self.assertFalse((state / "last-refresh-date.txt").exists())

    def test_run_due_writes_stamp_after_retry_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            state = Path(tmp) / "state"
            write_config(root, retry_attempts=3, retry_delay_seconds=0)
            returncodes = [1, 0]

            def run(command: list[str], cwd: Path) -> SimpleNamespace:
                return SimpleNamespace(returncode=returncodes.pop(0))

            with mock.patch.object(refresh_schedule, "STATE_DIR", state):
                with mock.patch.object(refresh_schedule.subprocess, "run", side_effect=run) as subprocess_run:
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = refresh_schedule.run_due(root)

            self.assertEqual(result, 0)
            self.assertEqual(subprocess_run.call_count, 2)
            self.assertEqual((state / "last-refresh-date.txt").read_text(encoding="utf-8").strip(), today_utc())

    def test_run_due_lock_prevents_duplicate_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            state = Path(tmp) / "state"
            write_config(root)
            state.mkdir()
            lock_path = state / "refresh.lock"
            with lock_path.open("w", encoding="utf-8") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with mock.patch.object(refresh_schedule, "STATE_DIR", state):
                    with mock.patch.object(refresh_schedule.subprocess, "run") as run:
                        with contextlib.redirect_stdout(io.StringIO()) as stdout:
                            result = refresh_schedule.run_due(root)
                fcntl.flock(lock, fcntl.LOCK_UN)

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
