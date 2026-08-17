from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "machine.py"
SPEC = importlib.util.spec_from_file_location("machine", SCRIPT)
assert SPEC and SPEC.loader
machine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(machine)


class MachineTests(unittest.TestCase):
    def registry(self):
        return {
            "schema_version": 4,
            "primary_machine_id": "local-box",
            "machines": [
                {
                    "id": "local-box",
                    "display_name": "Local Box",
                    "enabled": True,
                    "role": "primary",
                    "platform": "macos",
                    "transport": "local",
                    "home": "/Users/matt",
                    "wireguard_address": "10.13.13.2",
                    "global_agents_eligible": True,
                },
                {
                    "id": "linux-box",
                    "display_name": "Linux Box",
                    "enabled": True,
                    "role": "worker",
                    "platform": "linux",
                    "transport": "ssh",
                    "ssh_alias": "linux-box",
                    "home": "/home/matt",
                    "wireguard_address": "10.13.13.10",
                    "global_agents_eligible": True,
                    "vault_sync": {
                        "enabled": False,
                        "required": False,
                    },
                    "vnc": {
                        "kind": "ssh-novnc",
                        "remote_host": "127.0.0.1",
                        "remote_port": 6080,
                        "default_local_port": 6080,
                        "health_path": "/vnc.html",
                        "open_path": "/vnc.html?autoconnect=1",
                    },
                },
                {
                    "id": "old-box",
                    "display_name": "Old Box",
                    "enabled": False,
                    "role": "worker",
                    "platform": "linux",
                    "transport": "ssh",
                    "ssh_alias": "old-box",
                    "home": "/home/old",
                    "global_agents_eligible": False,
                },
            ],
        }

    def write_registry(self, directory: str) -> Path:
        path = Path(directory) / "machines.json"
        path.write_text(json.dumps(self.registry()), encoding="utf-8")
        return path

    def test_load_and_resolve_by_id_or_display_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = machine.load_registry(self.write_registry(temporary))
        self.assertEqual(machine.resolve_machine(registry, "linux-box")["ssh_alias"], "linux-box")
        self.assertEqual(machine.resolve_machine(registry, "Linux Box")["id"], "linux-box")

    def test_unknown_and_disabled_fail(self):
        registry = self.registry()
        with self.assertRaisesRegex(machine.MachineError, "unknown machine"):
            machine.resolve_machine(registry, "missing")
        with self.assertRaisesRegex(machine.MachineError, "disabled"):
            machine.resolve_machine(registry, "old-box")

    def test_default_port_falls_back_but_explicit_occupied_fails(self):
        with mock.patch.object(machine, "port_available", return_value=False):
            with mock.patch.object(machine.socket, "socket") as socket_class:
                candidate = socket_class.return_value.__enter__.return_value
                candidate.getsockname.return_value = ("127.0.0.1", 49152)
                self.assertEqual(machine.choose_port(6080), 49152)

    def test_vnc_parser_supports_control_modes(self):
        args = machine.build_parser().parse_args(["vnc", "linux-box", "--status"])
        self.assertTrue(args.status)
        args = machine.build_parser().parse_args(["vnc", "linux-box", "--stop"])
        self.assertTrue(args.stop)

    def test_schema_requires_primary_role_and_rejects_linux_vault_checkout(self):
        registry = self.registry()
        registry["primary_machine_id"] = "linux-box"
        with self.assertRaisesRegex(machine.MachineError, "must reference a primary"):
            machine.validate_registry(registry)
        registry = self.registry()
        registry["machines"][1]["vault_sync"] = {
            "enabled": True,
            "checkout": "sparse",
            "repo_path": "/home/matt/Code/vault",
            "sparse_paths": ["_system"],
        }
        with self.assertRaisesRegex(machine.MachineError, "must not enable Vault"):
            machine.validate_registry(registry)

    def test_schema_rejects_invalid_wireguard_address(self):
        registry = self.registry()
        registry["machines"][1]["wireguard_address"] = "not-an-address"
        with self.assertRaisesRegex(machine.MachineError, "invalid WireGuard address"):
            machine.validate_registry(registry)

    def test_schema_rejects_worker_mac_vault_git_even_when_sync_is_disabled(self):
        registry = self.registry()
        registry["machines"].append(
            {
                "id": "worker-mac",
                "display_name": "Worker Mac",
                "enabled": False,
                "role": "worker",
                "platform": "macos",
                "transport": "ssh",
                "ssh_alias": "worker-mac",
                "home": "/Users/worker",
                "vault_sync": {
                    "enabled": False,
                    "checkout": "full",
                    "repo_path": "/Users/worker/Vault",
                    "git_dir": "/Users/worker/.local/share/vault-git/Vault.git",
                },
            }
        )
        with self.assertRaisesRegex(machine.MachineError, "Gitless iCloud"):
            machine.validate_registry(registry)

    def test_new_registry_and_linux_worker_disable_vault_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = Path(temporary) / "machines.json"
            init_args = machine.build_parser().parse_args([
                "--registry", str(registry_path), "init",
                "--id", "primary", "--display-name", "Primary",
                "--platform", "macos", "--apply",
            ])
            self.assertEqual(machine.command_init(init_args), 0)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertNotIn("default_sparse_paths", registry["vault_sync"])

            worker_args = machine.build_parser().parse_args([
                "--registry", str(registry_path), "register-worker",
                "--id", "worker", "--display-name", "Worker",
                "--platform", "linux", "--ssh-alias", "worker",
                "--home", "/home/worker",
                "--apply",
            ])
            self.assertEqual(machine.command_register_worker(worker_args, registry), 0)
            written = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertFalse(written["machines"][-1]["enabled"])
            self.assertEqual(
                written["machines"][-1]["vault_sync"],
                {"enabled": False, "required": False},
            )
            self.assertEqual(
                written["machines"][-1]["private_notes_path"],
                "_system/local/skills/infra-code-folder-and-computer-topology/"
                "private/My Machines/worker.md",
            )

    def test_new_macos_worker_uses_gitless_icloud_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = Path(temporary) / "machines.json"
            init_args = machine.build_parser().parse_args([
                "--registry", str(registry_path), "init",
                "--id", "primary", "--display-name", "Primary",
                "--platform", "macos", "--apply",
            ])
            self.assertEqual(machine.command_init(init_args), 0)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            worker_args = machine.build_parser().parse_args([
                "--registry", str(registry_path), "register-worker",
                "--id", "worker-mac", "--display-name", "Worker Mac",
                "--platform", "macos", "--ssh-alias", "worker-mac",
                "--home", "/Users/worker",
                "--repo-path", "/Users/worker/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault",
                "--apply",
            ])
            self.assertEqual(machine.command_register_worker(worker_args, registry), 0)
            written = json.loads(registry_path.read_text(encoding="utf-8"))
            sync = written["machines"][-1]["vault_sync"]
            self.assertEqual(sync["checkout"], "icloud")
            self.assertNotIn("git_dir", sync)
            self.assertNotIn("sparse_paths", sync)

    def test_identify_writes_machine_local_file_for_icloud_worker(self):
        registry = self.registry()
        registry["machines"].append(
            {
                "id": "worker-mac",
                "display_name": "Worker Mac",
                "enabled": False,
                "role": "worker",
                "platform": "macos",
                "transport": "ssh",
                "ssh_alias": "worker-mac",
                "home": "/Users/worker",
                "vault_sync": {
                    "enabled": True,
                    "checkout": "icloud",
                    "repo_path": "/Users/worker/Vault",
                },
            }
        )
        args = machine.build_parser().parse_args(
            ["identify", "worker-mac", "--root", "/tmp/vault", "--apply"]
        )
        with tempfile.TemporaryDirectory() as temporary:
            identity = Path(temporary) / "machine-id"
            with mock.patch.object(machine, "DEFAULT_MACHINE_ID_PATH", identity):
                self.assertEqual(machine.command_identify(args, registry), 0)
            self.assertEqual(identity.read_text(encoding="utf-8"), "worker-mac\n")
            self.assertEqual(identity.stat().st_mode & 0o777, 0o600)

    def test_ssh_command_forwarding(self):
        registry = self.registry()
        args = machine.build_parser().parse_args(["ssh", "linux-box", "--", "uname", "-a"])
        with mock.patch.object(machine.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(machine.command_ssh(args, registry), 0)
        self.assertEqual(run.call_args.args[0], ["ssh", "-o", "ConnectTimeout=10", "linux-box", "--", "uname", "-a"])


if __name__ == "__main__":
    unittest.main()
