#!/usr/bin/env python3
"""Integration tests for managed text snippet synchronization."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("managed_snippets", SCRIPT_DIR / "snippets.py")
assert SPEC and SPEC.loader
managed_snippets = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = managed_snippets
SPEC.loader.exec_module(managed_snippets)


class ManagedSnippetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="managed-snippets-")
        self.base = Path(self.temp.name)
        self.vault = self.base / "vault"
        self.external = self.base / "external"
        self.config = self.vault / "_system/local/snippets"
        self.registry = self.vault / "repositories.json"
        self.source = self.config / "sources/example.md"
        for root in (self.vault, self.external):
            root.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", "-b", "master"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        self.source.parent.mkdir(parents=True)
        (self.config / "private").mkdir(parents=True)
        self.source.write_text("Canonical line one.\n\nCanonical line two.\n", encoding="utf-8")
        self.write_target(self.vault / "AGENTS.md", prefix="# Vault\n", suffix="\nAfter vault.\n")
        self.write_target(self.external / "AGENTS.md", prefix="# External\n", suffix="\nAfter external.\n")
        (self.config / "defaults.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "snippets": {
                        "example": {
                            "source": "sources/example.md",
                            "targets": [{"repository": "vault", "path": "AGENTS.md"}],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.config / "private/targets.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "targets": {
                        "example": [{"repository": "external", "path": "AGENTS.md"}]
                    },
                }
            ),
            encoding="utf-8",
        )
        self.registry.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "repositories": {"external": {"path": str(self.external)}},
                }
            ),
            encoding="utf-8",
        )
        for root in (self.vault, self.external):
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def write_target(path: Path, *, prefix: str, suffix: str) -> None:
        path.write_text(
            prefix
            + "<!-- snippet:example:start -->\n"
            + "Old generated text.\n"
            + "<!-- snippet:example:end -->\n"
            + suffix,
            encoding="utf-8",
        )

    def call(self, *args: str) -> tuple[int, str, str]:
        argv = [
            "--root",
            str(self.vault),
            "--config-dir",
            str(self.config),
            "--repository-registry",
            str(self.registry),
            *args,
        ]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = managed_snippets.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_dry_run_then_apply_updates_multiple_repositories(self) -> None:
        unrelated = self.external / "unrelated.txt"
        unrelated.write_text("concurrent work\n", encoding="utf-8")
        before = (self.external / "AGENTS.md").read_text(encoding="utf-8")

        result, stdout, _ = self.call("sync", "--dry-run")
        self.assertEqual(result, 0)
        self.assertIn("2 file(s) would change", stdout)
        self.assertEqual((self.external / "AGENTS.md").read_text(encoding="utf-8"), before)

        result, _, _ = self.call("sync", "--apply")
        self.assertEqual(result, 0)
        for path in (self.vault / "AGENTS.md", self.external / "AGENTS.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Canonical line one.\n\nCanonical line two.", text)
            self.assertNotIn("Old generated text.", text)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "concurrent work\n")
        self.assertEqual(self.call("check")[0], 0)

    def test_apply_preserves_concurrent_surrounding_edits_in_target_file(self) -> None:
        target = self.external / "AGENTS.md"
        text = target.read_text(encoding="utf-8").replace("# External", "# Concurrent edit")
        target.write_text(text, encoding="utf-8")

        result, stdout, _ = self.call("sync", "--repo", "external", "--apply")

        self.assertEqual(result, 0)
        self.assertIn("target already had local changes", stdout)
        rendered = target.read_text(encoding="utf-8")
        self.assertIn("# Concurrent edit", rendered)
        self.assertIn("Canonical line one.", rendered)
        self.assertIn("After external.", rendered)

    def test_invalid_target_stops_all_selected_writes(self) -> None:
        external = self.external / "AGENTS.md"
        external.write_text(
            external.read_text(encoding="utf-8").replace(
                "<!-- snippet:example:end -->", "<!-- snippet:example:finish -->"
            ),
            encoding="utf-8",
        )
        vault_before = (self.vault / "AGENTS.md").read_text(encoding="utf-8")

        result, stdout, _ = self.call("sync", "--apply")

        self.assertEqual(result, 1)
        self.assertIn("malformed snippet marker", stdout)
        self.assertEqual((self.vault / "AGENTS.md").read_text(encoding="utf-8"), vault_before)

    def test_filters_and_json_status(self) -> None:
        result, stdout, _ = self.call("check", "example", "--repo", "vault", "--json")
        payload = json.loads(stdout)
        self.assertEqual(result, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["targets"]), 1)
        self.assertEqual(payload["targets"][0]["repository"], "vault")
        self.assertEqual(payload["targets"][0]["status"], "stale")

    def test_unsafe_target_path_is_rejected(self) -> None:
        defaults = json.loads((self.config / "defaults.json").read_text(encoding="utf-8"))
        defaults["snippets"]["example"]["targets"][0]["path"] = "../AGENTS.md"
        (self.config / "defaults.json").write_text(json.dumps(defaults), encoding="utf-8")

        result, _, stderr = self.call("check")

        self.assertEqual(result, 2)
        self.assertIn("unsafe target path", stderr)

    def test_missing_duplicate_and_nested_markers_are_rejected(self) -> None:
        cases = {
            "missing": "ordinary text\n",
            "duplicate": (
                "<!-- snippet:example:start -->\none\n<!-- snippet:example:end -->\n"
                "<!-- snippet:example:start -->\ntwo\n<!-- snippet:example:end -->\n"
            ),
            "nested": (
                "<!-- snippet:example:start -->\n"
                "<!-- snippet:other:start -->\n"
                "<!-- snippet:other:end -->\n"
                "<!-- snippet:example:end -->\n"
            ),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                target = self.external / "AGENTS.md"
                target.write_text(text, encoding="utf-8")
                result, output, _ = self.call("sync", "--repo", "external", "--apply")
                self.assertEqual(result, 1)
                self.assertIn("error", output)

    def test_symlink_target_is_rejected(self) -> None:
        target = self.external / "AGENTS.md"
        physical = self.external / "physical.md"
        target.rename(physical)
        target.symlink_to(physical.name)

        result, output, _ = self.call("check", "--repo", "external")

        self.assertEqual(result, 1)
        self.assertIn("physical existing file", output)


if __name__ == "__main__":
    unittest.main()
