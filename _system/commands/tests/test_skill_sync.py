#!/usr/bin/env python3
"""Tests for generated vault skill catalog sync."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


AGENT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "agents/_package/src"
sys.path.insert(0, str(AGENT_SCRIPTS_DIR))

import sync_skills  # noqa: E402
import sync_agents  # noqa: E402


class SkillSyncTests(unittest.TestCase):
    def sync(self, root: Path, home: Path, apply: bool, **kwargs: object) -> int:
        return sync_skills.sync(
            root,
            home,
            apply,
            manage_agent_configuration=False,
            **kwargs,
        )

    def roots(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp) / "vault"
        home = Path(tmp) / "home"
        for name in ("skills/auto", "skills/manual", "skills/github", "skills/catalog"):
            (root / "_system/agents" / name).mkdir(parents=True)
        home.mkdir()
        return root, home

    def skill(
        self,
        root: Path,
        source: str,
        relative: str,
        name: str | None = None,
        title: str | None = None,
    ) -> Path:
        path = root / "_system/agents" / source / relative
        path.mkdir(parents=True)
        declared = name or path.name
        category = relative.split("/", 1)[0]
        category_title = sync_skills.CATEGORY_TOKENS.get(category, ("", category.lstrip("_").title()))[1]
        heading = title or f"{category_title} · Example"
        (path / "SKILL.md").write_text(
            f"---\nname: {declared}\n---\n\n# {heading}\n", encoding="utf-8"
        )
        return path

    def registry(self, root: Path, repositories: dict[str, object]) -> Path:
        path = (
            root
            / "_system/agents/_package/instance/fleet/workspaces.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        workspace_repositories: dict[str, object] = {}
        workspace_projections: dict[str, object] = {}
        for repo_id, raw in repositories.items():
            entry = dict(raw) if isinstance(raw, dict) else raw
            if isinstance(entry, dict):
                projections = entry.pop("skill_projections", [])
                if projections:
                    workspace_projections[repo_id] = projections
                raw_path = entry.get("path")
                if isinstance(raw_path, str) and Path(raw_path).is_absolute():
                    entry["path"] = Path(raw_path).relative_to(root.parent).as_posix()
            workspace_repositories[repo_id] = entry
        path.write_text(
            json.dumps({"schema_version": 2, "entries": workspace_repositories}) + "\n",
            encoding="utf-8",
        )
        machines = root / "_system/agents/_package/instance/fleet/machines.json"
        machines.write_text(
            json.dumps({
                "schema_version": 7,
                "primary_machine_id": "primary",
                "vault_git": {
                    "owner_machine_id": "primary",
                    "refresh_owner_machine_id": "primary",
                    "remote": "origin",
                    "branch": "master",
                },
                "machines": [{
                    "id": "primary",
                    "display_name": "Primary",
                    "enabled": True,
                    "role": "primary",
                    "platform": "macos",
                    "transport": "local",
                    "home": str(root.parent),
                    "roots": {"code": str(root.parent), "vault": str(root)},
                    "vault": {"enabled": True, "checkout_mode": "primary-external-git", "required": True},
                }],
            }) + "\n",
            encoding="utf-8",
        )
        selection = root / "_system/agents/_package/instance/skills/sources.json"
        selection.parent.mkdir(parents=True, exist_ok=True)
        selection.write_text(
            json.dumps({
                "schema_version": 3,
                "repos": [],
                "repository_skills": workspace_projections,
            }) + "\n",
            encoding="utf-8",
        )
        return path

    def repo_skill(self, repo: Path, relative: str, body: str = "") -> Path:
        path = repo / relative
        path.mkdir(parents=True)
        name = path.name
        (path / "SKILL.md").write_text(
            f"---\nname: {name}\n---\n\n# {name}\n\n{body}", encoding="utf-8"
        )
        return path

    def test_recursive_groups_are_flattened(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            source = self.skill(root, "skills/auto", "_code/_python/code-example")
            self.sync(root, home, apply=True)
            link = root / "_system/agents/skills/catalog/code-example"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), source.resolve())

    def test_group_and_frontmatter_names_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/auto", "Code/code-example")
            with self.assertRaisesRegex(sync_skills.SyncError, "_lower-kebab"):
                sync_skills.scan_source(root / "_system/agents/skills/auto", "auto")
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/auto", "_code/code-example", name="wrong")
            with self.assertRaisesRegex(sync_skills.SyncError, "mismatch"):
                sync_skills.scan_source(root / "_system/agents/skills/auto", "auto")

    def test_duplicate_names_fail_before_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "skills/auto", "_code/code-example")
            self.skill(root, "skills/manual", "_code/code-example")
            with self.assertRaisesRegex(sync_skills.SyncError, "Duplicate skill"):
                self.sync(root, home, apply=True)
            self.assertEqual(list((root / "_system/agents/skills/catalog").iterdir()), [])

    def test_dry_run_is_pure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            skill = self.skill(root, "skills/manual", "_code/code-example")
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.sync(root, home, apply=False)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertFalse((skill / "agents/openai.yaml").exists())

    def test_snapshot_preview_uses_planned_repository_projection_without_writing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            self.repo_skill(repo, ".agents/skills/l-example")
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "auto"}
                        ],
                    }
                },
            )

            bundle = sync_agents.build_skill_snapshot_bundle(
                root,
                require_repo_sources=False,
            )

            self.assertIn("repo-example", bundle.manifest)
            self.assertFalse(
                (root / "_system/agents/skills/projected/repo/repo-example").exists()
            )

    def test_policy_is_created_and_existing_metadata_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            auto = self.skill(root, "skills/auto", "_code/code-auto-example")
            manual = self.skill(root, "skills/manual", "_code/code-manual-example")
            metadata = auto / "agents/openai.yaml"
            metadata.parent.mkdir()
            metadata.write_text("interface:\n  short_description: Example\npolicy:\n  allow_implicit_invocation: false\n")
            self.sync(root, home, apply=True)
            self.assertIn("short_description: Example", metadata.read_text())
            self.assertNotIn("display_name:", metadata.read_text())
            self.assertIn("allow_implicit_invocation: true", metadata.read_text())
            self.assertIn("allow_implicit_invocation: false", (manual / "agents/openai.yaml").read_text())

    def test_stale_links_removed_and_real_collision_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "skills/auto", "_code/code-example")
            stale = root / "_system/agents/skills/catalog/example"
            stale.symlink_to("../../skills/auto/_code/example")
            self.sync(root, home, apply=True)
            self.assertFalse(stale.is_symlink())
            collision = root / "_system/agents/skills/catalog/real-content"
            collision.mkdir()
            with self.assertRaisesRegex(sync_skills.SyncError, "Unexpected real content"):
                self.sync(root, home, apply=False)

    def test_old_catalog_and_discovery_links_are_removed_in_one_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "skills/auto", "_code/code-example")
            old_source = root / "retired/example"
            old_source.mkdir(parents=True)
            catalog = root / "_system/agents/skills/catalog"
            (catalog / "example").symlink_to(old_source)
            discovery = home / ".agents/skills"
            discovery.mkdir(parents=True)
            (discovery / "example").symlink_to(catalog / "example")

            self.sync(root, home, apply=True)

            self.assertFalse((catalog / "example").is_symlink())
            self.assertFalse((discovery / "example").is_symlink())
            self.assertTrue((discovery / "code-example").is_symlink())
            self.assertEqual(self.sync(root, home, apply=False), 0)

    def test_global_links_migrate_without_ingesting_or_deleting_unmanaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            self.skill(root, "skills/auto", "_code/code-example")
            catalog = root / "_system/agents/skills/catalog"
            claude = home / ".claude"
            claude.mkdir()
            (claude / "skills").symlink_to(catalog)
            agents = home / ".agents/skills"
            agents.mkdir(parents=True)
            unrelated = agents / "unrelated"
            unrelated.mkdir()
            (unrelated / "KEEP").write_text("mine\n")
            self.sync(root, home, apply=True)
            self.assertTrue((claude / "skills").is_dir())
            self.assertFalse((claude / "skills").is_symlink())
            self.assertTrue((claude / "skills/code-example").is_symlink())
            self.assertEqual((unrelated / "KEEP").read_text(), "mine\n")
            self.assertFalse((root / "_system/agents/skills/auto/unrelated").exists())

    def test_dependency_choice_repairs_stale_marker_without_rewriting_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            skill = self.skill(root, "skills/auto", "_creative/creative-example")
            marker = {
                "managed_by": "ctx9-agents sync",
                "repo_id": "example",
                "source": "skills/example",
                "target": "_system/agents/skills/manual/creative-example",
                "type": "manual-skill",
                "title_override": "Creative · Example",
            }
            (skill / sync_skills.MARKER).write_text(json.dumps(marker) + "\n")
            config = root / "_system/agents/_package/instance/skills/sources.json"
            config.parent.mkdir(parents=True)
            choice = {
                "schema_version": 3,
                "repos": [{
                    "id": "example",
                    "github": "example/repo",
                    "skills": [{
                        "source": "skills/example",
                        "mode": "auto",
                        "group": "_creative",
                        "name": "creative-example",
                        "title": "Creative · Example",
                    }],
                }],
                "repository_skills": {},
            }
            config.write_text(json.dumps(choice) + "\n")
            self.sync(root, home, apply=True)
            self.assertEqual(json.loads(config.read_text()), choice)
            updated_marker = json.loads((skill / sync_skills.MARKER).read_text())
            self.assertEqual(updated_marker["type"], "auto-skill")
            self.assertEqual(updated_marker["title_override"], "Creative · Example")

    def test_duplicate_dependency_projection_names_fail_without_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            config = root / "_system/agents/_package/instance/skills/sources.json"
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "repos": [
                            {
                                "id": "one",
                                "github": "example/one",
                                "skills": [
                                    {"source": "skills/a", "mode": "auto", "group": "_code", "name": "code-example"}
                                ],
                            },
                            {
                                "id": "two",
                                "github": "example/two",
                                "skills": [
                                    {"source": "skills/b", "group": "_code", "name": "code-example"}
                                ],
                            },
                        ],
                        "repository_skills": {},
                    }
                )
                + "\n"
            )
            with self.assertRaisesRegex(sync_skills.SyncError, "Duplicate dependency skill"):
                self.sync(root, home, apply=True)
            self.assertEqual(list((root / "_system/agents/skills/catalog").iterdir()), [])

    def test_category_prefix_and_infrastructure_exception_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/auto", "_infrastructure/infra-example", title="Infra · Example")
            skills = sync_skills.scan_source(root / "_system/agents/skills/auto", "auto")
            self.assertEqual([skill.name for skill in skills], ["infra-example"])
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/auto", "_infrastructure/infrastructure-example", title="Infra · Example")
            with self.assertRaisesRegex(sync_skills.SyncError, "category prefix 'infra'"):
                sync_skills.scan_source(root / "_system/agents/skills/auto", "auto")

    def test_distinctive_pack_prefixes_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(
                root,
                "skills/manual",
                "_claude-seo/claude-seo-audit",
                title="Claude SEO · Audit",
            )
            self.skill(
                root,
                "skills/manual",
                "_claude-seo/claude-seo",
                title="Claude SEO · Universal Audit",
            )
            self.skill(
                root,
                "skills/manual",
                "_corey-marketing-skills/corey-analytics",
                title="Corey Marketing Skills · Analytics",
            )
            skills = sync_skills.scan_source(
                root / "_system/agents/skills/manual", "manual"
            )
            self.assertEqual(
                [skill.name for skill in skills],
                ["claude-seo", "claude-seo-audit", "corey-analytics"],
            )

    def test_vault_root_skill_uses_exact_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/auto", "_vault/vault", title="Vault")
            skills = sync_skills.scan_source(root / "_system/agents/skills/auto", "auto")
            self.assertEqual([skill.name for skill in skills], ["vault"])
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/auto", "_vault/vault", title="Vault · Vault")
            with self.assertRaisesRegex(sync_skills.SyncError, "Root skill H1 must be exactly"):
                sync_skills.scan_source(root / "_system/agents/skills/auto", "auto")

    def test_nested_pack_projection_marker_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            skill = self.skill(
                root,
                "skills/manual",
                "_matt-p-skills/_engineering/mp-review",
                title="Matt P Skills · Engineering · Review",
            )
            marker = skill.parent / sync_skills.MARKER
            marker.write_text("{}\n")

            skills = sync_skills.scan_source(
                root / "_system/agents/skills/manual", "manual"
            )

            self.assertEqual([item.name for item in skills], ["mp-review"])

    def test_big_endian_h1_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            self.skill(root, "skills/manual", "_video/video-example", title="Example Video")
            with self.assertRaisesRegex(sync_skills.SyncError, "big-endian hierarchy"):
                sync_skills.scan_source(root / "_system/agents/skills/manual", "manual")

    def test_descriptive_capability_names_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _home = self.roots(tmp)
            skill = self.skill(
                root,
                "skills/manual",
                "_spreadsheets/spreadsheets-update-financial-model-from-statements",
                title="Spreadsheets · Update Financial Model from Statements",
            )
            skills = sync_skills.scan_source(root / "_system/agents/skills/manual", "manual")
            self.assertEqual(
                [item.name for item in skills],
                ["spreadsheets-update-financial-model-from-statements"],
            )
            self.assertEqual(skill.name, "spreadsheets-update-financial-model-from-statements")

    def test_repo_projection_materializes_rewrites_and_copies_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "business"
            first = self.repo_skill(
                repo,
                ".agents/skills/l-debugging",
                "Use $l-tracing.\n",
            )
            tracing = self.repo_skill(repo, ".agents/skills/l-tracing")
            references = first / "references"
            references.mkdir()
            (references / "notes.md").write_text("Also use $l-tracing.\n")
            metadata = first / "agents/openai.yaml"
            metadata.parent.mkdir()
            metadata.write_text("policy:\n  allow_implicit_invocation: false\n")
            self.registry(
                root,
                {
                    "business": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-debugging", "mode": "auto"},
                            {"source": ".agents/skills/l-tracing", "mode": "auto"},
                        ],
                    }
                },
            )

            self.sync(root, home, apply=True)

            projected = (
                root
                / "_system/agents/skills/projected/business/business-debugging"
            )
            skill_text = (projected / "SKILL.md").read_text()
            self.assertIn("name: business-debugging", skill_text)
            self.assertIn("# Impression · Debugging", skill_text)
            self.assertIn("$business-tracing", skill_text)
            self.assertIn(
                "$business-tracing", (projected / "references/notes.md").read_text()
            )
            self.assertIn(
                "allow_implicit_invocation: true",
                (projected / "agents/openai.yaml").read_text(),
            )
            marker = json.loads(
                (projected / sync_skills.working_repo_skills.MARKER).read_text()
            )
            self.assertEqual(marker["source"], ".agents/skills/l-debugging")
            self.assertEqual(marker["mode"], "auto")
            self.assertEqual(
                marker["target"],
                "_system/agents/skills/projected/business/business-debugging",
            )
            self.assertTrue(marker["content_digest"])
            self.assertTrue((root / "_system/agents/skills/catalog/business-debugging").is_symlink())
            self.assertEqual(self.sync(root, home, apply=False), 0)

    def test_repo_projection_dry_run_is_pure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            self.repo_skill(repo, ".agents/skills/l-example")
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "manual"}
                        ],
                    }
                },
            )
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))

            self.sync(root, home, apply=False)

            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertFalse((root / "_system/agents/skills/projected").exists())

    def test_missing_checkout_preserves_valid_tracked_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            self.repo_skill(repo, ".agents/skills/l-example")
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "auto"}
                        ],
                    }
                },
            )
            self.sync(root, home, apply=True)
            repo.rename(Path(tmp) / "repo-unavailable")

            self.assertEqual(self.sync(root, home, apply=False), 0)
            self.assertTrue(
                (root / "_system/agents/skills/projected/repo/repo-example/SKILL.md").is_file()
            )

    def test_working_repo_tree_refuses_unmanaged_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            unmanaged = root / "_system/agents/skills/projected/repo/repo-example"
            unmanaged.mkdir(parents=True)
            (unmanaged / "SKILL.md").write_text(
                "---\nname: repo-example\n---\n\n# Repo · Example\n"
            )

            with self.assertRaisesRegex(
                sync_skills.working_repo_skills.ProjectionError,
                "Unmanaged skill inside generated working-repos tree",
            ):
                self.sync(root, home, apply=False)

    def test_present_checkout_missing_source_without_projection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-missing", "mode": "auto"}
                        ],
                    }
                },
            )
            with self.assertRaisesRegex(
                sync_skills.working_repo_skills.ProjectionError, "managed projection is missing"
            ):
                self.sync(root, home, apply=False)

    def test_present_checkout_missing_source_preserves_projection_but_strict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            source = self.repo_skill(repo, ".agents/skills/l-example")
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "auto"}
                        ],
                    }
                },
            )
            self.sync(root, home, apply=True)
            for path in sorted(source.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            source.rmdir()

            self.assertEqual(self.sync(root, home, apply=False), 0)
            with self.assertRaisesRegex(
                sync_skills.working_repo_skills.ProjectionError,
                "Required projected skill source is missing",
            ):
                self.sync(root, home, apply=False, require_repo_sources=True)

    def test_obsolete_marked_projection_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            self.repo_skill(repo, ".agents/skills/l-example")
            registry = self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "auto"}
                        ],
                    }
                },
            )
            self.sync(root, home, apply=True)
            registry.write_text(
                json.dumps({"schema_version": 2, "entries": {"repo": {"path": "repo"}}}) + "\n"
            )
            (root / "_system/agents/_package/instance/skills/sources.json").write_text(
                json.dumps({
                    "schema_version": 3,
                    "repos": [],
                    "repository_skills": {},
                }) + "\n",
                encoding="utf-8",
            )

            self.sync(root, home, apply=True)

            self.assertFalse((root / "_system/agents/skills/projected/repo").exists())
            self.assertFalse((root / "_system/agents/skills/catalog/repo-example").exists())

    def test_repo_projection_rejects_duplicates_and_dangling_local_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            self.repo_skill(repo, ".agents/skills/l-example")
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "auto"},
                            {"source": ".agents/skills/l-example", "mode": "auto"},
                        ],
                    }
                },
            )
            with self.assertRaisesRegex(
                sync_skills.working_repo_skills.ProjectionError,
                "Duplicate projected skill name",
            ):
                self.sync(root, home, apply=False)

        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.roots(tmp)
            repo = Path(tmp) / "repo"
            self.repo_skill(repo, ".agents/skills/l-example", "Use $l-not-projected.\n")
            self.registry(
                root,
                {
                    "repo": {
                        "path": str(repo),
                        "skill_projections": [
                            {"source": ".agents/skills/l-example", "mode": "auto"}
                        ],
                    }
                },
            )
            with self.assertRaisesRegex(
                sync_skills.working_repo_skills.ProjectionError, "unprojected repository skills"
            ):
                self.sync(root, home, apply=False)


if __name__ == "__main__":
    unittest.main()
