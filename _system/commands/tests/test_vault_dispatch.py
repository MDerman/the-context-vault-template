#!/usr/bin/env python3
"""Tests for public vault command dispatch."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
VAULT_PATH = SCRIPT_DIR / "vault.py"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("vault_dispatch", VAULT_PATH)
assert SPEC and SPEC.loader
vault_dispatch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vault_dispatch
SPEC.loader.exec_module(vault_dispatch)


class VaultDispatchTests(unittest.TestCase):
    def test_apply_is_injected_for_mutating_commands(self) -> None:
        cases = {
            ("attachments", ()): ["--apply"],
            ("snippets", ("sync",)): ["sync", "--apply"],
            ("business-toolkit", ("unconfigure",)): ["unconfigure", "--apply"],
            ("git-media", ("install-hook",)): ["install-hook", "--apply"],
            ("machine", ("identify", "wootbook")): ["identify", "wootbook", "--apply"],
            ("worker-sync", ("bootstrap", "wootbook")): ["bootstrap", "wootbook", "--apply"],
            ("profile", ("upgrade",)): ["upgrade", "--apply"],
            ("folder", ("remove", "studio")): ["remove", "studio", "--apply"],
            ("upgrade", ()): ["--apply"],
        }
        for (command, arguments), expected in cases.items():
            with self.subTest(command=command, arguments=arguments):
                self.assertEqual(
                    vault_dispatch.with_default_apply(command, list(arguments)),
                    expected,
                )

    def test_explicit_non_apply_modes_are_preserved(self) -> None:
        for mode in ("--dry-run", "--verify", "--verify-only", "--help"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    vault_dispatch.with_default_apply("attachments", [mode]),
                    [mode],
                )
        self.assertEqual(vault_dispatch.with_default_apply("upgrade", ["status"]), ["status"])

    def test_attachment_verification_uses_read_only_capability(self) -> None:
        self.assertEqual(
            vault_dispatch.command_capabilities("attachments", ["--verify-only"]),
            frozenset({"content-read"}),
        )
        self.assertEqual(
            vault_dispatch.command_capabilities("attachments", []),
            frozenset({"content-write"}),
        )

    def test_mac_startup_command_is_registered(self) -> None:
        self.assertEqual(
            vault_dispatch.COMMANDS["mac-startup"],
            SCRIPT_DIR / "mac_startup.py",
        )

    def test_snippets_command_is_registered(self) -> None:
        self.assertEqual(
            vault_dispatch.COMMANDS["snippets"],
            SCRIPT_DIR / "snippets.py",
        )

    def test_agent_package_commands_are_not_vault_aliases(self) -> None:
        self.assertNotIn("agents", vault_dispatch.COMMANDS)
        self.assertNotIn("skills", vault_dispatch.COMMANDS)

    def test_every_dispatch_route_has_a_capability_policy(self) -> None:
        self.assertEqual(
            set(vault_dispatch.COMMAND_CAPABILITIES),
            {*vault_dispatch.COMMANDS, "root", "tui"},
        )

    def test_context_command_is_removed(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                result = vault_dispatch.main(["context"])

        self.assertEqual(result, 2)
        self.assertIn("Unknown vault command: context", stderr.getvalue())
        self.assertNotIn("\n  context", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
