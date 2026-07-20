#!/usr/bin/env python3
"""Tests for Apple Notes Brain Dump ingestion helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BRAIN_DUMP_PATH = SCRIPT_DIR / "brain_dump.py"
SPEC = importlib.util.spec_from_file_location("brain_dump", BRAIN_DUMP_PATH)
assert SPEC and SPEC.loader
brain_dump = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = brain_dump
SPEC.loader.exec_module(brain_dump)


class BrainDumpClearBodyTests(unittest.TestCase):
    def test_clear_body_prepends_title_when_template_is_blank(self) -> None:
        body = brain_dump.clear_body_for_note("<div><br></div>", "Brain Dump")

        self.assertTrue(body.startswith("<div>Brain Dump</div>"))

    def test_clear_body_does_not_duplicate_existing_title_placeholder(self) -> None:
        body = brain_dump.clear_body_for_note("<div>{note_name}</div><div><br></div>", "Brain Dump")

        self.assertEqual(body, "<div>Brain Dump</div><div><br></div>")

    def test_clear_body_escapes_title(self) -> None:
        body = brain_dump.clear_body_for_note("<div><br></div>", "Ideas & Tasks")

        self.assertTrue(body.startswith("<div>Ideas &amp; Tasks</div>"))


if __name__ == "__main__":
    unittest.main()
