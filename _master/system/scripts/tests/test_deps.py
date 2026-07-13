#!/usr/bin/env python3
"""Tests for dependency setup hooks."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import deps  # noqa: E402


def repo(path: Path, setup_script: str | None = None) -> deps.Repo:
    return deps.Repo("example", "https://example.invalid/repo.git", path, "main", None, setup_script, [])


class DependencySetupTests(unittest.TestCase):
    def test_active_skill_projection_uses_directory_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: example\n---\n")
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/example",
                target="_master/agents/skills/example",
                type="active-skill",
                managed=True,
            )
            deps.create_active_skill_projection(root, projection, apply=True)
            target = root / projection.target
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), source.resolve())
            self.assertFalse((target / "SKILL.md").is_symlink())
            self.assertTrue(deps.projection_health(root, projection)["marker"])

    def test_active_skill_projection_migrates_per_file_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: example\n---\n")
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/example",
                target="_master/agents/skills/example",
                type="active-skill",
                managed=True,
            )
            target = root / projection.target
            target.mkdir(parents=True)
            (target / "SKILL.md").symlink_to(source / "SKILL.md")
            deps.write_json(deps.projection_marker(target), deps.marker_payload(projection))

            deps.create_active_skill_projection(root, projection, apply=True)

            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), source.resolve())

    def test_setup_script_must_stay_inside_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "outside.py"
            outside.write_text("pass\n")
            with self.assertRaisesRegex(SystemExit, "must stay inside vault"):
                deps.repo_setup_script(root, repo(root / "checkout", str(outside)))

    def test_status_json_reports_pending_for_missing_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "setup.py"
            script.write_text("pass\n")
            payload = deps.status_payload(root, [repo(root / "missing", "setup.py")])
            self.assertEqual(payload["repos"][0]["setup"]["state"], "pending")
            json.dumps(payload)

    def test_status_json_reports_hook_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "checkout"
            checkout.mkdir()
            (root / "setup.py").write_text("pass\n")
            result = deps.subprocess.CompletedProcess([], 1, "needs repair\n", "")
            with patch.object(deps, "run", return_value=result):
                payload = deps.status_payload(root, [repo(checkout, "setup.py")])
            self.assertEqual(payload["repos"][0]["setup"]["state"], "needs-setup")

    def test_sync_forces_setup_after_repo_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "checkout"
            checkout.mkdir()
            (root / "setup.py").write_text("pass\n")
            item = repo(checkout, "setup.py")
            with (
                patch.object(deps, "sync_repo", return_value=True),
                patch.object(deps, "run_repo_setup") as setup,
            ):
                deps.sync(root, [item], apply=True)
            setup.assert_called_once_with(root, item, True, force_build=True)

    def test_setup_failure_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "checkout"
            checkout.mkdir()
            (root / "setup.py").write_text("pass\n")
            result = deps.subprocess.CompletedProcess([], 2, "", "broken")
            with patch.object(deps, "run", return_value=result):
                with self.assertRaisesRegex(SystemExit, "Dependency setup failed"):
                    deps.run_repo_setup(root, repo(checkout, "setup.py"), True, False)

    def test_setup_dry_run_uses_dry_run_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "checkout"
            checkout.mkdir()
            (root / "setup.py").write_text("pass\n")
            result = deps.subprocess.CompletedProcess([], 0, "ok\n", "")
            with patch.object(deps, "run", return_value=result) as command:
                deps.run_repo_setup(root, repo(checkout, "setup.py"), False, True)
            args = command.call_args.args[0]
            self.assertIn("--dry-run", args)
            self.assertIn("--force-build", args)


if __name__ == "__main__":
    unittest.main()
