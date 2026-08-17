#!/usr/bin/env python3
"""Focused integration tests for primary-owned agent configuration sync."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
VAULT_ROOT = SCRIPT_DIRECTORY.parents[5]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIRECTORY / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = load_module("agent_configuration_sync", "sync_agent_configuration.py")
WORKER = SCRIPT_DIRECTORY / "agent_configuration_target_worker.py"


class AgentConfigurationSyncTests(unittest.TestCase):
    def create_registry(self) -> dict[str, object]:
        return {
            "schema_version": 99,
            "primary_machine_id": "primary",
            "machines": [
                {
                    "id": "primary",
                    "display_name": "Primary",
                    "enabled": True,
                    "home": "/Users/matt",
                    "role": "primary",
                    "platform": "macos",
                    "wireguard_address": "10.13.13.2",
                },
                {
                    "id": "worker-mac",
                    "display_name": "Worker Mac",
                    "enabled": True,
                    "home": "/Users/matt",
                    "role": "worker",
                    "platform": "macos",
                    "wireguard_address": "10.13.13.11",
                },
                {
                    "id": "linux-worker",
                    "display_name": "Linux Worker",
                    "enabled": True,
                    "home": "/home/matt",
                    "role": "worker",
                    "platform": "linux",
                    "wireguard_address": "10.13.13.10",
                    "vnc": {
                        "kind": "ssh-novnc",
                        "open_path": "/vnc.html?autoconnect=1",
                    },
                },
            ],
        }

    def create_source(self, root: Path) -> tuple[Path, dict[str, object]]:
        source = root / "source"
        (source / ".codex").mkdir(parents=True)
        (source / ".claude").mkdir()
        (source / ".codex/config.toml").write_text(
            f'''model = "gpt-test"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
log_dir = "{source}/logs"

[mcp_servers.computer-use]
enabled = false

[plugins."source-only@paper"]
enabled = true

[marketplaces.paper]
source_type = "git"
source = "https://example.com/source-only.git"
''',
            encoding="utf-8",
        )
        (source / ".claude/settings.json").write_text(
            json.dumps({"model": "test", "hooks": {}, "path": f"{source}/tools"}) + "\n",
            encoding="utf-8",
        )
        config = root / "_system/agents/config"
        (config / "overlays").mkdir(parents=True)
        (config / "AGENTS.md").write_text("Keep it simple.\n", encoding="utf-8")
        template = "Machine {machine_id} at {service_url}.\n{peers}\n{access_guidance}\n"
        for name in ("primary-macos.md", "worker-macos.md", "worker-linux.md"):
            (config / "overlays" / name).write_text(template, encoding="utf-8")
        return source, self.create_registry()

    def run_worker(self, home: Path, files: list[dict[str, object]], suffix: str) -> dict[str, object]:
        payload = {
            "home": str(home),
            "apply": True,
            "verify": False,
            "backup_suffix": suffix,
            "files": files,
        }
        process = subprocess.run(
            ["python3", str(WORKER)],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "HOME": str(home)},
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        return json.loads(process.stdout)

    def test_worker_mac_sync_is_rebased_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, registry = self.create_source(root)
            target = root / "target"
            target.mkdir()
            (target / ".codex").mkdir()
            (target / ".codex/config.toml").write_text(
                '''[plugins."target-only@personal"]
enabled = false

[marketplaces.personal]
source_type = "local"
source = "/target/local/marketplace"
''',
                encoding="utf-8",
            )
            bundle = sync.load_source_bundle(source, root=root, registry=registry)
            machine = {
                "id": "worker-mac",
                "home": str(target),
                "role": "worker",
                "platform": "macos",
            }
            files = sync.rendered_files(bundle, machine)
            first = self.run_worker(target, files, "first")
            self.assertTrue(first["ready"])
            config = (target / ".codex/config.toml").read_text(encoding="utf-8")
            self.assertIn('approval_policy = "never"', config)
            self.assertIn('sandbox_mode = "danger-full-access"', config)
            self.assertIn("[mcp_servers.computer-use]\nenabled = true", config)
            self.assertIn('[plugins."target-only@personal"]\nenabled = false', config)
            self.assertIn('[marketplaces.personal]', config)
            self.assertNotIn("source-only@paper", config)
            self.assertNotIn("source-only.git", config)
            self.assertIn(f'log_dir = "{target}/logs"', config)
            self.assertNotIn(str(source), config)
            self.assertEqual(stat.S_IMODE((target / ".codex/config.toml").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((target / ".codex/AGENTS.md").stat().st_mode), 0o644)
            self.assertTrue((target / ".claude/CLAUDE.md").is_symlink())
            self.assertEqual(os.readlink(target / ".claude/CLAUDE.md"), "../.codex/AGENTS.md")

            (target / ".codex/config.toml").write_text("local drift\n", encoding="utf-8")
            second = self.run_worker(target, files, "second")
            self.assertTrue(second["ready"])
            self.assertTrue((target / ".codex/config.toml.backup-second").is_file())
            third = self.run_worker(target, files, "third")
            self.assertTrue(all(result["status"] == "match" for result in third["results"]))

    def test_role_rendering_uses_registry_addresses_and_linux_novnc_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, registry = self.create_source(root)
            bundle = sync.load_source_bundle(source, root=root, registry=registry)
            rendered = bundle["agents_by_machine"]
            self.assertIn("http://10.13.13.2:<port>", rendered["primary"])
            self.assertIn("http://10.13.13.11:<port>", rendered["worker-mac"])
            self.assertIn("http://10.13.13.10:<port>", rendered["linux-worker"])
            self.assertIn("127.0.0.1:61152", rendered["linux-worker"])

    def test_shared_vault_alias_reconciler_is_dry_run_safe_and_refuses_unmanaged_file(self) -> None:
        shared = sync.global_agent_configuration
        helper_spec = importlib.util.spec_from_file_location(
            "ensure_agent_file_symlinks_test",
            VAULT_ROOT / "_system/bootstrap/agents/ensure-agent-file-symlinks.py",
        )
        assert helper_spec and helper_spec.loader
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        self.assertIs(helper.load_shared(VAULT_ROOT).ensure_agent_paths, shared.ensure_agent_paths)
        sync_spec = importlib.util.spec_from_file_location(
            "sync_skills_shared_agent_test",
            VAULT_ROOT / "_system/agents/sync_skills.py",
        )
        assert sync_spec and sync_spec.loader
        regular_sync = importlib.util.module_from_spec(sync_spec)
        sys.modules[sync_spec.name] = regular_sync
        sync_spec.loader.exec_module(regular_sync)
        self.assertIs(
            regular_sync.global_agent_configuration.ensure_agent_paths,
            shared.ensure_agent_paths,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "AGENTS.md").write_text("Vault instructions\n", encoding="utf-8")
            preview = shared.ensure_agent_paths(root, dry_run=True)
            self.assertFalse(preview["ready"])
            self.assertFalse((root / "CLAUDE.md").exists())
            applied = shared.ensure_agent_paths(root, dry_run=False)
            self.assertTrue(applied["ready"])
            self.assertEqual(os.readlink(root / "CLAUDE.md"), "AGENTS.md")
            (root / "CLAUDE.md").unlink()
            (root / "CLAUDE.md").write_text("unmanaged\n", encoding="utf-8")
            with self.assertRaisesRegex(shared.AgentConfigurationError, "unmanaged"):
                shared.ensure_agent_paths(root, dry_run=True)

    def test_registry_consumers_are_forward_compatible_and_inline_secrets_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "machines.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": 99,
                        "primary_machine_id": "primary",
                        "machines": [{"id": "primary"}],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync.load_registry(registry)["schema_version"], 99)

            source, source_registry = self.create_source(root)
            (source / ".claude/settings.json").write_text(
                json.dumps({"env": {"API_TOKEN": "do-not-copy"}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "credential-like"):
                sync.load_source_bundle(source, root=root, registry=source_registry)


if __name__ == "__main__":
    unittest.main()
