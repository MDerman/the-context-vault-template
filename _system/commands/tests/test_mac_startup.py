#!/usr/bin/env python3
"""Tests for opt-in, machine-specific macOS startup automation."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SCRIPT = SCRIPT_DIR / "mac_startup.py"
SPEC = importlib.util.spec_from_file_location("mac_startup", SCRIPT)
assert SPEC and SPEC.loader
mac_startup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mac_startup
SPEC.loader.exec_module(mac_startup)


def write_fixture(
    root: Path,
    *,
    private_enabled: bool = True,
    topology_enabled: bool = True,
) -> None:
    defaults = root / mac_startup.DEFAULT_CONFIG_RELATIVE
    defaults.parent.mkdir(parents=True)
    defaults.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "enabled": False,
                "label": mac_startup.DEFAULT_LABEL,
                "actions": {
                    "open-applications": False,
                    "remap-tilde-key": False,
                },
                "applications": [],
                "legacy_launch_agents": [],
            }
        ),
        encoding="utf-8",
    )
    private = root / mac_startup.PRIVATE_CONFIG_RELATIVE
    private.parent.mkdir(parents=True)
    private.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "machines": {
                    "mattbook": {
                        "enabled": private_enabled,
                        "actions": {"remap-tilde-key": private_enabled},
                        "legacy_launch_agents": [
                            "com.user.loginscript",
                            "com.typespace.hidutil-keymap",
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    topology = root / mac_startup.TOPOLOGY_REGISTRY_RELATIVE
    topology.parent.mkdir(parents=True, exist_ok=True)
    topology.write_text(
        json.dumps(
            {
                "machines": [
                    {
                        "id": "mattbook",
                        "enabled": topology_enabled,
                        "platform": "macos",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    runner = root / mac_startup.RUNNER_RELATIVE
    runner.parent.mkdir(parents=True)
    runner.write_text("#!/bin/zsh\nexit 0\n", encoding="utf-8")


class RuntimePaths:
    def __init__(self, root: Path):
        self.runtime_dir = root / "runtime"
        self.runtime_runner = self.runtime_dir / "startup.sh"
        self.runtime_config = self.runtime_dir / "runtime-config.json"
        self.archive_dir = self.runtime_dir / "legacy-launchagents"
        self.launch_dir = root / "LaunchAgents"
        self.log_dir = root / "Logs"

    def patch(self):
        return mock.patch.multiple(
            mac_startup,
            RUNTIME_DIR=self.runtime_dir,
            RUNTIME_RUNNER=self.runtime_runner,
            RUNTIME_CONFIG=self.runtime_config,
            LEGACY_ARCHIVE_DIR=self.archive_dir,
            LAUNCH_AGENT_DIR=self.launch_dir,
            LOG_DIR=self.log_dir,
        )


class MacStartupTests(unittest.TestCase):
    def test_public_defaults_are_disabled_without_private_machine_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            (root / mac_startup.PRIVATE_CONFIG_RELATIVE).unlink()

            config = mac_startup.load_config(root, machine_id="fresh-machine")

        self.assertFalse(config["enabled"])
        self.assertEqual(mac_startup.enabled_actions(config), [])

    def test_mattbook_private_override_enables_only_remap_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)

            config = mac_startup.load_config(root, machine_id="mattbook")

        self.assertTrue(config["enabled"])
        self.assertEqual(mac_startup.enabled_actions(config), ["remap-tilde-key"])
        self.assertEqual(
            config["legacy_launch_agents"],
            ["com.user.loginscript", "com.typespace.hidutil-keymap"],
        )

    def test_launch_agent_uses_copied_runtime_and_run_at_load(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = RuntimePaths(Path(temporary))
            with paths.patch():
                plist = mac_startup.launch_agent_plist(
                    mac_startup.DEFAULT_LABEL, ["remap-tilde-key"]
                )

        self.assertTrue(plist["RunAtLoad"])
        self.assertEqual(plist["ProcessType"], "Background")
        self.assertEqual(
            plist["ProgramArguments"],
            ["/bin/zsh", str(paths.runtime_runner), "remap-tilde-key"],
        )
        self.assertNotIn("iCloud", " ".join(plist["ProgramArguments"]))

    def test_open_applications_expand_to_validated_runtime_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            private_path = root / mac_startup.PRIVATE_CONFIG_RELATIVE
            private = json.loads(private_path.read_text(encoding="utf-8"))
            private["machines"]["mattbook"]["actions"]["open-applications"] = True
            private["machines"]["mattbook"]["applications"] = [
                "com.bitwarden.desktop"
            ]
            private_path.write_text(json.dumps(private), encoding="utf-8")

            config = mac_startup.load_config(root, machine_id="mattbook")

        self.assertEqual(
            mac_startup.runtime_actions(config),
            ["remap-tilde-key", "open-application:com.bitwarden.desktop"],
        )

    def test_open_applications_reject_invalid_or_empty_bundle_list(self) -> None:
        with self.assertRaisesRegex(mac_startup.MacStartupError, "bundle identifier"):
            mac_startup.validate_applications(["/Applications/Bitwarden.app"])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            private_path = root / mac_startup.PRIVATE_CONFIG_RELATIVE
            private = json.loads(private_path.read_text(encoding="utf-8"))
            private["machines"]["mattbook"]["actions"]["open-applications"] = True
            private_path.write_text(json.dumps(private), encoding="utf-8")
            with self.assertRaisesRegex(mac_startup.MacStartupError, "at least one"):
                mac_startup.load_config(root, machine_id="mattbook")

    def test_install_dry_run_does_not_write_or_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            write_fixture(root)
            paths = RuntimePaths(Path(temporary))
            with paths.patch():
                with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                    with mock.patch.object(mac_startup, "current_machine_id", return_value="mattbook"):
                        with mock.patch.object(mac_startup, "service_loaded", return_value=False):
                            with mock.patch.object(mac_startup, "run_launchctl") as launchctl:
                                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                                    result = mac_startup.install(root, dry_run=True)

            self.assertEqual(result, 0)
            self.assertIn("would copy", stdout.getvalue())
            self.assertFalse(paths.runtime_runner.exists())
            self.assertFalse(paths.launch_dir.exists())
            launchctl.assert_not_called()

    def test_install_refuses_disabled_machine_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            write_fixture(root, private_enabled=False)
            paths = RuntimePaths(Path(temporary))
            with paths.patch():
                with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                    with mock.patch.object(mac_startup, "current_machine_id", return_value="mattbook"):
                        with self.assertRaisesRegex(
                            mac_startup.MacStartupError, "disabled for machine"
                        ):
                            mac_startup.install(root, dry_run=False)

            self.assertFalse(paths.runtime_dir.exists())
            self.assertFalse(paths.launch_dir.exists())

    def test_install_can_explicitly_provision_disabled_topology_machine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            write_fixture(root, topology_enabled=False)
            paths = RuntimePaths(Path(temporary))
            with paths.patch():
                with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                    with mock.patch.object(mac_startup, "current_machine_id", return_value="mattbook"):
                        with mock.patch.object(mac_startup, "service_loaded", return_value=False):
                            with mock.patch.object(mac_startup, "run_launchctl") as launchctl:
                                launchctl.return_value = SimpleNamespace(returncode=0)
                                with mock.patch.object(mac_startup, "run_actions", return_value=0):
                                    result = mac_startup.install(
                                        root,
                                        dry_run=False,
                                        provision_disabled=True,
                                    )

            self.assertEqual(result, 0)
            self.assertTrue(paths.runtime_runner.is_file())

    def test_provision_disabled_flag_refuses_enabled_topology_machine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root, topology_enabled=True)
            config = mac_startup.load_config(root, machine_id="mattbook")
            with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                with self.assertRaisesRegex(mac_startup.MacStartupError, "already enabled"):
                    mac_startup.require_eligible_machine(
                        root, config, provision_disabled=True
                    )

    def test_install_archives_legacy_jobs_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            write_fixture(root)
            paths = RuntimePaths(base)
            paths.launch_dir.mkdir()
            for label in ("com.user.loginscript", "com.typespace.hidutil-keymap"):
                (paths.launch_dir / f"{label}.plist").write_text(label, encoding="utf-8")

            with paths.patch():
                with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                    with mock.patch.object(mac_startup, "current_machine_id", return_value="mattbook"):
                        with mock.patch.object(mac_startup, "service_loaded", return_value=False):
                            with mock.patch.object(mac_startup, "run_launchctl") as launchctl:
                                launchctl.return_value = SimpleNamespace(returncode=0)
                                with mock.patch.object(mac_startup, "run_actions", return_value=0):
                                    first = mac_startup.install(root, dry_run=False)
                                    second = mac_startup.install(root, dry_run=False)

            self.assertEqual((first, second), (0, 0))
            self.assertTrue(paths.runtime_runner.is_file())
            self.assertEqual(paths.runtime_runner.stat().st_mode & 0o777, 0o755)
            self.assertTrue(paths.runtime_config.is_file())
            managed_plist = paths.launch_dir / f"{mac_startup.DEFAULT_LABEL}.plist"
            self.assertTrue(managed_plist.is_file())
            parsed = plistlib.loads(managed_plist.read_bytes())
            self.assertEqual(parsed["ProgramArguments"][-1], "remap-tilde-key")
            archives = sorted(paths.archive_dir.glob("*.plist"))
            self.assertEqual(len(archives), 2)
            self.assertFalse((paths.launch_dir / "com.user.loginscript.plist").exists())
            self.assertFalse((paths.launch_dir / "com.typespace.hidutil-keymap.plist").exists())

    def test_hidutil_mapping_parser_requires_requested_direction(self) -> None:
        requested = """(
          {
            HIDKeyboardModifierMappingDst = 30064771172;
            HIDKeyboardModifierMappingSrc = 30064771125;
          }
        )"""
        inverse = requested.replace("30064771172", "TEMP").replace(
            "30064771125", "30064771172"
        ).replace("TEMP", "30064771125")

        with mock.patch.object(mac_startup.sys, "platform", "darwin"):
            with mock.patch.object(
                mac_startup.subprocess,
                "run",
                return_value=SimpleNamespace(stdout=requested, stderr="", returncode=0),
            ):
                active, _ = mac_startup.hidutil_mapping_active()
            with mock.patch.object(
                mac_startup.subprocess,
                "run",
                return_value=SimpleNamespace(stdout=inverse, stderr="", returncode=0),
            ):
                inverse_active, _ = mac_startup.hidutil_mapping_active()

        self.assertTrue(active)
        self.assertFalse(inverse_active)

    def test_runner_contains_exact_hidutil_mapping(self) -> None:
        runner = Path(__file__).parents[2] / "tools/mac-automation/startup.sh"
        text = runner.read_text(encoding="utf-8")
        self.assertIn('"HIDKeyboardModifierMappingSrc":0x700000035', text)
        self.assertIn('"HIDKeyboardModifierMappingDst":0x700000064', text)
        self.assertIn('open-application:*', text)
        self.assertIn('/usr/bin/open -gja -b "$bundle_id"', text)

    def test_status_reports_config_runtime_mapping_and_legacy_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            write_fixture(root)
            paths = RuntimePaths(base)
            paths.runtime_dir.mkdir()
            paths.runtime_runner.write_text("runner", encoding="utf-8")
            paths.launch_dir.mkdir()
            (paths.launch_dir / f"{mac_startup.DEFAULT_LABEL}.plist").write_text(
                "plist", encoding="utf-8"
            )

            with paths.patch():
                with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                    with mock.patch.object(mac_startup, "current_machine_id", return_value="mattbook"):
                        with mock.patch.object(
                            mac_startup,
                            "service_loaded",
                            side_effect=lambda label: label == mac_startup.DEFAULT_LABEL,
                        ):
                            with mock.patch.object(
                                mac_startup, "hidutil_mapping_active", return_value=(True, "mapping")
                            ):
                                payload = mac_startup.status_payload(root)

        self.assertTrue(payload["configuredEnabled"])
        self.assertTrue(payload["registeredMachine"])
        self.assertTrue(payload["plistInstalled"])
        self.assertTrue(payload["runtimeInstalled"])
        self.assertTrue(payload["loaded"])
        self.assertTrue(payload["mapping"]["active"])
        self.assertTrue(all(not agent["loaded"] for agent in payload["legacyAgents"]))

    def test_uninstall_leaves_hidutil_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            write_fixture(root)
            paths = RuntimePaths(base)
            paths.runtime_dir.mkdir()
            paths.runtime_runner.write_text("runner", encoding="utf-8")
            paths.runtime_config.write_text("{}", encoding="utf-8")
            paths.launch_dir.mkdir()
            (paths.launch_dir / f"{mac_startup.DEFAULT_LABEL}.plist").write_text(
                "plist", encoding="utf-8"
            )
            with paths.patch():
                with mock.patch.object(mac_startup.sys, "platform", "darwin"):
                    with mock.patch.object(mac_startup, "current_machine_id", return_value="mattbook"):
                        with mock.patch.object(mac_startup, "run_launchctl") as launchctl:
                            with mock.patch.object(mac_startup.subprocess, "run") as process:
                                result = mac_startup.uninstall(root, dry_run=False)

            self.assertEqual(result, 0)
            self.assertFalse(paths.runtime_runner.exists())
            self.assertFalse(paths.runtime_config.exists())
            process.assert_not_called()
            launchctl.assert_called_once()

    def test_bootstrap_contract_exports_disabled_defaults_only(self) -> None:
        vault_root = Path(__file__).parents[3]
        defaults = json.loads(
            (vault_root / mac_startup.DEFAULT_CONFIG_RELATIVE).read_text(encoding="utf-8")
        )
        export_config = json.loads(
            (vault_root / "_system/bootstrap/bootstrap-export.json").read_text(encoding="utf-8")
        )
        installer_text = "\n".join(
            (vault_root / path).read_text(encoding="utf-8")
            for path in ("_system/bootstrap/install.sh", "_system/bootstrap/init_vault.sh")
        )

        self.assertFalse(defaults["enabled"])
        self.assertTrue(all(enabled is False for enabled in defaults["actions"].values()))
        self.assertEqual(defaults["applications"], [])
        self.assertIn("_system/local/skills/**/private/**", export_config["generated_exclude_globs"])
        self.assertNotIn("mac-startup install", installer_text)


if __name__ == "__main__":
    unittest.main()
