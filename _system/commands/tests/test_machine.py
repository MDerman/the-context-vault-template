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
            "schema_version": 7,
            "primary_machine_id": "local-box",
            "vault_git": {
                "owner_machine_id": "local-box",
                "refresh_owner_machine_id": "local-box",
                "remote": "origin",
                "branch": "master",
            },
            "machines": [
                {
                    "id": "local-box",
                    "display_name": "Local Box",
                    "enabled": True,
                    "role": "primary",
                    "platform": "macos",
                    "transport": "local",
                    "home": "/Users/matt",
                    "roots": {"code": "~/Code", "vault": "~/Vault"},
                    "vault": {
                        "enabled": True,
                        "checkout_mode": "primary-external-git",
                        "required": True,
                    },
                    "fleet_shell": {
                        "identity_file": "~/.ssh/local_fleet_ed25519",
                    },
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
                    "roots": {"code": "~/Code", "vault": None},
                    "vault": {"enabled": False, "checkout_mode": "none", "required": False},
                    "fleet_shell": {
                        "identity_file": "~/.ssh/linux_fleet_ed25519",
                    },
                    "global_agents_eligible": True,
                    "machine_access": {
                        "provider": "wireguard",
                        "ssh_user": "matt",
                        "identity_file": "~/.ssh/fleet_ed25519",
                        "lan_host": "linux-box.local",
                        "providers": {
                            "wireguard": {
                                "state": "configured",
                                "host": "10.13.13.10",
                            }
                        },
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
                    "roots": {"code": "~/Code", "vault": None},
                    "vault": {"enabled": False, "checkout_mode": "none", "required": False},
                    "global_agents_eligible": False,
                    "machine_access": {
                        "provider": "tailscale",
                        "ssh_user": "old",
                        "identity_file": "~/.ssh/fleet_ed25519",
                        "providers": {"tailscale": {"state": "pending"}},
                    },
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
        registry["machines"][1]["roots"]["vault"] = "~/Vault"
        registry["machines"][1]["vault"] = {
            "enabled": True,
            "checkout_mode": "sparse",
            "required": True,
        }
        with self.assertRaisesRegex(machine.MachineError, "unsupported Vault checkout mode"):
            machine.validate_registry(registry)

    def test_schema_rejects_invalid_provider_host(self):
        registry = self.registry()
        registry["machines"][1]["machine_access"]["providers"]["wireguard"]["host"] = "not a host"
        with self.assertRaisesRegex(machine.MachineError, "invalid wireguard host"):
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
                "roots": {"code": "~/Code", "vault": "~/Vault"},
                "vault": {
                    "enabled": True,
                    "checkout_mode": "primary-external-git",
                    "required": True,
                },
                "machine_access": {
                    "provider": "wireguard",
                    "ssh_user": "worker",
                    "identity_file": "~/.ssh/fleet_ed25519",
                    "providers": {"wireguard": {"state": "pending"}},
                },
            }
        )
        with self.assertRaisesRegex(machine.MachineError, "primary-external-git"):
            machine.validate_registry(registry)

    def test_schema_accepts_registered_remote_vault_client_and_rejects_bad_source(self):
        registry = self.registry()
        registry["machines"].append(
            {
                "id": "icloud-host",
                "display_name": "iCloud Host",
                "enabled": True,
                "role": "worker",
                "platform": "macos",
                "transport": "ssh",
                "ssh_alias": "icloud-host",
                "home": "/Users/matt",
                "roots": {"code": "~/Code", "vault": "~/Vault"},
                "vault": {
                    "enabled": True,
                    "checkout_mode": "icloud-gitless",
                    "required": True,
                    "remote_access": {"host_enabled": True},
                },
                "machine_access": {
                    "provider": "tailscale",
                    "ssh_user": "matt",
                    "identity_file": "~/.ssh/fleet_ed25519",
                    "providers": {"tailscale": {"state": "configured", "host": "icloud-host.example.test"}},
                },
            }
        )
        client = registry["machines"][1]
        client["roots"]["vault"] = "~/Vault"
        client["vault"] = {
            "enabled": True,
            "checkout_mode": "remote-sshfs",
            "required": True,
            "remote_access": {"source_machine_id": "icloud-host", "writable": True},
        }
        machine.validate_registry(registry)
        client["vault"]["remote_access"]["source_machine_id"] = "linux-box"
        with self.assertRaisesRegex(machine.MachineError, "source itself"):
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
            self.assertEqual(registry["machines"][0]["roots"]["code"], "~/Code")

            worker_args = machine.build_parser().parse_args([
                "--registry", str(registry_path), "register-worker",
                "--id", "worker", "--display-name", "Worker",
                "--platform", "linux", "--ssh-alias", "worker",
                "--home", "/home/worker",
                "--ssh-user", "worker", "--provider", "tailscale",
                "--apply",
            ])
            self.assertEqual(machine.command_register_worker(worker_args, registry), 0)
            written = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertFalse(written["machines"][-1]["enabled"])
            self.assertEqual(
                written["machines"][-1]["vault"],
                {"enabled": False, "checkout_mode": "none", "required": False},
            )
            self.assertEqual(
                written["machines"][-1]["private_notes_path"],
                "_system/agents/_package/instance/skills/config/infra-code-folder-and-computer-topology/"
                "private/My Machines/worker.md",
            )
            self.assertEqual(
                written["machines"][-1]["machine_access"]["providers"]["tailscale"],
                {
                    "state": "pending",
                    "desired_state": {
                        "device_name": "worker",
                        "accept_dns": True,
                        "accept_routes": False,
                        "tailscale_ssh": False,
                    },
                },
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
                "--ssh-user", "worker", "--provider", "wireguard",
                "--vault-root", "/Users/worker/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault",
                "--apply",
            ])
            self.assertEqual(machine.command_register_worker(worker_args, registry), 0)
            written = json.loads(registry_path.read_text(encoding="utf-8"))
            worker = written["machines"][-1]
            self.assertEqual(worker["vault"]["checkout_mode"], "icloud-gitless")
            self.assertEqual(
                worker["roots"]["vault"],
                "/Users/worker/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault",
            )

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
                "roots": {"code": "~/Code", "vault": "/Users/worker/Vault"},
                "vault": {
                    "enabled": True,
                    "checkout_mode": "icloud-gitless",
                    "required": True,
                },
                "machine_access": {
                    "provider": "wireguard",
                    "ssh_user": "worker",
                    "identity_file": "~/.ssh/fleet_ed25519",
                    "providers": {"wireguard": {"state": "pending"}},
                },
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            args = machine.build_parser().parse_args(
                ["identify", "worker-mac", "--root", temporary, "--apply"]
            )
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

    def test_provider_prompt_has_no_default(self):
        with mock.patch("builtins.input", side_effect=["", "tailscale"]):
            self.assertEqual(
                machine.prompt_choice("Provider", machine.ACCESS_PROVIDERS),
                "tailscale",
            )

    def test_setup_creates_disabled_tailscale_worker_and_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_path = root / "_system/agents/_package/instance/fleet/machines.json"
            args = machine.build_parser().parse_args([
                "--registry", str(registry_path),
                "setup", "--root", str(root), "--apply", "--yes", "--no-codex",
            ])
            answers = [
                "primary",
                "Primary Mac",
                "",
                "macos",
                "Worker Air",
                "",
                "tailscale",
                "matt",
                "",
                "",
                "yes",
            ]
            with mock.patch("builtins.input", side_effect=answers):
                with mock.patch.object(machine, "set_primary_identity"):
                    self.assertEqual(machine.command_setup(args), 0)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            worker = registry["machines"][-1]
            self.assertFalse(worker["enabled"])
            self.assertEqual(worker["ssh_alias"], "worker-air")
            self.assertEqual(worker["machine_access"]["provider"], "tailscale")
            self.assertEqual(
                worker["machine_access"]["providers"]["tailscale"],
                {
                    "state": "pending",
                    "desired_state": {
                        "device_name": "worker-air",
                        "accept_dns": True,
                        "accept_routes": False,
                        "tailscale_ssh": False,
                    },
                },
            )
            note = root / worker["private_notes_path"]
            self.assertIn("Personal machine-access provider: tailscale", note.read_text(encoding="utf-8"))

    def test_access_configure_then_switch_keeps_old_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = self.write_registry(temporary)
            registry = machine.load_registry(registry_path)
            configure = machine.build_parser().parse_args([
                "--registry", str(registry_path),
                "access", "configure", "linux-box", "tailscale",
                "--host", "linux-box.example.ts.net", "--client-variant", "linux-package", "--apply",
            ])
            with mock.patch.object(machine, "run_access_renderer"):
                self.assertEqual(machine.command_access_configure(configure, registry), 0)
            configured = machine.load_registry(registry_path)
            switch = machine.build_parser().parse_args([
                "--registry", str(registry_path),
                "access", "switch", "linux-box", "tailscale", "--apply",
            ])
            with mock.patch.object(machine, "run_access_renderer"):
                with mock.patch.object(machine, "verify_route"):
                    with mock.patch.object(machine, "verify_canonical"):
                        self.assertEqual(machine.command_access_switch(switch, configured), 0)
            switched = machine.load_registry(registry_path)
            access = switched["machines"][1]["machine_access"]
            self.assertEqual(access["provider"], "tailscale")
            self.assertIn("wireguard", access["providers"])
            self.assertIn("tailscale", access["providers"])

    def test_access_switch_rolls_registry_back_when_render_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = self.write_registry(temporary)
            registry = machine.load_registry(registry_path)
            registry["machines"][1]["machine_access"]["providers"]["tailscale"] = {
                "state": "configured",
                "host": "linux-box.example.ts.net",
                "desired_state": machine.tailscale_desired_state("linux-box"),
            }
            machine.write_registry(registry_path, registry, True)
            args = machine.build_parser().parse_args([
                "--registry", str(registry_path),
                "access", "switch", "linux-box", "tailscale", "--apply",
            ])
            with mock.patch.object(machine, "verify_route"):
                with mock.patch.object(
                    machine,
                    "run_access_renderer",
                    side_effect=[RuntimeError("render failed"), None],
                ):
                    with self.assertRaisesRegex(machine.MachineError, "restored"):
                        machine.command_access_switch(args, registry)
            restored = machine.load_registry(registry_path)
            self.assertEqual(
                restored["machines"][1]["machine_access"]["provider"],
                "wireguard",
            )

    def test_route_probe_uses_source_fleet_identity_for_target_route(self):
        registry = self.registry()
        command = machine.route_probe_command(
            registry["machines"][0],
            registry["machines"][1],
            "10.13.13.10",
        )
        self.assertIn("IdentityFile=~/.ssh/local_fleet_ed25519", command)
        self.assertIn("HostName=10.13.13.10", command)
        self.assertEqual(command[-2:], ["linux-box", "true"])

    def test_codex_handoff_always_prints_request_when_codex_is_missing(self):
        with mock.patch.object(machine.shutil, "which", return_value=None):
            with mock.patch("builtins.print") as printed:
                machine.offer_codex_handoff(Path("/tmp/vault"), "editable request")
        rendered = "\n".join(str(call.args[0]) for call in printed.call_args_list if call.args)
        self.assertIn("editable request", rendered)
        self.assertIn("not opened", rendered)

    def test_codex_handoff_copies_and_opens_without_submitting(self):
        completed = mock.Mock(returncode=0)
        with mock.patch.object(machine.shutil, "which", return_value="/usr/local/bin/codex"):
            with mock.patch.object(machine.subprocess, "run", return_value=completed) as run:
                machine.offer_codex_handoff(Path("/tmp/vault"), "editable request")
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/local/bin/codex", "login", "status"])
        self.assertEqual(run.call_args_list[1].kwargs["input"], "editable request")
        self.assertEqual(
            run.call_args_list[2].args[0],
            ["/usr/local/bin/codex", "app", "/tmp/vault"],
        )


if __name__ == "__main__":
    unittest.main()
