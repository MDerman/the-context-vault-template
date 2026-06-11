#!/usr/bin/env python3
"""Tests for generated dashboard checklist rules."""

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

CONTEXT_PATH = SCRIPT_DIR / "context.py"
SPEC = importlib.util.spec_from_file_location("context", CONTEXT_PATH)
assert SPEC and SPEC.loader
context = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = context
SPEC.loader.exec_module(context)


CONFIG = {
    "dashboard_checklist": {
        "end_of_week_day": "sunday",
        "monthly_sops_reminder_day": "last_day",
    }
}


class DashboardChecklistTests(unittest.TestCase):
    def lines_for(self, root: Path, day: dt.date) -> list[str]:
        return context.dashboard_checklist_lines(root, day, context.active_periods(day), CONFIG)

    def test_daily_checklist_and_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            day = dt.date(2025, 7, 23)
            lines = self.lines_for(Path(tmp), day)

        self.assertEqual(context.checklist_heading(day), "Checklist for Wed, 23rd July")
        self.assertEqual(len(lines), 1)
        self.assertIn("[[_master/_obsidian/periodic/daily/2025-07-23|Plan and review day]]", lines[0])

    def test_dashboard_heading_is_home_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rendered = context.dashboard_markdown(
                root,
                ["personal"],
                context.active_periods(dt.date(2025, 7, 23)),
                [],
                "2025-07-23T07:00:00",
                dt.date(2025, 7, 23),
                CONFIG,
            )

        self.assertIn("#### Home Pages\n", rendered)
        self.assertNotIn("#### Home Pages (contexts)", rendered)

    def test_end_of_week_includes_weekly_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = self.lines_for(Path(tmp), dt.date(2025, 6, 15))

        joined = "\n".join(lines)
        self.assertIn("[[_master/_obsidian/periodic/weekly/2025-W24|Plan next week and review the 24th week of 2025]]", joined)

    def test_month_end_and_stale_monthly_sops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = root / "_master/system/context"
            agent_dir.mkdir(parents=True)
            (agent_dir / "2025-06.md").write_text(
                """---
type: agent-periodic
period: monthly
period_id: 2025-06
generated: true
---
- [ ] One
- [x] Done
- [ ] Two
""",
                encoding="utf-8",
            )
            lines = self.lines_for(root, dt.date(2025, 7, 31))

        joined = "\n".join(lines)
        self.assertIn("[[_master/_obsidian/periodic/monthly/2025-07|Monthly SOPs]]", joined)
        self.assertIn("[[_master/_obsidian/periodic/monthly/2025-06|Finish Monthly SOPs for June 2025]] (2 open)", joined)

    def test_quarter_planning_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sunday_before = "\n".join(self.lines_for(root, dt.date(2025, 9, 28)))
            day_before = "\n".join(self.lines_for(root, dt.date(2025, 9, 29)))
            too_early = "\n".join(self.lines_for(root, dt.date(2025, 9, 21)))

        text = "[[_master/_obsidian/periodic/quarterly/2025-Q3|Plan next quarter and review past quarter]]"
        self.assertIn(text, sunday_before)
        self.assertIn(text, day_before)
        self.assertNotIn(text, too_early)


if __name__ == "__main__":
    unittest.main()
