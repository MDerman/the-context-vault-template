from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import git_maintenance


def run(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


class GitMaintenanceTests(unittest.TestCase):
    def test_shallow_boundaries_cover_every_local_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run(root, "init", "-q")
            run(root, "config", "user.name", "Test")
            run(root, "config", "user.email", "test@example.com")
            for index in range(6):
                (root / "main.txt").write_text(f"{index}\n", encoding="utf-8")
                run(root, "add", "main.txt")
                run(root, "commit", "-qm", f"main {index}")
            run(root, "branch", "secondary", "HEAD~3")
            run(root, "checkout", "-q", "secondary")
            for index in range(4):
                (root / "secondary.txt").write_text(f"{index}\n", encoding="utf-8")
                run(root, "add", "secondary.txt")
                run(root, "commit", "-qm", f"secondary {index}")
            run(root, "checkout", "-q", "master")

            self.assertTrue(git_maintenance.trim_shallow_boundary(root, 3))

            shallow = Path(run(root, "rev-parse", "--git-path", "shallow"))
            if not shallow.is_absolute():
                shallow = root / shallow
            boundaries = set(shallow.read_text(encoding="utf-8").splitlines())
            expected = {
                run(root, "rev-list", "--max-count=1", "--skip=2", "master"),
                run(root, "rev-list", "--max-count=1", "--skip=2", "secondary"),
            }
            self.assertEqual(expected, boundaries)
            run(root, "fsck", "--no-dangling")


if __name__ == "__main__":
    unittest.main()
