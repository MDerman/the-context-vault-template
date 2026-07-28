#!/usr/bin/env python3
"""Tests for editable Agent Canvas installation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BOOTSTRAP_DIR = Path(__file__).resolve().parents[2] / "bootstrap"
sys.path.insert(0, str(BOOTSTRAP_DIR))

import install_agent_canvas as installer  # noqa: E402


def health(*, bun_bin: Path = Path("/tmp/bun/bin"), build: bool = True, package: bool = True, command: bool = True, local: bool = True, version: bool = True) -> installer.Health:
    return installer.Health(
        expected_version="0.13.0",
        bun=Path("/opt/bin/bun"),
        node=Path("/opt/bin/node"),
        bun_bin=bun_bin,
        build_ok=build,
        package_link_ok=package,
        bun_command_ok=command,
        local_command_ok=local,
        version_ok=version,
        version="0.13.0" if version else "0.12.0",
    )


class AgentCanvasInstallerTests(unittest.TestCase):
    def test_clean_install_builds_links_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            (repo / installer.CLI_DIR).mkdir(parents=True)
            bun_bin = root / "bun/bin"
            bun_bin.mkdir(parents=True)
            (bun_bin / "agent-canvas").write_text("command\n")
            states = [health(bun_bin=bun_bin, build=False, package=False, command=False, local=False, version=False), health(bun_bin=bun_bin, package=False, command=False, local=False, version=False), health(bun_bin=bun_bin, local=False), health(bun_bin=bun_bin)]
            with (
                patch.object(installer, "inspect", side_effect=states),
                patch.object(installer, "run", return_value=installer.subprocess.CompletedProcess([], 0, "", "")) as run,
                patch.object(installer, "ensure_local_command") as link,
            ):
                installer.apply(repo, root, False)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn(["/opt/bin/bun", "install", "--frozen-lockfile"], commands)
            self.assertIn(["/opt/bin/bun", "run", "build"], commands)
            self.assertIn(["/opt/bin/bun", "link"], commands)
            link.assert_called_once()

    def test_healthy_setup_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bun_bin = root / "bun/bin"
            bun_bin.mkdir(parents=True)
            (bun_bin / "agent-canvas").write_text("command\n")
            with (
                patch.object(installer, "inspect", side_effect=[health(bun_bin=bun_bin)] * 4),
                patch.object(installer, "run") as run,
                patch.object(installer, "ensure_local_command") as link,
            ):
                installer.apply(root, root, False)
            run.assert_not_called()
            link.assert_called_once()

    def test_broken_bun_link_is_repaired_without_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bun_bin = root / "bun/bin"
            bun_bin.mkdir(parents=True)
            (bun_bin / "agent-canvas").write_text("command\n")
            states = [health(bun_bin=bun_bin, package=False, command=False, local=False), health(bun_bin=bun_bin, package=False, command=False, local=False), health(bun_bin=bun_bin, local=False), health(bun_bin=bun_bin)]
            with (
                patch.object(installer, "inspect", side_effect=states),
                patch.object(installer, "run", return_value=installer.subprocess.CompletedProcess([], 0, "", "")) as run,
                patch.object(installer, "ensure_local_command"),
            ):
                installer.apply(root, root, False)
            self.assertEqual(run.call_args_list[0].args[0], ["/opt/bin/bun", "link"])

    def test_missing_build_and_version_mismatch_plan_build(self) -> None:
        self.assertIn("bun run build", installer.planned_actions(health(build=False), False))
        self.assertIn("bun run build", installer.planned_actions(health(version=False), False))
        self.assertIn("bun run build", installer.planned_actions(health(), True))

    def test_unrelated_local_command_conflict_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            command = home / ".local/bin/agent-canvas"
            command.parent.mkdir(parents=True)
            command.write_text("unrelated\n")
            with self.assertRaisesRegex(RuntimeError, "unrelated command conflict"):
                installer.ensure_local_command(home, home / "bun/agent-canvas")


if __name__ == "__main__":
    unittest.main()
