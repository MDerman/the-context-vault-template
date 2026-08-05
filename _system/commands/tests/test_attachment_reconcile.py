#!/usr/bin/env python3
"""Tests for Learning attachment reconciliation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from attachment_reconcile import (  # noqa: E402
    anchor_text,
    deterministic_generic_plan,
    export_targets,
    insert_missing_embeds,
    normalized_title,
    replace_spans,
    rewrite_from_export,
    slugify,
    similarity,
)


class AttachmentReconcileTests(unittest.TestCase):
    def test_export_targets_parse_encoded_balanced_parentheses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "A Note (Example)"
            assets.mkdir()
            image = assets / "Untitled.png"
            image.write_bytes(b"png")
            note = root / "A Note abcdefabcdefabcdefabcdefabcdefab.md"
            note.write_text("![Untitled](A%20Note%20(Example)/Untitled.png)\n", encoding="utf-8")
            self.assertEqual(export_targets(note), [image.resolve()])

    def test_insert_missing_embed_uses_surrounding_text_without_replacing_current_media(self) -> None:
        current = "# Topic\n![[current-only.png]]\n\nFollowing text\n"
        exported = "# Topic\n\n![Untitled](Topic/Untitled.png)\n\nFollowing text\n"
        rewritten, conflicts = insert_missing_embeds(current, exported, [(2, "![[topic-image-001.png]]")])
        self.assertEqual(conflicts, [])
        self.assertIn("![[current-only.png]]", rewritten)
        self.assertIn("![[topic-image-001.png]]", rewritten)
        self.assertLess(rewritten.index("topic-image-001"), rewritten.index("Following text"))

    def test_insert_missing_embed_refuses_unanchored_change(self) -> None:
        current = "Completely different\n"
        exported = "Before\n![Untitled](Topic/Untitled.png)\nAfter\n"
        rewritten, conflicts = insert_missing_embeds(current, exported, [(1, "![[topic-image-001.png]]")])
        self.assertEqual(rewritten, current)
        self.assertTrue(conflicts)

    def test_helpers_make_stable_names(self) -> None:
        self.assertEqual(normalized_title("SOLID, Design Patterns"), "soliddesignpatterns")
        self.assertEqual(slugify("SOLID, Design Patterns"), "solid-design-patterns")
        self.assertEqual(anchor_text("## Following Text"), "followingtext")
        self.assertEqual(replace_spans("a OLD z", [(2, 5, "NEW")]), "a NEW z")
        self.assertLess(similarity("avl tree assignment", "swing thread game"), 0.35)

    def test_global_pass_excludes_primary_learning_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "_library/_dev/Topic.md"
            media = root / "_library/_obsidian/attachments/Topic/Untitled.png"
            note.parent.mkdir(parents=True)
            media.parent.mkdir(parents=True)
            note.write_text("![[Untitled.png]]\n", encoding="utf-8")
            media.write_bytes(b"png")

            plan = deterministic_generic_plan(root, set(), set())

            self.assertEqual(plan.asset_actions, [])
            self.assertEqual(plan.note_edits, [])

    def test_global_pass_does_not_use_lone_unrelated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "ctx/Topic.md"
            media = root / "ctx/_obsidian/attachments/Unrelated/Untitled.png"
            note.parent.mkdir(parents=True)
            media.parent.mkdir(parents=True)
            note.write_text("![[Untitled.png]]\n", encoding="utf-8")
            media.write_bytes(b"png")

            plan = deterministic_generic_plan(root, set(), set())

            self.assertEqual(plan.asset_actions, [])
            self.assertEqual(plan.note_edits, [])
            self.assertEqual(len(plan.conflicts), 1)

    def test_rewrite_consumes_repeated_generic_basenames_in_export_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "Topic.md"
            source = root / "Export Topic.md"
            first = root / "One/Untitled 2.png"
            second = root / "Two/Untitled 2.png"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            note.write_text("![[Untitled 2.png]]\n![[Untitled 2.png]]\n", encoding="utf-8")
            source.write_text(
                "![first](One/Untitled%202.png)\n![second](Two/Untitled%202.png)\n",
                encoding="utf-8",
            )
            hashes = {first.resolve(): "first-hash", second.resolve(): "second-hash"}
            names = {"first-hash": "topic-image-001.png", "second-hash": "topic-image-002.png"}

            rewritten, restored, conflicts = rewrite_from_export(note, source, names, hashes)

            self.assertEqual(conflicts, [])
            self.assertEqual(restored, 0)
            self.assertEqual(rewritten, "![[topic-image-001.png]]\n![[topic-image-002.png]]\n")

    def test_rewrite_uses_position_when_import_reused_wrong_generic_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "Topic.md"
            source = root / "Export Topic.md"
            first = root / "Topic/Untitled.png"
            second = root / "Topic/Untitled 1.png"
            third = root / "Topic/Untitled 2.png"
            first.parent.mkdir()
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            third.write_bytes(b"third")
            note.write_text(
                "![[Untitled.png]]\n![[Untitled 1.png]]\n![[Untitled 1.png]]\n",
                encoding="utf-8",
            )
            source.write_text(
                "![first](Topic/Untitled.png)\n"
                "![second](Topic/Untitled%201.png)\n"
                "![third](Topic/Untitled%202.png)\n",
                encoding="utf-8",
            )
            hashes = {first.resolve(): "a", second.resolve(): "b", third.resolve(): "c"}
            names = {"a": "topic-image-001.png", "b": "topic-image-002.png", "c": "topic-image-003.png"}

            rewritten, restored, conflicts = rewrite_from_export(note, source, names, hashes)

            self.assertEqual(conflicts, [])
            self.assertEqual(restored, 0)
            self.assertEqual(
                rewritten,
                "![[topic-image-001.png]]\n![[topic-image-002.png]]\n![[topic-image-003.png]]\n",
            )


if __name__ == "__main__":
    unittest.main()
