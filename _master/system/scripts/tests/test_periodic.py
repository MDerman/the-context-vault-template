#!/usr/bin/env python3
"""Tests for periodic note generation helpers."""

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

PERIODIC_PATH = SCRIPT_DIR / "periodic.py"
SPEC = importlib.util.spec_from_file_location("periodic", PERIODIC_PATH)
assert SPEC and SPEC.loader
periodic = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = periodic
SPEC.loader.exec_module(periodic)


class PeriodicTemplateRenderingTests(unittest.TestCase):
    def test_renders_templater_date_now_and_cursor_calls(self) -> None:
        template = """---
entity: <% tp.file.folder(true).split('/')[0] %>
period_id: <% tp.file.title %>
---
- [[<% tp.file.folder(true).split('/')[0] %>/_obsidian/periodic/weekly/<% tp.date.now("GGGG-[W]WW", 0, tp.file.title, "YYYY-MM-DD") %>|Weekly note]]
- [[<% tp.file.folder(true).split('/')[0] %>/_obsidian/periodic/quarterly/<% tp.date.now("YYYY-[Q]Q", 0, tp.file.title, "YYYY-MM-DD") %>|Quarterly note]]
<< [[<% tp.date.now("YYYY-MM-DD", -1, tp.file.title, "YYYY-MM-DD") %>]] | [[<% tp.date.now("YYYY-MM-DD", 1, tp.file.title, "YYYY-MM-DD") %>]]>>
On this day last year <% tp.date.now("YYYY-MM-DD", "P-1Y") %>
<% tp.file.cursor() %>
"""
        with tempfile.TemporaryDirectory() as tmp:
            rendered = periodic.render_template(
                Path(tmp),
                template,
                "personal",
                "2026-06-01",
                dt.date(2026, 6, 1),
            )

        self.assertIn("entity: personal", rendered)
        self.assertIn("period_id: 2026-06-01", rendered)
        self.assertIn("[[personal/_obsidian/periodic/weekly/2026-W23|Weekly note]]", rendered)
        self.assertIn("[[personal/_obsidian/periodic/quarterly/2026-Q2|Quarterly note]]", rendered)
        self.assertIn("<< [[2026-05-31]] | [[2026-06-02]]>>", rendered)
        self.assertIn("On this day last year 2025-06-01", rendered)
        self.assertNotIn("<%", rendered)


if __name__ == "__main__":
    unittest.main()
