#!/usr/bin/env python3
"""Tests for public release helpers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

RELEASE_PATH = SCRIPT_DIR / "release.py"
SPEC = importlib.util.spec_from_file_location("release", RELEASE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_parse_semver_accepts_optional_v_prefix(self) -> None:
        self.assertEqual(release.parse_semver("0.1.2"), release.SemVer(0, 1, 2))
        self.assertEqual(release.parse_semver("v1.2.3"), release.SemVer(1, 2, 3))
        self.assertIsNone(release.parse_semver("2026.05.29"))

    def test_bump_semver_starts_calver_releases_at_0_1_0(self) -> None:
        self.assertEqual(release.bump_semver(None, "patch"), release.SemVer(0, 1, 0))

    def test_bump_semver_patch_minor_major(self) -> None:
        current = release.SemVer(1, 2, 3)
        self.assertEqual(release.bump_semver(current, "patch"), release.SemVer(1, 2, 4))
        self.assertEqual(release.bump_semver(current, "minor"), release.SemVer(1, 3, 0))
        self.assertEqual(release.bump_semver(current, "major"), release.SemVer(2, 0, 0))

    def test_choose_version_rejects_duplicate_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / release.RELEASE_PATH).parent.mkdir(parents=True)
            (root / release.RELEASE_PATH).write_text('{"version":"2026.05.29"}\n', encoding="utf-8")
            args = Namespace(version="0.1.0", bump="patch")

            with mock.patch.object(release, "latest_public_version", return_value=None):
                with mock.patch.object(release, "ensure_version_available", side_effect=SystemExit("Tag already exists")):
                    with self.assertRaisesRegex(SystemExit, "Tag already exists"):
                        release.choose_version(root, args)


if __name__ == "__main__":
    unittest.main()
