#!/usr/bin/env python3
"""Tests for pointer-only Git media tooling."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPT_DIR / "git_media.py"
SPEC = importlib.util.spec_from_file_location("git_media", MODULE_PATH)
assert SPEC and SPEC.loader
git_media = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = git_media
SPEC.loader.exec_module(git_media)


class GitMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="git-media-test-")
        self.root = Path(self.temporary.name)
        self.run_command("git", "init", "-b", "master")
        self.run_command("git", "config", "user.name", "Test User")
        self.run_command("git", "config", "user.email", "test@example.com")
        self.run_command("git", "lfs", "install", "--local")
        (self.root / ".gitattributes").write_text(
            "*.png filter=lfs diff=lfs merge=lfs -text\n"
            "*.docx filter=lfs diff=lfs merge=lfs -text\n",
            encoding="utf-8",
        )
        (self.root / "note.md").write_text("# Note\n", encoding="utf-8")
        (self.root / "image\nname.png").write_bytes(b"image-body")
        (self.root / "document.docx").write_bytes(b"office-body")
        self.run_command("git", "add", ".gitattributes", "note.md", "image\nname.png", "document.docx")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_command(self, *command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=self.root, check=True, text=True, capture_output=True)

    def write_and_stage_manifest(self) -> dict[str, object]:
        manifest = git_media.build_manifest(self.root, None)
        destination = self.root / git_media.MANIFEST_REL
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(git_media.manifest_bytes(manifest))
        self.run_command("git", "add", str(git_media.MANIFEST_REL))
        return manifest

    def test_manifest_round_trip_preserves_unusual_paths(self) -> None:
        manifest = self.write_and_stage_manifest()
        self.assertEqual(manifest["summary"]["files"], 2)
        self.assertEqual([item["path"] for item in manifest["files"]], ["document.docx", "image\nname.png"])
        verified = git_media.verify(self.root, None, local_objects=True, full_hash=True)
        self.assertEqual(verified, manifest)

        self.run_command("git", "commit", "-m", "Initial")
        committed = git_media.verify(self.root, "HEAD", local_objects=True, full_hash=False)
        self.assertEqual(committed, manifest)

    def test_stale_manifest_is_rejected(self) -> None:
        self.write_and_stage_manifest()
        (self.root / "second.png").write_bytes(b"second")
        self.run_command("git", "add", "second.png")
        with self.assertRaisesRegex(git_media.GitMediaError, "manifest is stale"):
            git_media.verify(self.root, None, local_objects=True, full_hash=False)

    def test_binary_without_lfs_routing_is_rejected(self) -> None:
        (self.root / "unrouted.xlsx").write_bytes(b"sheet")
        self.run_command("git", "add", "-f", "unrouted.xlsx")
        with self.assertRaisesRegex(git_media.GitMediaError, "not routed through LFS"):
            git_media.build_manifest(self.root, None)

    def test_hook_replaces_standard_lfs_upload_hook(self) -> None:
        git_media.install_hook(self.root, apply=True)
        hook_path = Path(self.run_command("git", "rev-parse", "--git-path", "hooks/pre-push").stdout.strip())
        if not hook_path.is_absolute():
            hook_path = self.root / hook_path
        content = hook_path.read_text(encoding="utf-8")
        self.assertIn(git_media.HOOK_MARKER, content)
        self.assertNotIn("git lfs pre-push", content)

    def test_pointer_parser_rejects_non_pointer(self) -> None:
        with self.assertRaisesRegex(git_media.GitMediaError, "canonical pointer"):
            git_media.parse_pointer(b"not a pointer\n", "bad.png")

    def test_worker_non_media_push_does_not_require_lfs_bodies(self) -> None:
        update = f"refs/heads/master {'1' * 40} refs/heads/master {'2' * 40}\n"
        with mock.patch.object(git_media.sys, "stdin", mock.Mock(read=mock.Mock(return_value=update))):
            with mock.patch.object(git_media, "pointer_only_role", return_value="worker"):
                with mock.patch.object(git_media, "media_write_authorized", return_value=False):
                    with mock.patch.object(git_media, "changed_media_paths", return_value=[]):
                        with mock.patch.object(git_media, "stored_manifest", return_value={"summary": {"files": 3}}) as stored:
                            with mock.patch.object(git_media, "verify") as verify:
                                git_media.pre_push(self.root)
        stored.assert_called_once_with(self.root, "1" * 40)
        verify.assert_not_called()

    def test_worker_media_change_requires_explicit_authorization(self) -> None:
        update = f"refs/heads/master {'1' * 40} refs/heads/master {'2' * 40}\n"
        with mock.patch.object(git_media.sys, "stdin", mock.Mock(read=mock.Mock(return_value=update))):
            with mock.patch.object(git_media, "pointer_only_role", return_value="worker"):
                with mock.patch.object(git_media, "media_write_authorized", return_value=False):
                    with mock.patch.object(git_media, "changed_media_paths", return_value=["image.png"]):
                        with self.assertRaisesRegex(git_media.GitMediaError, "not authorized"):
                            git_media.pre_push(self.root)


if __name__ == "__main__":
    unittest.main()
