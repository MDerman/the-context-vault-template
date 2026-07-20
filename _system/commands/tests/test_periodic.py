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


def make_periodic_entity(root: Path, daily_template: str) -> Path:
    entity = root / "personal"
    template_dir = entity / "_obsidian/templates/periodic"
    template_dir.mkdir(parents=True)
    (entity / "personal.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    (template_dir / "daily-template.md").write_text(daily_template, encoding="utf-8")
    for name in ("weekly", "monthly", "quarterly", "yearly"):
        (template_dir / f"{name}-template.md").write_text("", encoding="utf-8")
    return entity


class PeriodicTemplateRenderingTests(unittest.TestCase):
    def test_active_periods_include_monthly(self) -> None:
        periods = periodic.active_periods(dt.date(2026, 6, 11))

        self.assertEqual(periods["monthly"], "2026-06")

    def test_system_periodic_notes_render_personal_first(self) -> None:
        rendered = periodic.vault_periodic_note(
            Path("/tmp/vault"),
            ["business", "personal-brand", "personal"],
            "weekly",
            "2026-W24",
            "2026-06-11T02:00:00",
        )

        self.assertLess(rendered.index("## personal\n"), rendered.index("## business\n"))
        self.assertLess(rendered.index("  - personal"), rendered.index("  - business"))

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

    def test_generates_source_and_system_monthly_notes_without_agent_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entity = root / "personal"
            (entity / "_obsidian/templates/periodic").mkdir(parents=True)
            (entity / "personal.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
            for name in ("daily", "weekly", "quarterly", "yearly"):
                (entity / "_obsidian/templates/periodic" / f"{name}-template.md").write_text("", encoding="utf-8")
            (entity / "_obsidian/templates/periodic/monthly-template.md").write_text(
                "## Monthly SOPs\n\n- [ ] Review month\n",
                encoding="utf-8",
            )

            periodic.generate_periodic_notes(
                root,
                ["personal"],
                [],
                False,
                dt.date(2026, 6, 11),
                generated_at="2026-06-11T02:00:00",
            )
            periodic.generate_periodic_notes(
                root,
                ["personal"],
                [],
                False,
                dt.date(2026, 7, 1),
                generated_at="2026-07-01T02:00:00",
            )

            self.assertTrue((root / "personal/_obsidian/periodic/monthly/2026-06.md").exists())
            self.assertTrue((root / "_system/_obsidian/periodic/monthly/2026-06.md").exists())
            self.assertFalse(
                any("type: agent-periodic" in path.read_text(encoding="utf-8") for path in root.rglob("*.md"))
            )
            vault_rollup = (root / "_system/_obsidian/periodic/monthly/2026-06.md").read_text(encoding="utf-8")
            self.assertIn("![[personal/_obsidian/periodic/monthly/2026-06]]", vault_rollup)

    def test_carries_unchecked_daily_checklist_items_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entity = make_periodic_entity(
                root,
                """---
type: periodic
period: daily
entity: personal
period_id: <% tp.file.title %>
generated: false
---
## Today
- [ ] 
---
""",
            )
            previous = entity / "_obsidian/periodic/daily/2026-06-11.md"
            previous.parent.mkdir(parents=True)
            previous.write_text(
                """---
type: periodic
period: daily
entity: personal
period_id: 2026-06-11
generated: false
---
## Today
- [ ] alpha
- [ ] beta
- [x] done
- [ ] gamma
- [ ] 
- [ ] delta
---
""",
                encoding="utf-8",
            )

            periodic.generate_periodic_notes(
                root,
                ["personal"],
                [],
                False,
                dt.date(2026, 6, 12),
                generated_at="2026-06-12T02:00:00",
            )
            current = entity / "_obsidian/periodic/daily/2026-06-12.md"
            text = current.read_text(encoding="utf-8")

            self.assertIn("- [ ] alpha\n- [ ] beta\n- [ ] gamma\n- [ ] delta", text)
            self.assertNotIn("- [x] done", text)
            self.assertNotIn("- [ ] \n", text)

            periodic.generate_periodic_notes(
                root,
                ["personal"],
                [],
                False,
                dt.date(2026, 6, 12),
                generated_at="2026-06-12T02:00:00",
            )

            self.assertEqual(text, current.read_text(encoding="utf-8"))

    def test_carries_multiple_headings_and_preserves_existing_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entity = make_periodic_entity(
                root,
                """---
type: periodic
period: daily
entity: personal
period_id: <% tp.file.title %>
generated: false
---
## Output

- [ ] Existing prompt
- [ ] Another prompt

## Notes
-
""",
            )
            previous = entity / "_obsidian/periodic/daily/2026-06-11.md"
            previous.parent.mkdir(parents=True)
            previous.write_text(
                """---
type: periodic
period: daily
entity: personal
period_id: 2026-06-11
generated: false
---
## Output

- [ ] Existing prompt
- [ ] Ship new thing

## Missing Heading
- [ ] Carry into appended heading

## Notes
- not a checklist
""",
                encoding="utf-8",
            )

            periodic.generate_periodic_notes(
                root,
                ["personal"],
                [],
                False,
                dt.date(2026, 6, 12),
                generated_at="2026-06-12T02:00:00",
            )
            text = (entity / "_obsidian/periodic/daily/2026-06-12.md").read_text(encoding="utf-8")

            self.assertEqual(text.count("- [ ] Existing prompt"), 1)
            self.assertIn("- [ ] Another prompt\n- [ ] Ship new thing", text)
            self.assertIn("## Missing Heading\n- [ ] Carry into appended heading", text)
            self.assertNotIn("- [ ] not a checklist", text)


if __name__ == "__main__":
    unittest.main()
