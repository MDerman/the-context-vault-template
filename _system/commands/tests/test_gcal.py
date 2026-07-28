#!/usr/bin/env python3
"""Tests for Google Calendar TaskNotes mirror helpers."""

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

GCAL_PATH = SCRIPT_DIR / "gcal.py"
SPEC = importlib.util.spec_from_file_location("gcal", GCAL_PATH)
assert SPEC and SPEC.loader
gcal = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gcal
SPEC.loader.exec_module(gcal)


def env(root: Path, config: dict[str, object] | None = None) -> gcal.Env:
    return gcal.Env(
        root=root,
        config=gcal.deep_merge_config(gcal.DEFAULT_CALENDAR_CONFIG, config or {}),
    )


def task(root: Path, rel_path: str, data: dict[str, str]) -> gcal.TaskNote:
    path = root / rel_path
    return gcal.TaskNote(
        path=path,
        rel_path=rel_path,
        text="---\n---\n",
        body_start=8,
        fm_lines=[],
        data=data,
    )


def owned_event(event_id: str, task_path: str, field: str = "scheduled") -> dict[str, object]:
    return {
        "id": event_id,
        "summary": "Old title",
        "description": "Old description",
        "start": {"date": "2026-07-06"},
        "extendedProperties": {
            "private": {
                "syncOwner": gcal.SYNC_OWNER,
                "taskPath": task_path,
                "taskField": field,
            }
        },
    }


class GCalMirrorTests(unittest.TestCase):
    def test_load_calendar_config_uses_defaults_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loaded = gcal.load_calendar_config(Path(tmp))

        self.assertEqual(loaded["timeZone"], "Africa/Johannesburg")
        self.assertEqual(loaded["calendarNames"]["timeBlocks"], "Time Blocks")
        self.assertEqual(loaded["defaultDurations"]["blockMinutes"], 240)

    def test_load_calendar_config_merges_custom_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / gcal.CONFIG_RELATIVE_PATH
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "timeZone": "Europe/London",
                        "calendarNames": {"timeBlocks": "Focus Blocks"},
                    }
                ),
                encoding="utf-8",
            )

            loaded = gcal.load_calendar_config(root)

        self.assertEqual(loaded["timeZone"], "Europe/London")
        self.assertEqual(loaded["calendarNames"]["timeBlocks"], "Focus Blocks")
        self.assertEqual(loaded["calendarNames"]["scheduledTasks"], "Scheduled Tasks")

    def test_gws_event_list_uses_calendar_events_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = mock.Mock(returncode=0, stdout='{"items":[]}', stderr="")

            with mock.patch.object(gcal.shutil, "which", return_value="/opt/homebrew/bin/gws"):
                with mock.patch.object(gcal.subprocess, "run", return_value=completed) as run:
                    result = gcal.api_request(
                        env(root),
                        "GET",
                        "/calendars/primary/events",
                        query={
                            "timeMin": "2026-07-05T00:00:00+02:00",
                            "timeMax": "2026-07-06T00:00:00+02:00",
                            "singleEvents": "true",
                            "pageToken": None,
                        },
                    )

            self.assertEqual(result, {"items": []})
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ["gws", "calendar", "events", "list"])
            params = json_from_arg(command, "--params")
            self.assertEqual(params["calendarId"], "primary")
            self.assertEqual(params["singleEvents"], "true")
            self.assertNotIn("pageToken", params)

    def test_gws_create_event_sends_payload_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = mock.Mock(returncode=0, stdout='{"id":"event-id"}', stderr="")
            payload = {"summary": "Meet", "start": {"dateTime": "2026-07-05T10:00:00+02:00"}}

            with mock.patch.object(gcal.shutil, "which", return_value="/opt/homebrew/bin/gws"):
                with mock.patch.object(gcal.subprocess, "run", return_value=completed) as run:
                    result = gcal.api_request(
                        env(root),
                        "POST",
                        "/calendars/primary/events",
                        payload=payload,
                    )

            self.assertEqual(result, {"id": "event-id"})
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ["gws", "calendar", "events", "insert"])
            self.assertEqual(json_from_arg(command, "--params")["calendarId"], "primary")
            self.assertEqual(json_from_arg(command, "--json"), payload)

    def test_gws_unavailable_tells_user_to_install_gws(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(gcal.shutil, "which", return_value=None):
                with self.assertRaisesRegex(gcal.GwsUnavailable, "gws not found"):
                    gcal.api_request(env(root), "GET", "/users/me/calendarList")

    def test_gws_auth_error_tells_user_to_login(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = mock.Mock(returncode=2, stdout="", stderr="No encrypted credentials found.")

            with mock.patch.object(gcal.shutil, "which", return_value="/opt/homebrew/bin/gws"):
                with mock.patch.object(gcal.subprocess, "run", return_value=completed):
                    with self.assertRaisesRegex(gcal.GwsAuthError, "gws auth login"):
                        gcal.api_request(env(root), "GET", "/users/me/calendarList")

    def test_gws_insufficient_scope_tells_user_to_login_with_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = mock.Mock(returncode=1, stdout="", stderr="error[api]: Request had insufficient authentication scopes.")

            with mock.patch.object(gcal.shutil, "which", return_value="/opt/homebrew/bin/gws"):
                with mock.patch.object(gcal.subprocess, "run", return_value=completed):
                    with self.assertRaisesRegex(gcal.GwsAuthError, "--services calendar,drive"):
                        gcal.api_request(env(root), "GET", "/users/me/calendarList")

    def test_prunes_owned_event_when_no_task_references_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = owned_event("deleted-event", "personal/_obsidian/tasks/deleted.md")

            with mock.patch.object(gcal, "list_owned_task_events", return_value=[event]):
                with mock.patch.object(gcal, "delete_event") as delete_event:
                    actions = gcal.prune_orphaned_task_events(
                        env(root),
                        {"scheduled": "scheduled-calendar"},
                        [],
                        apply=True,
                    )

            self.assertEqual(
                actions,
                ["prune-orphaned-task-event:scheduled:deleted-event:personal/_obsidian/tasks/deleted.md"],
            )
            delete_event.assert_called_once_with(env(root), "scheduled-calendar", "deleted-event")

    def test_existing_task_with_cleared_date_deletes_existing_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = task(
                root,
                "personal/_obsidian/tasks/example.md",
                {"gcalScheduledEventId": "event-id"},
            )

            with mock.patch.object(gcal, "get_event", return_value=owned_event("event-id", note.rel_path)):
                with mock.patch.object(gcal, "delete_event") as delete_event:
                    action, dirty = gcal.sync_task_field(
                        env(root),
                        note,
                        "scheduled",
                        "scheduled-calendar",
                        apply=True,
                        accept_calendar_deletes=False,
                        now="2026-06-18T10:00:00+02:00",
                    )

            self.assertEqual(action, "delete-event-task-date-cleared:scheduled:personal/_obsidian/tasks/example.md")
            self.assertTrue(dirty)
            delete_event.assert_called_once()
            self.assertNotIn("gcalScheduledEventId", note.data)

    def test_live_task_with_stale_event_metadata_is_kept_and_refreshed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = task(
                root,
                "personal/_obsidian/tasks/current.md",
                {
                    "title": "Current title",
                    "scheduled": "2026-07-06",
                    "gcalScheduledEventId": "event-id",
                    "gcalScheduledLastSyncedValue": "2026-07-06",
                },
            )
            stale_event = owned_event("event-id", "personal/_obsidian/tasks/old.md")

            with mock.patch.object(gcal, "get_event", return_value=stale_event):
                with mock.patch.object(gcal, "update_event", return_value={"id": "event-id"}) as update_event:
                    action, dirty = gcal.sync_task_field(
                        env(root),
                        note,
                        "scheduled",
                        "scheduled-calendar",
                        apply=True,
                        accept_calendar_deletes=False,
                        now="2026-06-18T10:00:00+02:00",
                    )

            self.assertEqual(action, "refresh-event-metadata:scheduled:personal/_obsidian/tasks/current.md")
            self.assertFalse(dirty)
            payload = update_event.call_args.args[3]
            self.assertEqual(payload["summary"], "Current title")
            self.assertEqual(
                payload["extendedProperties"]["private"]["taskPath"],
                "personal/_obsidian/tasks/current.md",
            )

    def test_prune_keeps_referenced_event_even_when_task_path_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = task(
                root,
                "personal/_obsidian/tasks/current.md",
                {"gcalScheduledEventId": "event-id"},
            )
            event = owned_event("event-id", "personal/_obsidian/tasks/old.md")

            with mock.patch.object(gcal, "list_owned_task_events", return_value=[event]):
                with mock.patch.object(gcal, "delete_event") as delete_event:
                    actions = gcal.prune_orphaned_task_events(
                        env(root),
                        {"scheduled": "scheduled-calendar"},
                        [note],
                        apply=True,
                    )

            self.assertEqual(actions, [])
            delete_event.assert_not_called()

    def test_prune_never_deletes_non_owned_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = {
                "id": "manual-event",
                "extendedProperties": {"private": {"taskPath": "personal/_obsidian/tasks/deleted.md"}},
            }

            with mock.patch.object(gcal, "list_owned_task_events", return_value=[event]):
                with mock.patch.object(gcal, "delete_event") as delete_event:
                    actions = gcal.prune_orphaned_task_events(
                        env(root),
                        {"scheduled": "scheduled-calendar"},
                        [],
                        apply=True,
                    )

            self.assertEqual(actions, [])
            delete_event.assert_not_called()

    def test_prune_dry_run_reports_without_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = owned_event("deleted-event", "personal/_obsidian/tasks/deleted.md")

            with mock.patch.object(gcal, "list_owned_task_events", return_value=[event]):
                with mock.patch.object(gcal, "delete_event") as delete_event:
                    actions = gcal.prune_orphaned_task_events(
                        env(root),
                        {"scheduled": "scheduled-calendar"},
                        [],
                        apply=False,
                    )

            self.assertEqual(
                actions,
                ["prune-orphaned-task-event:scheduled:deleted-event:personal/_obsidian/tasks/deleted.md"],
            )
            delete_event.assert_not_called()


def json_from_arg(command: list[str], flag: str) -> dict[str, object]:
    index = command.index(flag)
    return gcal.json.loads(command[index + 1])


if __name__ == "__main__":
    unittest.main()
