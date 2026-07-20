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
SPEC = importlib.util.spec_from_file_location("vault_dispatch", VAULT_PATH)
assert SPEC and SPEC.loader
vault_dispatch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vault_dispatch
SPEC.loader.exec_module(vault_dispatch)


class VaultDispatchTests(unittest.TestCase):
    def test_context_command_is_removed(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                result = vault_dispatch.main(["context"])

        self.assertEqual(result, 2)
        self.assertIn("Unknown vault command: context", stderr.getvalue())
        self.assertNotIn("\n  context", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
