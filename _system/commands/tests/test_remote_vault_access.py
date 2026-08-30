#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


VAULT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    VAULT_ROOT
    / "_system/agents/skills/auto/_infrastructure/infra-onboard-machine/"
    "scripts/remote_vault_access.py"
)
SPEC = importlib.util.spec_from_file_location("remote_vault_access_tested", SCRIPT)
assert SPEC and SPEC.loader
access = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(access)


class RemoteVaultAccessTests(unittest.TestCase):
    def config(self, root: Path) -> dict[str, object]:
        return {
            "schema_version": 1,
            "role": "host",
            "machine_id": "host",
            "vault_root": str(root / "Vault"),
            "state_root": str(root / "state"),
            "receipt_root": str(root / "Vault/_system/local/state/remote-vault-receipts"),
            "allowed_clients": ["client"],
            "git_owner_machine_id": "primary",
        }

    def test_fileprovider_and_brctl_parsers_fail_closed(self) -> None:
        fields = "\n".join(
            f"{name} = {value};"
            for name, value in {
                "hasUnresolvedConflicts": 0,
                "isDownloaded": 1,
                "isDownloading": 0,
                "isExcludedFromSync": 0,
                "isKeepDownloaded": 1,
                "isMostRecentVersionDownloaded": 1,
                "isRecursivelyDownloaded": 1,
                "isSyncPaused": 0,
                "isUploaded": 1,
                "isUploading": 0,
            }.items()
        )
        with mock.patch.object(
            access,
            "run",
            return_value=subprocess.CompletedProcess(["fileproviderctl"], 0, fields, ""),
        ):
            state = access.fileprovider_evaluate(Path("/Vault"))
        self.assertTrue(state["known"])
        with mock.patch.object(
            access,
            "run",
            return_value=subprocess.CompletedProcess(["fileproviderctl"], 0, "isUploaded = 1;", ""),
        ):
            self.assertFalse(access.fileprovider_evaluate(Path("/Vault"))["known"])
        brctl = "1 containers matching 'com~apple~CloudDocs' {client:idle last-sync:2026-01-01 00:00:00.000, caught-up}"
        with mock.patch.object(
            access,
            "run",
            return_value=subprocess.CompletedProcess(["brctl"], 0, brctl, ""),
        ):
            self.assertTrue(access.brctl_status()["caught_up"])

    def test_lease_is_exclusive_and_expired_recovery_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            lease = access.acquire_lease(config, "client", "session-12345678", 123)
            self.assertEqual(lease["machine_id"], "client")
            with self.assertRaisesRegex(access.AccessError, "held by client"):
                access.acquire_lease(config, "client", "session-87654321", 456)
            paths = access.host_paths(config)
            lease["expires_at"] = "2000-01-01T00:00:00Z"
            access.atomic_write(paths["lease_file"], lease)
            recovered = access.recover_lease(config, "operator confirmed abandoned writer")
            self.assertTrue(recovered["recovered"])
            self.assertFalse(paths["lease"].exists())
            self.assertIn("operator confirmed", paths["events"].read_text())

    def test_pending_upload_does_not_block_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fields = {
                "hasUnresolvedConflicts": False,
                "isDownloaded": True,
                "isDownloading": False,
                "isExcludedFromSync": False,
                "isKeepDownloaded": True,
                "isMostRecentVersionDownloaded": True,
                "isRecursivelyDownloaded": True,
                "isSyncPaused": False,
                "isUploaded": False,
                "isUploading": True,
            }
            provider = {"known": True, "path": str(root), "fields": fields, "detail": "evaluated"}
            container = {
                "known": True,
                "caught_up": False,
                "idle": False,
                "pending": True,
                "last_activity": "now",
                "detail": "container not caught up",
            }
            with (
                mock.patch.object(access, "fileprovider_evaluate", return_value=provider),
                mock.patch.object(access, "brctl_status", return_value=container),
                mock.patch.object(access, "first_materialization_problem", return_value=(None, None)),
            ):
                health = access.icloud_health(root)
        self.assertTrue(health["access_ready"])
        self.assertFalse(health["healthy"])
        self.assertEqual(health["state"], "uploading")

    def test_finish_does_not_wait_for_upload_and_releases_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "Vault"
            (vault / "_system/local/state/remote-vault-receipts").mkdir(parents=True)
            (vault / "note.md").write_text("before\n", encoding="utf-8")
            config = self.config(base)
            healthy = {
                "healthy": False,
                "access_ready": True,
                "state": "uploading",
                "last_icloud_activity": "now",
            }
            with mock.patch.object(access, "icloud_health", return_value=healthy):
                access.host_begin(config, "client", "session-12345678", 123)
            (vault / "note.md").write_text("after\n", encoding="utf-8")
            with mock.patch.object(access, "icloud_health", return_value=healthy), mock.patch.object(
                access, "wait_for_icloud"
            ) as wait_for_icloud:
                result = access.host_finish(config, "client", "session-12345678", 30)
            self.assertTrue(result["finished"])
            wait_for_icloud.assert_not_called()
            receipt = json.loads(
                (vault / "_system/local/state/remote-vault-receipts/session-12345678.json").read_text()
            )
            self.assertEqual(receipt["files"][0]["path"], "note.md")
            self.assertEqual(len(receipt["files"][0]["sha256"]), 64)
            self.assertTrue(receipt["states"]["filesystem_saved"])
            self.assertFalse(receipt["states"]["icloud_uploaded"])
            self.assertFalse(access.host_paths(config)["lease"].exists())

    def test_mount_uses_portable_cache_options(self) -> None:
        config = {
            "mount_root": "/mnt/vault",
            "source_alias": "workermacair",
            "source_root": "/Vault",
            "writable": True,
        }
        with (
            mock.patch.object(access.shutil, "which", return_value="/usr/bin/sshfs"),
            mock.patch.object(access.Path, "mkdir"),
            mock.patch.object(access.os, "execvp") as execvp,
        ):
            access.mount_service(config)
        arguments = execvp.call_args.args[1]
        self.assertIn("cache=no", arguments[-1])
        self.assertNotIn("kernel_cache", arguments[-1])

    def test_new_client_status_allows_no_receipts(self) -> None:
        config = {
            "machine_id": "client",
            "source_alias": "host",
            "source_machine_id": "host",
        }
        host = {
            "machine_id": "host",
            "icloud": {"healthy": False, "access_ready": True},
            "latest_receipt": None,
        }
        with (
            mock.patch.object(access, "mount_record", return_value={"healthy": True}),
            mock.patch.object(
                access,
                "ssh_command",
                return_value=subprocess.CompletedProcess(["ssh"], 0, "", ""),
            ),
            mock.patch.object(access, "host_call", return_value=host),
            mock.patch.object(access, "active_local_session", return_value=None),
        ):
            status = access.client_status(config)
        self.assertTrue(status["ok"])
        self.assertEqual(
            status["states"],
            {
                "filesystem_saved": None,
                "icloud_uploaded": None,
                "peer_observed": None,
                "git_pushed": None,
            },
        )

    def test_client_install_includes_dispatcher_identity(self) -> None:
        files = access.managed_paths_for_role("client", {"machine_id": "client"})
        self.assertEqual(files[access.MACHINE_ID], b"client\n")

    def test_mount_status_ignores_containing_filesystem(self) -> None:
        config = {
            "mount_root": "/home/client/Vault",
            "source_alias": "host",
            "source_root": "/Vault",
        }
        findmnt = json.dumps(
            {
                "filesystems": [
                    {
                        "target": "/",
                        "source": "/dev/root",
                        "fstype": "ext4",
                        "options": "rw,relatime",
                    }
                ]
            }
        )
        with mock.patch.object(
            access,
            "run",
            return_value=subprocess.CompletedProcess(["findmnt"], 0, findmnt, ""),
        ):
            status = access.mount_record(config)
        self.assertFalse(status["mounted"])
        self.assertFalse(status["read_write"])
        self.assertIsNone(status["source"])


if __name__ == "__main__":
    unittest.main()
