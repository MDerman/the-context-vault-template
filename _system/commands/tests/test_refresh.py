#!/usr/bin/env python3
"""Tests for vault refresh command orchestration."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REFRESH_PATH = SCRIPT_DIR / "refresh.py"
SPEC = importlib.util.spec_from_file_location("refresh", REFRESH_PATH)
assert SPEC and SPEC.loader
refresh = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = refresh
SPEC.loader.exec_module(refresh)


GENERATED = (
    ["personal"],
    {
        "daily": "2026-07-28",
        "weekly": "2026-W31",
        "monthly": "2026-07",
        "quarterly": "2026-Q3",
        "yearly": "2026",
    },
    [],
)


class RefreshTests(unittest.TestCase):
    def test_schedule_refresh_is_gated_by_schedule_frontmatter_not_blog_folders(self) -> None:
        import content
        import dashboard
        import periodic

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, schedules_enabled in (("blog-only", False), ("scheduled", True)):
                context = root / name
                (context / "_obsidian/content/items/blog-posts").mkdir(parents=True)
                schedules = "content_schedules_enabled: true\n" if schedules_enabled else ""
                (context / f"{name}.md").write_text(
                    f"---\nstatus: active\n{schedules}context_registered: true\n---\n",
                    encoding="utf-8",
                )
            selected = ["blog-only", "scheduled"]
            periods = {"daily": "2026-08-13"}
            with (
                mock.patch.object(refresh, "configured_context_folders", return_value=selected),
                mock.patch.object(periodic, "resolve_entities", return_value=selected),
                mock.patch.object(content, "generate_content_schedules", return_value=[]) as generate_content,
                mock.patch.object(periodic, "generate_periodic_notes", return_value=(selected, periods)),
                mock.patch.object(dashboard, "write_dashboard"),
            ):
                refresh.generate_derived_views(root, day=refresh.dt.date(2026, 8, 13))

        self.assertEqual(generate_content.call_args.args[1], ["scheduled"])

    def test_refresh_skips_brain_dump_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            with mock.patch.object(refresh, "run") as run:
                with mock.patch.object(refresh, "generate_derived_views", return_value=GENERATED) as generate:
                    result = refresh.main(["--root", str(root), "--skip-gcal", "--skip-git-maintenance", "--skip-git-preflight"])

            self.assertEqual(result, 0)
            run.assert_not_called()
            generate.assert_called_once()

    def test_sync_brain_dump_runs_ingest_before_derived_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            events: list[str] = []

            def record_run(command: list[str], _root: Path) -> None:
                self.assertIn("brain_dump.py", " ".join(command))
                events.append("brain-dump")

            with mock.patch.object(refresh, "run", side_effect=record_run):
                with mock.patch.object(
                    refresh,
                    "generate_derived_views",
                    side_effect=lambda *args, **kwargs: (events.append("views") or GENERATED),
                ):
                    result = refresh.main(
                        ["--root", str(root), "--sync-brain-dump", "--skip-gcal", "--skip-git-maintenance", "--skip-git-preflight"]
                    )

            self.assertEqual(result, 0)
            self.assertEqual(events, ["brain-dump", "views"])

    def test_refresh_forwards_selection_and_date_to_derived_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            with mock.patch.object(refresh, "generate_derived_views", return_value=GENERATED) as generate:
                result = refresh.main(
                    [
                        "--root",
                        str(root),
                        "--skip-gcal",
                        "--skip-git-maintenance",
                        "--skip-git-preflight",
                        "--context-folders",
                        "personal,business",
                        "--date",
                        "2026-07-20",
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(generate.call_args.kwargs["explicit_entities"], ["personal", "business"])
        self.assertEqual(generate.call_args.kwargs["day"].isoformat(), "2026-07-20")

    def test_derived_view_failure_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            with mock.patch.object(refresh, "generate_derived_views", side_effect=RuntimeError("dashboard failed")):
                with self.assertRaisesRegex(RuntimeError, "dashboard failed"):
                    refresh.main(["--root", str(root), "--skip-gcal", "--skip-git-maintenance", "--skip-git-preflight"])

    def test_git_preflight_runs_before_generated_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            events: list[str] = []
            with mock.patch.object(refresh, "run", side_effect=lambda *_: events.append("preflight")):
                with mock.patch.object(
                    refresh,
                    "generate_derived_views",
                    side_effect=lambda *args, **kwargs: (events.append("views") or GENERATED),
                ):
                    result = refresh.main(["--root", str(root), "--skip-gcal", "--skip-git-maintenance"])
        self.assertEqual(result, 0)
        self.assertEqual(events, ["preflight", "views"])

    def test_best_effort_git_preflight_failure_does_not_block_generated_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            events: list[str] = []
            with mock.patch.object(refresh, "run") as run:
                with mock.patch.object(refresh, "run_optional", side_effect=lambda *_: events.append("preflight-warning")):
                    with mock.patch.object(
                        refresh,
                        "generate_derived_views",
                        side_effect=lambda *args, **kwargs: (events.append("views") or GENERATED),
                    ):
                        result = refresh.main(
                            [
                                "--root",
                                str(root),
                                "--best-effort-git-preflight",
                                "--skip-gcal",
                                "--skip-git-maintenance",
                            ]
                        )

        self.assertEqual(result, 0)
        run.assert_not_called()
        self.assertEqual(events, ["preflight-warning", "views"])

    def test_current_refresh_publishes_completion_after_generated_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            events: list[str] = []
            with mock.patch.object(refresh, "local_today", return_value=refresh.dt.date(2026, 7, 28)):
                with mock.patch.object(
                    refresh,
                    "generate_derived_views",
                    side_effect=lambda *args, **kwargs: (events.append("views") or GENERATED),
                ):
                    with mock.patch.object(
                        refresh,
                        "write_refresh_completion",
                        side_effect=lambda *_: (events.append("marker") or {"effectiveDate": "2026-07-28", "runId": "run-1"}),
                    ):
                        with mock.patch.object(
                            refresh,
                            "notify_context_nine",
                            side_effect=lambda *_: (events.append("notify") or True),
                        ):
                            result = refresh.main(
                                [
                                    "--root",
                                    str(root),
                                    "--date",
                                    "2026-07-28",
                                    "--skip-gcal",
                                    "--skip-git-maintenance",
                                    "--skip-git-preflight",
                                ]
                            )

        self.assertEqual(result, 0)
        self.assertEqual(events, ["views", "marker", "notify"])

    def test_historical_refresh_does_not_publish_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            with mock.patch.object(refresh, "local_today", return_value=refresh.dt.date(2026, 7, 28)):
                with mock.patch.object(refresh, "generate_derived_views", return_value=GENERATED):
                    with mock.patch.object(refresh, "write_refresh_completion") as write_completion:
                        result = refresh.main(
                            [
                                "--root",
                                str(root),
                                "--date",
                                "2026-07-27",
                                "--skip-gcal",
                                "--skip-git-maintenance",
                                "--skip-git-preflight",
                            ]
                        )

        self.assertEqual(result, 0)
        write_completion.assert_not_called()

    def test_completion_marker_is_atomic_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed_at = refresh.dt.datetime(2026, 7, 28, 8, 0, tzinfo=refresh.dt.timezone.utc)
            payload = refresh.write_refresh_completion(
                root,
                refresh.dt.date(2026, 7, 28),
                GENERATED[1],
                completed_at=completed_at,
                run_id="run-1",
            )

            marker = root / refresh.REFRESH_COMPLETION_MARKER
            self.assertEqual(json.loads(marker.read_text(encoding="utf-8")), payload)
            self.assertEqual(list(marker.parent.glob("*.tmp")), [])

    def test_notification_never_calls_cli_when_obsidian_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(refresh, "obsidian_process_is_running", return_value=False):
                with mock.patch.object(refresh.subprocess, "run") as run:
                    notified = refresh.notify_context_nine(
                        Path(tmp),
                        {"effectiveDate": "2026-07-28", "runId": "run-1"},
                    )

        self.assertFalse(notified)
        run.assert_not_called()

    def test_notification_calls_registered_cli_from_vault_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = mock.Mock(returncode=0, stdout='{"updated":1}\n', stderr="")
            with mock.patch.object(refresh, "obsidian_process_is_running", return_value=True):
                with mock.patch.object(refresh, "obsidian_cli_path", return_value="/usr/local/bin/obsidian"):
                    with mock.patch.object(refresh.subprocess, "run", return_value=result) as run:
                        notified = refresh.notify_context_nine(
                            root,
                            {"effectiveDate": "2026-07-28", "runId": "run-1"},
                        )

        self.assertTrue(notified)
        self.assertEqual(run.call_args.args[0][1:], [
            refresh.CONTEXT_NINE_CLI_COMMAND,
            "date=2026-07-28",
            "run-id=run-1",
        ])
        self.assertEqual(run.call_args.kwargs["cwd"], root)


if __name__ == "__main__":
    unittest.main()
