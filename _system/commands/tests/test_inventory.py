#!/usr/bin/env python3
"""Tests for live vault inventory routing."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
INVENTORY_PATH = SCRIPT_DIR / "inventory.py"
SPEC = importlib.util.spec_from_file_location("inventory", INVENTORY_PATH)
assert SPEC and SPEC.loader
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def test_inventory_reads_live_sources_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "personal"
            tasks = personal / "_obsidian/tasks"
            schedules = personal / "_obsidian/content-schedules"
            daily = personal / "_obsidian/periodic/daily"
            tasks.mkdir(parents=True)
            schedules.mkdir(parents=True)
            daily.mkdir(parents=True)
            (personal / "personal.md").write_text(
                "---\nstatus: active\ncontext_type: personal\ncontent_enabled: true\ndefault_capture: true\n---\n",
                encoding="utf-8",
            )
            (tasks / "Ship.md").write_text(
                "---\ntitle: Ship\nstatus: in-progress\npriority: high\n---\n",
                encoding="utf-8",
            )
            (tasks / "Later.md").write_text(
                "---\ntitle: Later\nstatus: backlog\npriority: normal\n---\n",
                encoding="utf-8",
            )
            (schedules / "Current.md").write_text(
                "---\ntype: content-schedule\nschedule_start: 2026-07-06\nschedule_end: 2026-08-02\n---\n",
                encoding="utf-8",
            )
            (daily / "2026-07-20.md").write_text("# Daily\n", encoding="utf-8")
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

            result = inventory.build_inventory(root, active_only=False, day=dt.date(2026, 7, 20))
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

        self.assertEqual(before, after)
        self.assertEqual(result["default_capture_context"], "personal")
        self.assertEqual(result["active_periods"]["weekly"], "2026-W30")
        self.assertEqual(result["contexts"][0]["note_path"], "personal/personal.md")
        self.assertTrue(result["contexts"][0]["periodic_notes"]["daily"]["exists"])
        self.assertEqual(result["content_schedules"][0]["path"], "personal/_obsidian/content-schedules/Current.md")
        self.assertEqual(result["tasks"]["in-progress"][0]["path"], "personal/_obsidian/tasks/Ship.md")
        self.assertEqual(result["backlog_counts"], {"personal": 1})


if __name__ == "__main__":
    unittest.main()
