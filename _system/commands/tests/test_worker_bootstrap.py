#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
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

    def test_bootstrap_script_rejects_linux_worker(self) -> None:
        worker = {
            "id": "worker",
            "platform": "linux",
            "home": "/home/test",
            "roots": {"code": "~/Code", "vault": None},
            "vault": {"enabled": False, "checkout_mode": "none", "required": False},
        }
        with self.assertRaisesRegex(
            worker_bootstrap.WorkerBootstrapError, "Mac/iCloud-only"
        ):
            worker_bootstrap.bootstrap_script(worker)

    def test_icloud_bootstrap_removes_worker_git_and_keeps_pointer_dangling(self) -> None:
        worker = {
            "id": "worker-mac",
            "platform": "macos",
            "home": "/Users/test",
            "roots": {
                "code": "~/Code",
                "vault": "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault",
            },
            "vault": {"enabled": True, "checkout_mode": "icloud-gitless", "required": True},
        }
        script = worker_bootstrap.bootstrap_script(worker)
        self.assertIn("-flags +dataless", script)
        self.assertIn("Vault.git-disabled-", script)
        self.assertIn(".config/vault/machine-id", script)
        self.assertIn("worker iCloud vault still resolves as a Git worktree", script)
        self.assertIn("block-worker --machine-id worker-mac", script)
        self.assertIn("refresh_schedule.py", script)
        for forbidden in (
            "git clone", "git checkout", "git reset", "git lfs pull",
            "git init", "git fetch", "git config --local",
        ):
            self.assertNotIn(forbidden, script)

    def test_linux_worker_bootstrap_is_disabled(self) -> None:
        worker = {
            "id": "worker",
            "display_name": "Worker",
            "enabled": False,
            "role": "worker",
            "platform": "linux",
            "transport": "ssh",
            "ssh_alias": "worker",
            "home": "/home/test",
            "global_agents_eligible": True,
            "roots": {"code": "~/Code", "vault": None},
            "vault": {"enabled": False, "checkout_mode": "none", "required": False},
        }
        registry = {
            "schema_version": 7,
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
                    "roots": {"code": "~/Code", "vault": "~/Vault"},
                    "vault": {"enabled": True, "checkout_mode": "primary-external-git", "required": True},
                    "global_agents_eligible": True,
                },
                worker,
            ],
        }

        with self.assertRaisesRegex(worker_bootstrap.WorkerBootstrapError, "bootstrap disabled"):
            worker_bootstrap.bootstrap_worker(
                self.root,
                registry,
                "worker",
                apply=False,
                provision_disabled=True,
            )

    def test_provision_disabled_flag_refuses_enabled_worker(self) -> None:
        registry = {
            "schema_version": 7,
            "primary_machine_id": "primary",
            "machines": [
                {
                    "id": "primary",
                    "display_name": "Primary",
                    "enabled": True,
                    "role": "primary",
                    "platform": "linux",
                    "transport": "local",
                    "home": "/Users/primary",
                    "roots": {"code": "~/Code", "vault": "~/Vault"},
                    "vault": {"enabled": True, "checkout_mode": "primary-external-git", "required": True},
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
                    "home": "/home/test",
                    "global_agents_eligible": True,
                    "roots": {"code": "~/Code", "vault": "/Users/test/Vault"},
                    "vault": {"enabled": True, "checkout_mode": "icloud-gitless", "required": True},
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

    def test_macos_worker_refuses_sparse_code_vault(self) -> None:
        worker = {
            "id": "worker-mac",
            "display_name": "Worker Mac",
            "enabled": True,
            "role": "worker",
            "platform": "macos",
            "transport": "ssh",
            "ssh_alias": "worker-mac",
            "home": "/Users/test",
            "global_agents_eligible": False,
            "roots": {"code": "~/Code", "vault": "/Users/test/Code/vault"},
            "vault": {"enabled": True, "checkout_mode": "sparse", "required": True},
        }
        registry = {
            "schema_version": 7,
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
                    "roots": {"code": "~/Code", "vault": "~/Vault"},
                    "vault": {"enabled": True, "checkout_mode": "primary-external-git", "required": True},
                    "global_agents_eligible": True,
                },
                worker,
            ],
        }

        with self.assertRaisesRegex(worker_bootstrap.WorkerBootstrapError, "Mac/iCloud-only"):
            worker_bootstrap.bootstrap_worker(self.root, registry, "worker-mac", apply=False)

    def test_versioned_hooks_do_not_push_or_start_remote_sync(self) -> None:
        post_commit = (VAULT_ROOT / ".githooks/post-commit").read_text()
        self.assertIn("git lfs post-commit", post_commit)
        checkout_hooks = "\n".join(
            (VAULT_ROOT / f".githooks/{name}").read_text()
            for name in ("post-checkout", "post-merge", "post-rewrite")
        )
        self.assertIn("agents/_package/src/sync_agents.py", checkout_hooks)
        all_hooks = post_commit + checkout_hooks
        for forbidden in ("git push", "ssh ", "vault-worker-sync"):
            self.assertNotIn(forbidden, all_hooks)


if __name__ == "__main__":
    unittest.main()
