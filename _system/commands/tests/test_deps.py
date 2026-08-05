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
    def test_auto_skill_projection_uses_policy_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: example\n---\n")
            (source / "references").mkdir()
            (source / "references/example.md").write_text("portable\n")
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/example",
                target="_system/agents/auto-skills/_creative/example",
                type="auto-skill",
                managed=True,
            )
            deps.create_auto_skill_projection(root, projection, apply=True)
            target = root / projection.target
            self.assertTrue(target.is_dir())
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertFalse((target / "SKILL.md").is_symlink())
            self.assertEqual((target / "SKILL.md").read_text(), (source / "SKILL.md").read_text())
            self.assertIn("allow_implicit_invocation: true", (target / "agents/openai.yaml").read_text())
            self.assertTrue(deps.projection_health(root, projection)["marker"])
            self.assertTrue((target / "references").is_dir())
            self.assertFalse((target / "references").is_symlink())
            self.assertEqual((target / "references/example.md").read_text(), "portable\n")

    def test_skill_projection_applies_local_name_and_title_without_changing_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            original = "---\nname: example\ndescription: Example.\n---\n\n# Upstream Title\n\nBody.\n"
            (source / "SKILL.md").write_text(original)
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/example",
                target="_system/agents/auto-skills/_creative/creative-example",
                type="auto-skill",
                managed=True,
                title_override="Creative · Example",
            )

            self.assertTrue(deps.create_auto_skill_projection(root, projection, apply=True))
            target = root / projection.target
            rendered = (target / "SKILL.md").read_text()
            self.assertIn("name: creative-example", rendered)
            self.assertIn("# Creative · Example", rendered)
            self.assertNotIn("# Upstream Title", rendered)
            self.assertNotIn("display_name:", (target / "agents/openai.yaml").read_text())
            self.assertEqual((source / "SKILL.md").read_text(), original)
            self.assertFalse(deps.create_auto_skill_projection(root, projection, apply=True))

    def test_skill_projection_inserts_title_when_upstream_has_no_h1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: example\n---\n\n## Workflow\n\n```sh\n# not a title\n```\n"
            )
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/example",
                target="_system/agents/manual-skills/_code/code-example",
                type="manual-skill",
                managed=True,
                title_override="Code · Example",
            )

            deps.create_manual_skill_projection(root, projection, apply=True)
            rendered = (root / projection.target / "SKILL.md").read_text()
            self.assertIn("---\n\n# Code · Example\n\n## Workflow", rendered)
            self.assertIn("# not a title", rendered)

    def test_skill_pack_projection_prefixes_title_and_preserves_upstream_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: example\ndescription: Example.\n"
                "user-invocable: true\nargument-hint: \"[url]\"\n"
                "---\n\n# SEO Audit\n\nBody.\n"
            )
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/example",
                target=(
                    "_system/agents/manual-skills/_claude-seo/"
                    "claude-seo-example"
                ),
                type="manual-skill",
                managed=True,
            )

            self.assertTrue(deps.create_manual_skill_projection(root, projection, apply=True))
            rendered = (root / projection.target / "SKILL.md").read_text()
            self.assertIn("name: claude-seo-example", rendered)
            self.assertIn("user-invocable: true", rendered)
            self.assertIn('argument-hint: "[url]"', rendered)
            self.assertIn("# Claude SEO · SEO Audit", rendered)

    def test_swan_gtm_pack_uses_registered_title_prefix(self) -> None:
        target = (
            "_system/agents/manual-skills/_swan-gtm-skills/"
            "swan-gtm-reach-out"
        )

        self.assertEqual(
            deps.projection_title_prefix(target),
            "Swan GTM Skills",
        )

    def test_load_config_accepts_optional_projection_title_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / deps.CONFIG_PATH
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "repos": [
                            {
                                "id": "example",
                                "url": "https://example.invalid/repo.git",
                                "path": str(root / "checkout"),
                                "projections": [
                                    {
                                        "source": "skills/example",
                                        "target": "_system/agents/auto-skills/_code/code-example",
                                        "type": "auto-skill",
                                        "title_override": "Code · Example",
                                    }
                                ],
                            }
                        ]
                    }
                )
                + "\n"
            )
            projection = deps.load_config(root)[0].projections[0]
            self.assertEqual(projection.title_override, "Code · Example")

    def test_manual_skill_pack_projects_prefixed_skills_and_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/engineering"
            (source / "review").mkdir(parents=True)
            (source / "tdd").mkdir()
            productivity = checkout / "skills/productivity/grilling"
            productivity.mkdir(parents=True)
            (productivity / "SKILL.md").write_text(
                "---\nname: grilling\ndescription: Ask questions.\n---\n"
            )
            (source / "README.md").write_text(
                "# Engineering\n\n[Review](./review/SKILL.md) then run `/tdd`.\n"
            )
            (source / "review/SKILL.md").write_text(
                "---\nname: review\ndescription: Review code.\n---\n\n"
                "Run `/tdd` and `/grilling`.\n"
            )
            (source / "review/checklist.md").write_text("Use `/tdd`.\n")
            (source / "tdd/SKILL.md").write_text(
                "---\nname: tdd\ndescription: Test first.\n---\n\n# TDD\n"
            )
            projection = deps.Projection(
                repo_id="example",
                repo_path=checkout,
                source="skills/engineering",
                target=(
                    "_system/agents/manual-skills/_matt-p-skills/_engineering"
                ),
                type="manual-skill-pack",
                managed=True,
                skill_prefix="mp-",
                rewrite_skill_sources=(
                    "skills/engineering",
                    "skills/productivity",
                ),
            )

            self.assertTrue(deps.create_manual_skill_pack_projection(root, projection, apply=True))
            target = root / projection.target
            self.assertIn(
                "[Review](./mp-review/SKILL.md)",
                (target / "README.md").read_text(),
            )
            self.assertIn("`/mp-tdd`", (target / "README.md").read_text())
            rendered = (target / "mp-review/SKILL.md").read_text()
            self.assertIn("name: mp-review", rendered)
            self.assertIn("# Matt P Skills · Engineering · Review", rendered)
            self.assertIn("`/mp-tdd`", rendered)
            self.assertIn("`/mp-grilling`", rendered)
            self.assertIn("`/mp-tdd`", (target / "mp-review/checklist.md").read_text())
            self.assertIn(
                "allow_implicit_invocation: false",
                (target / "mp-review/agents/openai.yaml").read_text(),
            )
            self.assertTrue(deps.projection_health(root, projection)["marker"])
            self.assertFalse(deps.create_manual_skill_pack_projection(root, projection, apply=True))

    def test_load_config_accepts_skill_pack_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / deps.CONFIG_PATH
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "repos": [
                            {
                                "id": "example",
                                "url": "https://example.invalid/repo.git",
                                "path": str(root / "checkout"),
                                "projections": [
                                    {
                                        "source": "skills/engineering",
                                        "target": "_system/agents/manual-skills/_pack/_engineering",
                                        "type": "manual-skill-pack",
                                        "skill_prefix": "mp-",
                                        "rewrite_skill_sources": [
                                            "skills/engineering",
                                            "skills/productivity",
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
                )
                + "\n"
            )

            projection = deps.load_config(root)[0].projections[0]
            self.assertEqual(projection.skill_prefix, "mp-")
            self.assertEqual(
                projection.rewrite_skill_sources,
                ("skills/engineering", "skills/productivity"),
            )

    def test_sync_parser_accepts_repeatable_repo_selectors(self) -> None:
        args = deps.parse_args(
            ["sync", "--repo", "one", "--repo", "two", "--apply"]
        )

        self.assertEqual(args.repo_ids, ["one", "two"])
        self.assertTrue(args.apply)

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

    def test_project_auto_skills_does_not_sync_or_build_dependency_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            checkout = Path(tmp) / "checkout"
            source = checkout / "skills/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: example\n---\n")
            projection = deps.Projection(
                repo_id="example", repo_path=checkout, source="skills/example",
                target="_system/agents/auto-skills/_creative/example",
                type="auto-skill", managed=True,
            )
            item = deps.Repo("example", "https://example.invalid/repo.git", checkout, "main", None, None, [projection])
            with patch.object(deps, "sync_repo") as sync_repo:
                with patch.object(deps, "run_repo_setup") as setup:
                    with patch.object(deps, "run_skill_sync"):
                        deps.project_auto_skills(root, [item], apply=True)
            sync_repo.assert_not_called()
            setup.assert_not_called()
            self.assertTrue((root / projection.target / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
