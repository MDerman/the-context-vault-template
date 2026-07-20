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
            "schema_version": 2,
            "machines": [
                {
                    "id": "local-box",
                    "display_name": "Local Box",
                    "enabled": True,
                    "transport": "local",
                    "home": "/Users/matt",
                    "global_agents_eligible": True,
                },
                {
                    "id": "linux-box",
                    "display_name": "Linux Box",
                    "enabled": True,
                    "transport": "ssh",
                    "ssh_alias": "linux-box",
                    "home": "/home/matt",
                    "global_agents_eligible": True,
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

    def test_ssh_command_forwarding(self):
        registry = self.registry()
        args = machine.build_parser().parse_args(["ssh", "linux-box", "--", "uname", "-a"])
        with mock.patch.object(machine.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(machine.command_ssh(args, registry), 0)
        self.assertEqual(run.call_args.args[0], ["ssh", "-o", "ConnectTimeout=10", "linux-box", "--", "uname", "-a"])


if __name__ == "__main__":
    unittest.main()
