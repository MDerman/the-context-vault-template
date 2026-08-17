#!/usr/bin/env python3
"""Tests for Apple Notes Brain Dump ingestion helpers."""

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


class BrainDumpAttachmentTests(unittest.TestCase):
    def test_attachment_export_parses_saved_and_failed_records(self) -> None:
        output = (
            "saved\tcid:image-1\timage.png\timport-1-image.png\t\n"
            "failed\tcid:table-1\t\timport-2-attachment-2\t\t-10000\tAppleEvent handler failed.\n"
        )
        completed = mock.Mock(returncode=0, stdout=output, stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(brain_dump.subprocess, "run", return_value=completed):
                attachments, failures = brain_dump.save_brain_dump_attachments(
                    "Brain Dump", Path(tmp), "import"
                )

        self.assertEqual(attachments[0]["output_name"], "import-1-image.png")
        self.assertEqual(failures[0]["error_number"], "-10000")

    def test_unreferenced_failed_attachment_is_safe_when_body_contains_table_object(self) -> None:
        failures = [{"cid": "cid:table-object", "url": ""}]
        note_html = "<div><object><table><tr><td>Kept text</td></tr></table></object></div>"

        self.assertTrue(brain_dump.failures_are_embedded_tables(note_html, failures))

    def test_referenced_failed_attachment_is_not_treated_as_table_object(self) -> None:
        failures = [{"cid": "cid:image-1", "url": ""}]
        note_html = '<object><table><tr><td>Text</td></tr></table></object><img src="cid:image-1">'

        self.assertFalse(brain_dump.failures_are_embedded_tables(note_html, failures))

    def test_failed_attachment_without_table_object_is_not_safe(self) -> None:
        failures = [{"cid": "cid:file-1", "url": ""}]

        self.assertFalse(brain_dump.failures_are_embedded_tables("<div>Text only</div>", failures))


if __name__ == "__main__":
    unittest.main()
