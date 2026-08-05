#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("worker_bootstrap", SCRIPT_DIR / "worker_bootstrap.py")
assert SPEC and SPEC.loader
worker_bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker_bootstrap
SPEC.loader.exec_module(worker_bootstrap)


class WorkerBootstrapTests(unittest.TestCase):
    def shell(self, cwd: Path, *args: str) -> str:
        return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="worker-bootstrap-")
        base = Path(self.temp.name)
        self.root = base / "vault"
        git_dir = base / "external.git"
        self.root.mkdir()
        self.shell(base, "git", "init", "-b", "master", "--separate-git-dir", str(git_dir), str(self.root))
        self.shell(self.root, "git", "config", "user.name", "Test")
        self.shell(self.root, "git", "config", "user.email", "test@example.com")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_versioned_hooks_work_with_external_git_directory(self) -> None:
        hooks = self.root / ".githooks"
        hooks.mkdir()
        for name in ("post-commit", "post-checkout", "post-merge", "post-rewrite", "pre-push"):
            (hooks / name).write_text("#!/bin/sh\nexit 0\n")
        worker_bootstrap.install_hooks(self.root, apply=True)
        self.assertEqual(self.shell(self.root, "git", "config", "--get", "core.hooksPath"), ".githooks")
        self.assertTrue(all((hooks / name).stat().st_mode & 0o111 for name in ("post-commit", "pre-push")))

    def test_bootstrap_script_has_no_background_git_automation(self) -> None:
        worker = {
            "id": "worker",
            "vault_sync": {
                "repo_path": "/home/test/Code/vault",
                "sparse_paths": [".agents", "_system", ".githooks"],
            },
        }
        script = worker_bootstrap.bootstrap_script(worker, "https://example.com/vault.git")
        self.assertIn('/opt/homebrew/bin:/usr/local/bin:$PATH', script)
        self.assertIn("git sparse-checkout set", script)
        self.assertIn("worker_bootstrap.py", script)
        for forbidden in ("systemctl", "launchctl", "git push", "vault-worker-sync"):
            self.assertNotIn(forbidden, script)

    def test_disabled_worker_requires_explicit_provisioning_flag(self) -> None:
        worker = {
            "id": "worker",
            "display_name": "Worker",
            "enabled": False,
            "role": "worker",
            "platform": "macos",
            "transport": "ssh",
            "ssh_alias": "worker",
            "home": "/Users/test",
            "global_agents_eligible": True,
            "vault_sync": {
                "enabled": True,
                "checkout": "sparse",
                "repo_path": "/Users/test/Code/vault",
                "sparse_paths": [".agents", "_system", ".githooks"],
            },
        }
        registry = {
            "schema_version": 3,
            "primary_machine_id": "primary",
            "machines": [
                {
                    "id": "primary",
                    "display_name": "Primary",
                    "enabled": True,
                    "role": "primary",
                    "platform": "macos",
                    "transport": "local",
                    "home": "/Users/primary",
                    "global_agents_eligible": True,
                },
                worker,
            ],
        }

        with self.assertRaisesRegex(worker_bootstrap.machine_registry.MachineError, "disabled"):
            worker_bootstrap.bootstrap_worker(self.root, registry, "worker", apply=False)

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            worker_bootstrap.bootstrap_worker(
                self.root,
                registry,
                "worker",
                apply=False,
                provision_disabled=True,
            )
        self.assertIn("DRY RUN: bootstrap worker", stdout.getvalue())

    def test_provision_disabled_flag_refuses_enabled_worker(self) -> None:
        registry = {
            "schema_version": 3,
            "primary_machine_id": "primary",
            "machines": [
                {
                    "id": "primary",
                    "display_name": "Primary",
                    "enabled": True,
                    "role": "primary",
                    "platform": "macos",
                    "transport": "local",
                    "home": "/Users/primary",
                    "global_agents_eligible": True,
                },
                {
                    "id": "worker",
                    "display_name": "Worker",
                    "enabled": True,
                    "role": "worker",
                    "platform": "macos",
                    "transport": "ssh",
                    "ssh_alias": "worker",
                    "home": "/Users/test",
                    "global_agents_eligible": True,
                    "vault_sync": {
                        "enabled": True,
                        "checkout": "sparse",
                        "repo_path": "/Users/test/Code/vault",
                        "sparse_paths": [".agents", "_system", ".githooks"],
                    },
                },
            ],
        }

        with self.assertRaisesRegex(worker_bootstrap.WorkerBootstrapError, "already enabled"):
            worker_bootstrap.bootstrap_worker(
                self.root,
                registry,
                "worker",
                apply=False,
                provision_disabled=True,
            )

    def test_versioned_hooks_do_not_push_or_start_remote_sync(self) -> None:
        post_commit = (VAULT_ROOT / ".githooks/post-commit").read_text()
        self.assertIn("git lfs post-commit", post_commit)
        checkout_hooks = "\n".join(
            (VAULT_ROOT / f".githooks/{name}").read_text()
            for name in ("post-checkout", "post-merge", "post-rewrite")
        )
        self.assertIn("project-auto-skills", checkout_hooks)
        self.assertIn("sync_skills.py", checkout_hooks)
        all_hooks = post_commit + checkout_hooks
        for forbidden in ("git push", "ssh ", "vault-worker-sync"):
            self.assertNotIn(forbidden, all_hooks)


if __name__ == "__main__":
    unittest.main()
