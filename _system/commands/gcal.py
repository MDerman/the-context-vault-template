#!/usr/bin/env python3
"""Google Calendar helpers for vault events, time blocks, and TaskNotes date mirrors."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import shutil
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from script_utils import context_folder_note_path, resolve_vault_root
from vault_layout import CALENDAR_CONFIG_PATH

CONFIG_RELATIVE_PATH = CALENDAR_CONFIG_PATH.as_posix()
SYNC_OWNER = "vault-gcal-task-mirror"

DEFAULT_CALENDAR_CONFIG: dict[str, Any] = {
    "timeZone": "Africa/Johannesburg",
    "calendarNames": {
        "timeBlocks": "Time Blocks",
        "scheduledTasks": "Scheduled Tasks",
        "dueTasks": "Due Tasks",
    },
    "defaultDurations": {
        "taskMinutes": 60,
        "blockMinutes": 240,
        "eventMinutes": 60,
    },
    "defaultEventCalendar": "primary",
}
DEFAULT_CALENDAR_NAMES = {
    "time-blocks": "Time Blocks",
    "scheduled": "Scheduled Tasks",
    "due": "Due Tasks",
}
CALENDAR_NAME_CONFIG = {
    "time-blocks": (("calendarNames", "timeBlocks"), "Time Blocks"),
    "scheduled": (("calendarNames", "scheduledTasks"), "Scheduled Tasks"),
    "due": (("calendarNames", "dueTasks"), "Due Tasks"),
}
DEFAULT_CALENDAR_REMINDERS = {
    "time-blocks": [{"method": "popup", "minutes": 0}],
    "scheduled": [{"method": "popup", "minutes": 0}],
    "due": [{"method": "popup", "minutes": 0}, {"method": "popup", "minutes": 25}],
}

FIELD_CONFIG = {
    "scheduled": {
        "calendar_key": "scheduled",
        "event_id": "gcalScheduledEventId",
        "last_value": "gcalScheduledLastSyncedValue",
        "last_event_updated": "gcalScheduledLastSyncedEventUpdated",
        "last_synced_at": "gcalScheduledLastSyncedAt",
    },
    "due": {
        "calendar_key": "due",
        "event_id": "gcalDueEventId",
        "last_value": "gcalDueLastSyncedValue",
        "last_event_updated": "gcalDueLastSyncedEventUpdated",
        "last_synced_at": "gcalDueLastSyncedAt",
    },
}


class GCalError(RuntimeError):
    pass


class GwsUnavailable(GCalError):
    pass


class GwsAuthError(GCalError):
    pass


@dataclass
class Env:
    root: Path
    config: dict[str, Any]

    def config_value(self, keys: tuple[str, ...], default: Any = "") -> Any:
        value: Any = self.config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def setting(self, keys: tuple[str, ...], default: Any = "") -> Any:
        return self.config_value(keys, default)

    def int_setting(self, keys: tuple[str, ...], default: int) -> int:
        return max(1, int(self.setting(keys, default)))

    @property
    def timezone_name(self) -> str:
        return str(self.setting(("timeZone",), "Africa/Johannesburg"))

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def default_task_duration(self) -> int:
        return self.int_setting(("defaultDurations", "taskMinutes"), 60)

    @property
    def default_block_duration(self) -> int:
        return self.int_setting(("defaultDurations", "blockMinutes"), 240)

    @property
    def default_event_duration(self) -> int:
        return self.int_setting(("defaultDurations", "eventMinutes"), 60)

    @property
    def default_event_calendar(self) -> str:
        return str(self.setting(("defaultEventCalendar",), "primary"))


@dataclass
class TaskNote:
    path: Path
    rel_path: str
    text: str
    body_start: int
    fm_lines: list[str]
    data: dict[str, Any]

    @property
    def title(self) -> str:
        title = str(self.data.get("title") or self.path.stem).strip()
        return title.strip('"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Calendar helpers for this vault.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("auth", help="Authorize Google Calendar access.")

    calendars = subparsers.add_parser("calendars", help="Manage required calendars.")
    calendar_sub = calendars.add_subparsers(dest="calendar_command", required=True)
    ensure = calendar_sub.add_parser("ensure", help="Create/find required calendars.")
    ensure.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
    ensure.add_argument("--apply", action="store_true", help="Create missing calendars.")

    list_parser = subparsers.add_parser("list", help="List upcoming calendar events.")
    list_parser.add_argument("--days", type=int, default=7, help="Days to include from --from.")
    list_parser.add_argument("--from", dest="from_date", default=None, help="Start date/datetime.")
    list_parser.add_argument("--calendar", default="all", help="Calendar name, id, or all.")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    event = subparsers.add_parser("create-event", help="Create a specific event on the default calendar.")
    event.add_argument("--title", required=True)
    event.add_argument("--start", required=True, help="Local datetime, e.g. 2026-05-18T09:00.")
    event.add_argument("--end", default=None, help="Local datetime. Defaults to event duration.")
    event.add_argument("--description", default="")
    event.add_argument(
        "--calendar",
        default=None,
        help="Calendar name, id, primary, or default. Defaults to calendar config defaultEventCalendar or primary.",
    )
    event.add_argument("--dry-run", action="store_true")
    event.add_argument("--apply", action="store_true")
    event.add_argument("--json", action="store_true")

    block = subparsers.add_parser("create-block", help="Create a planning block on Time Blocks.")
    block.add_argument("--title", required=True)
    block.add_argument("--start", required=True, help="Local datetime, e.g. 2026-05-18T09:00.")
    block.add_argument("--end", default=None, help="Local datetime. Defaults to block duration.")
    block.add_argument("--description", default="")
    block.add_argument("--dry-run", action="store_true")
    block.add_argument("--apply", action="store_true")
    block.add_argument("--json", action="store_true")

    sync = subparsers.add_parser("sync-tasks", help="Mirror TaskNotes dates with Google Calendar.")
    sync.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
    sync.add_argument("--apply", action="store_true", help="Apply task/calendar changes.")
    sync.add_argument(
        "--accept-calendar-deletes",
        action="store_true",
        help="Treat deleted mirror events as clearing the matching task date.",
    )
    sync.add_argument(
        "--prune-orphaned-task-events",
        action="store_true",
        help="Delete owned mirror events whose event IDs are not referenced by any current TaskNotes task.",
    )
    sync.add_argument("--json", action="store_true", help="Emit JSON summary.")

    return parser.parse_args()


def deep_merge_config(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge_config(result[key], value)
        else:
            result[key] = value
    return result


def load_calendar_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE_PATH
    if not path.exists():
        return copy.deepcopy(DEFAULT_CALENDAR_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GCalError(f"Invalid calendar config JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise GCalError(f"Calendar config must be a JSON object: {path}")
    return deep_merge_config(DEFAULT_CALENDAR_CONFIG, raw)


def load_env(root: Path) -> Env:
    return Env(root=root, config=load_calendar_config(root))


def clean_query(query: dict[str, Any] | None) -> dict[str, Any]:
    if not query:
        return {}
    return {key: value for key, value in query.items() if value is not None}


def decode_path_part(value: str) -> str:
    return urllib.parse.unquote(value)


def gws_command_for_request(
    method: str,
    path: str,
    query: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any]]:
    method = method.upper()
    query_values = clean_query(query)
    parts = [decode_path_part(part) for part in path.strip("/").split("/") if part]

    if method == "GET" and parts == ["users", "me", "calendarList"]:
        return ["calendarList", "list"], query_values
    if method == "POST" and parts == ["calendars"]:
        return ["calendars", "insert"], query_values
    if method == "PATCH" and parts[:3] == ["users", "me", "calendarList"] and len(parts) == 4:
        query_values["calendarId"] = parts[3]
        return ["calendarList", "patch"], query_values

    if len(parts) >= 3 and parts[0] == "calendars" and parts[2] == "events":
        calendar_id = parts[1]
        query_values["calendarId"] = calendar_id
        if len(parts) == 3:
            if method == "GET":
                return ["events", "list"], query_values
            if method == "POST":
                return ["events", "insert"], query_values
        if len(parts) == 4:
            query_values["eventId"] = parts[3]
            if method == "GET":
                return ["events", "get"], query_values
            if method == "PUT":
                return ["events", "update"], query_values
            if method == "DELETE":
                return ["events", "delete"], query_values

    raise GCalError(f"Unsupported Google Calendar API request for GWS: {method} {path}")


def gws_error(stdout: str, stderr: str, returncode: int) -> GCalError:
    message = (stderr or stdout or "").strip()
    message_lower = message.lower()
    if (
        returncode == 2
        or "No encrypted credentials found" in message
        or "auth failed" in message_lower
        or "insufficient authentication scopes" in message_lower
    ):
        return GwsAuthError(
            "GWS Calendar auth missing or invalid. Run `gws auth setup`, then "
            "`gws auth login --services calendar,drive`."
        )
    if "404" in message:
        return GCalError(f"Google Calendar API error 404: {message}")
    if "410" in message:
        return GCalError(f"Google Calendar API error 410: {message}")
    return GCalError(f"gws calendar failed with exit code {returncode}: {message}")


def gws_api_request(
    env: Env,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if shutil.which("gws") is None:
        raise GwsUnavailable("gws not found. Install dependencies, then run `gws auth setup`.")

    command_parts, params = gws_command_for_request(method, path, query)
    command = ["gws", "calendar", *command_parts, "--format", "json"]
    if params:
        command.extend(["--params", json.dumps(params, separators=(",", ":"))])
    if payload is not None:
        command.extend(["--json", json.dumps(payload, separators=(",", ":"))])

    result = subprocess.run(command, cwd=env.root, text=True, capture_output=True)
    if result.returncode != 0:
        raise gws_error(result.stdout, result.stderr, result.returncode)
    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GCalError(f"gws calendar returned invalid JSON: {raw}") from exc


def api_request(
    env: Env,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return gws_api_request(env, method, path, payload=payload, query=query)


def api_request_optional(env: Env, method: str, path: str, **kwargs: Any) -> dict[str, Any] | None:
    try:
        return api_request(env, method, path, **kwargs)
    except GCalError as exc:
        if "API error 404" in str(exc) or "API error 410" in str(exc):
            return None
        raise


def command_auth(env: Env) -> int:
    _ = env
    print("Google Calendar auth uses GWS.")
    print("Run:")
    print("  gws auth setup")
    print("  gws auth login --services calendar,drive")
    print("  vault gcal calendars ensure --apply")
    return 0


def calendar_name(env: Env, key: str) -> str:
    config_keys, default = CALENDAR_NAME_CONFIG[key]
    return str(env.setting(config_keys, default))


def list_calendars(env: Env) -> list[dict[str, Any]]:
    calendars: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = api_request(env, "GET", "/users/me/calendarList", query={"pageToken": page_token})
        calendars.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return calendars


def calendar_map(env: Env) -> dict[str, dict[str, Any]]:
    return {item.get("summary", ""): item for item in list_calendars(env)}


def ensure_calendars(env: Env, apply: bool) -> dict[str, str]:
    existing = calendar_map(env)
    ids: dict[str, str] = {}
    for key in ("time-blocks", "scheduled", "due"):
        name = calendar_name(env, key)
        if name in existing:
            ids[key] = existing[name]["id"]
            print(f"exists: {name} ({ids[key]})")
            ensure_calendar_reminders(env, key, ids[key], existing[name], apply)
            continue
        if not apply:
            print(f"would create: {name}")
            print(f"would set default reminders: {name} {DEFAULT_CALENDAR_REMINDERS[key]}")
            continue
        created = api_request(env, "POST", "/calendars", {"summary": name})
        ids[key] = created["id"]
        print(f"created: {name} ({ids[key]})")
        ensure_calendar_reminders(env, key, ids[key], None, apply)
    return ids


def ensure_calendar_reminders(
    env: Env,
    key: str,
    calendar_id: str,
    calendar_list_entry: dict[str, Any] | None,
    apply: bool,
) -> None:
    desired = DEFAULT_CALENDAR_REMINDERS[key]
    existing = (calendar_list_entry or {}).get("defaultReminders", [])
    if normalize_reminders(existing) == normalize_reminders(desired):
        print(f"default reminders ok: {calendar_name(env, key)} {desired}")
        return
    if not apply:
        print(
            f"would update default reminders: {calendar_name(env, key)} "
            f"{existing} -> {desired}"
        )
        return
    api_request(
        env,
        "PATCH",
        f"/users/me/calendarList/{urllib.parse.quote(calendar_id, safe='')}",
        {"defaultReminders": desired},
    )
    print(f"updated default reminders: {calendar_name(env, key)} {desired}")


def normalize_reminders(reminders: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return sorted(
        (str(item.get("method", "popup")), int(item.get("minutes", 0)))
        for item in reminders
    )


def command_calendars(env: Env, args: argparse.Namespace) -> int:
    if args.calendar_command != "ensure":
        raise GCalError(f"Unknown calendars command: {args.calendar_command}")
    apply = bool(args.apply)
    if not apply and not args.dry_run:
        print("Defaulting to dry run. Pass --apply to create missing calendars.")
    ensure_calendars(env, apply=apply)
    return 0


def parse_local_datetime(value: str, env: Env) -> dt.datetime:
    normalized = value.strip().replace(" ", "T")
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=env.timezone)
    return parsed.astimezone(env.timezone)


def date_or_datetime_to_event(value: str, env: Env, duration_minutes: int) -> tuple[dict[str, str], dict[str, str]]:
    value = value.strip()
    if "T" not in value and len(value) == 10:
        start = dt.date.fromisoformat(value)
        end = start + dt.timedelta(days=1)
        return {"date": start.isoformat()}, {"date": end.isoformat()}
    start_dt = parse_local_datetime(value, env)
    end_dt = start_dt + dt.timedelta(minutes=duration_minutes)
    return (
        {"dateTime": start_dt.isoformat(), "timeZone": env.timezone_name},
        {"dateTime": end_dt.isoformat(), "timeZone": env.timezone_name},
    )


def event_to_task_value(event: dict[str, Any], env: Env) -> str:
    start = event.get("start", {})
    if start.get("date"):
        return str(start["date"])
    date_time = start.get("dateTime")
    if not date_time:
        return ""
    parsed = dt.datetime.fromisoformat(date_time.replace("Z", "+00:00")).astimezone(env.timezone)
    return parsed.strftime("%Y-%m-%dT%H:%M")


def rfc3339_range(env: Env, from_date: str | None, days: int) -> tuple[str, str]:
    if from_date:
        if "T" in from_date or " " in from_date:
            start = parse_local_datetime(from_date, env)
        else:
            start = dt.datetime.combine(dt.date.fromisoformat(from_date), dt.time.min, env.timezone)
    else:
        start = dt.datetime.now(env.timezone)
    end = start + dt.timedelta(days=days)
    return start.isoformat(), end.isoformat()


def resolve_calendar_ids(env: Env, selector: str) -> list[tuple[str, str]]:
    if selector in {"primary", "default"}:
        return [("Default", "primary")]
    calendars = list_calendars(env)
    if selector == "all":
        return [(item.get("summary", item["id"]), item["id"]) for item in calendars]
    required_names = {calendar_name(env, key): key for key in DEFAULT_CALENDAR_NAMES}
    names = {item.get("summary", ""): item["id"] for item in calendars}
    ids = {item["id"]: item.get("summary", item["id"]) for item in calendars}
    if selector in names:
        return [(selector, names[selector])]
    if selector in DEFAULT_CALENDAR_NAMES:
        name = calendar_name(env, selector)
        if name in names:
            return [(name, names[name])]
    if selector in required_names:
        name = calendar_name(env, required_names[selector])
        if name in names:
            return [(name, names[name])]
    if selector in ids:
        return [(ids[selector], selector)]
    raise GCalError(f"Calendar not found: {selector}")


def resolve_write_calendar_id(env: Env, selector: str) -> tuple[str, str]:
    matches = resolve_calendar_ids(env, selector)
    if len(matches) != 1:
        raise GCalError(f"Calendar selector must resolve to one calendar: {selector}")
    return matches[0]


def list_events(env: Env, calendar_id: str, time_min: str, time_max: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = api_request(
            env,
            "GET",
            f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events",
            query={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "pageToken": page_token,
            },
        )
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return events


def compact_event(calendar_name_value: str, event: dict[str, Any], env: Env) -> dict[str, Any]:
    return {
        "calendar": calendar_name_value,
        "id": event.get("id"),
        "title": event.get("summary", ""),
        "start": event_to_task_value(event, env),
        "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
        "status": event.get("status"),
        "htmlLink": event.get("htmlLink"),
    }


def command_list(env: Env, args: argparse.Namespace) -> int:
    time_min, time_max = rfc3339_range(env, args.from_date, args.days)
    output: list[dict[str, Any]] = []
    for label, calendar_id in resolve_calendar_ids(env, args.calendar):
        for event in list_events(env, calendar_id, time_min, time_max):
            output.append(compact_event(label, event, env))
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        for item in output:
            print(f"{item['start']} [{item['calendar']}] {item['title']}")
    return 0


def event_payload(
    title: str,
    start_value: str,
    end_value: str | None,
    env: Env,
    description: str = "",
    private: dict[str, str] | None = None,
    duration_minutes: int | None = None,
) -> dict[str, Any]:
    start = parse_local_datetime(start_value, env)
    duration = duration_minutes if duration_minutes is not None else env.default_event_duration
    end = parse_local_datetime(end_value, env) if end_value else start + dt.timedelta(minutes=duration)
    payload: dict[str, Any] = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": env.timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": env.timezone_name},
    }
    if private:
        payload["extendedProperties"] = {"private": private}
    return payload


def command_create_event(env: Env, args: argparse.Namespace) -> int:
    apply = bool(args.apply)
    if not apply and not args.dry_run:
        print("Defaulting to dry run. Pass --apply to create the default-calendar event.")
    calendar_selector = args.calendar or env.default_event_calendar
    payload = event_payload(
        args.title,
        args.start,
        args.end,
        env,
        description=args.description,
        private={"syncOwner": "vault-gcal-event", "vaultRoot": str(env.root)},
        duration_minutes=env.default_event_duration,
    )
    if not apply:
        result = {"calendar": calendar_selector, "event": payload}
    else:
        _, calendar_id = resolve_write_calendar_id(env, calendar_selector)
        result = create_event(env, calendar_id, payload)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_create_block(env: Env, args: argparse.Namespace) -> int:
    apply = bool(args.apply)
    if not apply and not args.dry_run:
        print("Defaulting to dry run. Pass --apply to create the Time Blocks event.")
    ids = ensure_calendars(env, apply=apply)
    time_blocks_id = ids.get("time-blocks")
    payload = event_payload(
        args.title,
        args.start,
        args.end,
        env,
        description=args.description,
        private={"syncOwner": "vault-gcal-time-block", "vaultRoot": str(env.root)},
        duration_minutes=env.default_block_duration,
    )
    if not apply:
        result = {"calendar": calendar_name(env, "time-blocks"), "event": payload}
    else:
        if not time_blocks_id:
            time_blocks_id = calendar_map(env)[calendar_name(env, "time-blocks")]["id"]
        result = api_request(
            env,
            "POST",
            f"/calendars/{urllib.parse.quote(time_blocks_id, safe='')}/events",
            payload,
        )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def parse_frontmatter(text: str) -> tuple[list[str], dict[str, Any], int] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    body_start = end + 4
    if body_start < len(text) and text[body_start] == "\n":
        body_start += 1
    lines = text[4:end].splitlines()
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for line in lines:
        if line.startswith("  - ") and current_key and current_list is not None:
            current_list.append(line[4:].strip().strip('"'))
            continue
        current_key = None
        current_list = None
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            current_key = key
            current_list = []
            data[key] = current_list
            continue
        data[key] = value.strip('"').strip("'")
    return lines, data, body_start


def active_context_folders(root: Path) -> list[Path]:
    folders: list[Path] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith(".") or folder.name.startswith("_"):
            continue
        note = context_folder_note_path(folder)
        if not note.exists():
            continue
        text = note.read_text(encoding="utf-8")
        parsed = parse_frontmatter(text)
        if parsed and parsed[1].get("context_registered", "true").strip().lower() in {"false", "no", "0"}:
            continue
        status = parsed[1].get("status") if parsed else None
        if status == "active":
            folders.append(folder)
    return folders


def read_tasks(root: Path) -> list[TaskNote]:
    tasks: list[TaskNote] = []
    for folder in active_context_folders(root):
        for path in sorted((folder / "_obsidian" / "tasks").glob("*.md")):
            if "/archive/" in path.as_posix():
                continue
            text = path.read_text(encoding="utf-8")
            parsed = parse_frontmatter(text)
            if not parsed:
                continue
            lines, data, body_start = parsed
            tags = data.get("tags", [])
            if "task" not in tags:
                continue
            tasks.append(
                TaskNote(
                    path=path,
                    rel_path=path.relative_to(root).as_posix(),
                    text=text,
                    body_start=body_start,
                    fm_lines=lines,
                    data=data,
                )
            )
    return tasks


def frontmatter_quote(value: str) -> str:
    if value == "":
        return '""'
    if any(ch in value for ch in [":", "#", "[", "]", "{", "}", ",", '"']):
        return json.dumps(value)
    return value


def set_frontmatter_value(task: TaskNote, key: str, value: str | None) -> None:
    new_lines: list[str] = []
    found = False
    skip_list = False
    for line in task.fm_lines:
        if skip_list:
            if line.startswith("  - "):
                new_lines.append(line)
                continue
            skip_list = False
        if line.split(":", 1)[0].strip() == key and ":" in line and not line.startswith(" "):
            found = True
            if value is not None:
                new_lines.append(f"{key}: {frontmatter_quote(value)}")
            skip_list = line.endswith(":")
            continue
        new_lines.append(line)
    if value is not None and not found:
        new_lines.append(f"{key}: {frontmatter_quote(value)}")
    task.fm_lines = new_lines
    if value is None:
        task.data.pop(key, None)
    else:
        task.data[key] = value


def write_task(task: TaskNote) -> None:
    body = task.text[task.body_start :]
    task.path.write_text("---\n" + "\n".join(task.fm_lines) + "\n---\n" + body, encoding="utf-8")


def task_event_payload(task: TaskNote, field: str, env: Env) -> dict[str, Any]:
    value = str(task.data[field])
    start, end = date_or_datetime_to_event(value, env, env.default_task_duration)
    private = {
        "syncOwner": SYNC_OWNER,
        "vaultRoot": str(env.root),
        "taskPath": task.rel_path,
        "taskField": field,
    }
    return {
        "summary": task.title,
        "description": f"Mirrored from TaskNotes.\n\nTask: {task.rel_path}",
        "start": start,
        "end": end,
        "extendedProperties": {"private": private},
    }


def get_event(env: Env, calendar_id: str, event_id: str) -> dict[str, Any] | None:
    return api_request_optional(
        env,
        "GET",
        f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events/{urllib.parse.quote(event_id, safe='')}",
    )


def create_event(env: Env, calendar_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return api_request(env, "POST", f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events", payload)


def update_event(env: Env, calendar_id: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return api_request(
        env,
        "PUT",
        f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events/{urllib.parse.quote(event_id, safe='')}",
        payload,
    )


def delete_event(env: Env, calendar_id: str, event_id: str) -> None:
    api_request_optional(
        env,
        "DELETE",
        f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events/{urllib.parse.quote(event_id, safe='')}",
    )


def event_private_properties(event: dict[str, Any]) -> dict[str, str]:
    private = (event.get("extendedProperties") or {}).get("private") or {}
    return {str(key): str(value) for key, value in private.items()}


def event_needs_payload_refresh(event: dict[str, Any], payload: dict[str, Any]) -> bool:
    if event.get("summary", "") != payload.get("summary", ""):
        return True
    if event.get("description", "") != payload.get("description", ""):
        return True
    event_private = event_private_properties(event)
    desired_private = ((payload.get("extendedProperties") or {}).get("private") or {})
    return any(event_private.get(str(key)) != str(value) for key, value in desired_private.items())


def list_owned_task_events(env: Env, calendar_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = api_request(
            env,
            "GET",
            f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events",
            query={
                "singleEvents": "true",
                "showDeleted": "false",
                "privateExtendedProperty": f"syncOwner={SYNC_OWNER}",
                "pageToken": page_token,
            },
        )
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return events


def referenced_event_ids(tasks: list[TaskNote]) -> set[str]:
    ids: set[str] = set()
    for task in tasks:
        for cfg in FIELD_CONFIG.values():
            event_id = str(task.data.get(cfg["event_id"]) or "")
            if event_id:
                ids.add(event_id)
    return ids


def all_existing_task_event_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for path in sorted(root.glob("*/_obsidian/tasks/*.md")):
        if path.parts[-4].startswith(".") or path.parts[-4].startswith("_"):
            continue
        if "/archive/" in path.as_posix():
            continue
        parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not parsed:
            continue
        data = parsed[1]
        tags = data.get("tags", [])
        if "task" not in tags:
            continue
        for cfg in FIELD_CONFIG.values():
            event_id = str(data.get(cfg["event_id"]) or "")
            if event_id:
                ids.add(event_id)
    return ids


def prune_orphaned_task_events(
    env: Env,
    calendar_ids: dict[str, str],
    tasks: list[TaskNote],
    apply: bool,
) -> list[str]:
    referenced_ids = referenced_event_ids(tasks) | all_existing_task_event_ids(env.root)
    actions: list[str] = []
    for field in ("scheduled", "due"):
        calendar_id = calendar_ids.get(field)
        if not calendar_id:
            continue
        for event in list_owned_task_events(env, calendar_id):
            event_id = str(event.get("id") or "")
            if event_private_properties(event).get("syncOwner") != SYNC_OWNER:
                continue
            if not event_id or event_id in referenced_ids:
                continue
            task_path = event_private_properties(event).get("taskPath", "")
            if apply:
                delete_event(env, calendar_id, event_id)
            actions.append(f"prune-orphaned-task-event:{field}:{event_id}:{task_path}")
    return actions


def store_sync_metadata(task: TaskNote, field: str, event: dict[str, Any], value: str, now: str) -> None:
    cfg = FIELD_CONFIG[field]
    set_frontmatter_value(task, cfg["event_id"], str(event["id"]))
    set_frontmatter_value(task, cfg["last_value"], value)
    set_frontmatter_value(task, cfg["last_event_updated"], str(event.get("updated", "")))
    set_frontmatter_value(task, cfg["last_synced_at"], now)


def clear_sync_metadata(task: TaskNote, field: str) -> None:
    cfg = FIELD_CONFIG[field]
    for key in (cfg["event_id"], cfg["last_value"], cfg["last_event_updated"], cfg["last_synced_at"]):
        set_frontmatter_value(task, key, None)


def sync_task_field(
    env: Env,
    task: TaskNote,
    field: str,
    calendar_id: str,
    apply: bool,
    accept_calendar_deletes: bool,
    now: str,
) -> tuple[str, bool]:
    cfg = FIELD_CONFIG[field]
    value = str(task.data.get(field) or "")
    event_id = str(task.data.get(cfg["event_id"]) or "")
    last_value = str(task.data.get(cfg["last_value"]) or "")
    dirty = False

    event = get_event(env, calendar_id, event_id) if event_id else None

    if event_id and event is None:
        if accept_calendar_deletes:
            if apply:
                set_frontmatter_value(task, field, None)
                clear_sync_metadata(task, field)
                dirty = True
            return f"calendar-delete-clears-task:{field}:{task.rel_path}", dirty
        if value:
            payload = task_event_payload(task, field, env)
            if apply:
                event = create_event(env, calendar_id, payload)
                store_sync_metadata(task, field, event, value, now)
                dirty = True
            return f"recreate-missing-event:{field}:{task.rel_path}", dirty
        if apply:
            clear_sync_metadata(task, field)
            dirty = True
        return f"clear-stale-event-id:{field}:{task.rel_path}", dirty

    if not value:
        if event_id and event:
            if apply:
                delete_event(env, calendar_id, event_id)
                clear_sync_metadata(task, field)
                dirty = True
            return f"delete-event-task-date-cleared:{field}:{task.rel_path}", dirty
        return f"skip-empty:{field}:{task.rel_path}", dirty

    if not event:
        payload = task_event_payload(task, field, env)
        if apply:
            event = create_event(env, calendar_id, payload)
            store_sync_metadata(task, field, event, value, now)
            dirty = True
        return f"create-event:{field}:{task.rel_path}", dirty

    event_value = event_to_task_value(event, env)
    if not last_value:
        if apply:
            event = update_event(env, calendar_id, event_id, task_event_payload(task, field, env))
            store_sync_metadata(task, field, event, value, now)
            dirty = True
        return f"initialize-sync-state:{field}:{task.rel_path}", dirty

    task_changed = value != last_value
    event_changed = event_value != last_value
    if task_changed and event_changed and event_value != value:
        return f"conflict:{field}:{task.rel_path}:task={value}:calendar={event_value}:last={last_value}", dirty
    if task_changed:
        if apply:
            event = update_event(env, calendar_id, event_id, task_event_payload(task, field, env))
            store_sync_metadata(task, field, event, value, now)
            dirty = True
        return f"update-event-from-task:{field}:{task.rel_path}", dirty
    if event_changed:
        if apply:
            set_frontmatter_value(task, field, event_value)
            store_sync_metadata(task, field, event, event_value, now)
            dirty = True
        return f"update-task-from-event:{field}:{task.rel_path}", dirty
    payload = task_event_payload(task, field, env)
    if event_needs_payload_refresh(event, payload):
        if apply:
            update_event(env, calendar_id, event_id, payload)
        return f"refresh-event-metadata:{field}:{task.rel_path}", dirty
    return f"unchanged:{field}:{task.rel_path}", dirty


def command_sync_tasks(env: Env, args: argparse.Namespace) -> int:
    apply = bool(args.apply)
    if not apply and not args.dry_run:
        print("Defaulting to dry run. Pass --apply to sync tasks and calendars.")
    calendar_ids = ensure_calendars(env, apply=apply)
    if apply:
        calendar_ids = calendar_ids or {
            key: calendar_map(env)[calendar_name(env, key)]["id"] for key in DEFAULT_CALENDAR_NAMES
        }
    else:
        existing = calendar_map(env)
        calendar_ids = {
            key: existing[calendar_name(env, key)]["id"]
            for key in ("scheduled", "due")
            if calendar_name(env, key) in existing
        }
    missing = [key for key in ("scheduled", "due") if key not in calendar_ids]
    if missing and apply:
        raise GCalError(f"Missing required calendars after ensure: {', '.join(missing)}")

    now = dt.datetime.now(env.timezone).isoformat(timespec="seconds")
    actions: list[str] = []
    dirty_tasks: set[Path] = set()
    tasks = read_tasks(env.root)
    for task in tasks:
        for field in ("scheduled", "due"):
            if field not in calendar_ids:
                actions.append(f"skip-missing-calendar:{field}:{task.rel_path}")
                continue
            action, dirty = sync_task_field(
                env,
                task,
                field,
                calendar_ids[field],
                apply,
                args.accept_calendar_deletes,
                now,
            )
            actions.append(action)
            if dirty:
                dirty_tasks.add(task.path)
        if apply and task.path in dirty_tasks:
            write_task(task)
    if args.prune_orphaned_task_events:
        actions.extend(prune_orphaned_task_events(env, calendar_ids, tasks, apply))

    summary = {
        "apply": apply,
        "actions": actions,
        "counts": {prefix: sum(1 for item in actions if item.startswith(prefix)) for prefix in sorted({a.split(":", 1)[0] for a in actions})},
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for action in actions:
            if not action.startswith("skip-empty") and not action.startswith("unchanged"):
                print(action)
        print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    root = resolve_vault_root(args.root, __file__)
    env = load_env(root)
    try:
        if args.command == "auth":
            return command_auth(env)
        if args.command == "calendars":
            return command_calendars(env, args)
        if args.command == "list":
            return command_list(env, args)
        if args.command == "create-event":
            return command_create_event(env, args)
        if args.command == "create-block":
            return command_create_block(env, args)
        if args.command == "sync-tasks":
            return command_sync_tasks(env, args)
        raise GCalError(f"Unknown command: {args.command}")
    except GCalError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
