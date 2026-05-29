#!/usr/bin/env python3
"""Google Calendar helpers for vault time blocks and TaskNotes date mirrors."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from script_utils import resolve_vault_root


API_ROOT = "https://www.googleapis.com/calendar/v3"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar"
SYNC_OWNER = "vault-gcal-task-mirror"

CALENDAR_ENV_KEYS = {
    "time-blocks": "GOOGLE_CALENDAR_TIME_BLOCKS_NAME",
    "scheduled": "GOOGLE_CALENDAR_SCHEDULED_TASKS_NAME",
    "due": "GOOGLE_CALENDAR_DUE_TASKS_NAME",
}
DEFAULT_CALENDAR_NAMES = {
    "time-blocks": "Time Blocks",
    "scheduled": "Scheduled Tasks",
    "due": "Due Tasks",
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


@dataclass
class Env:
    root: Path
    env_dir: Path
    values: dict[str, str]

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key) or os.environ.get(key, default)

    @property
    def token_path(self) -> Path:
        raw = self.get("GOOGLE_ACCOUNT_TOKEN_PATH", "")
        if raw:
            path = resolve_env_path(self.root, raw)
            legacy_path = resolve_env_path(
                self.root, self.get("GOOGLE_CALENDAR_TOKEN_PATH", "master/env/.gcal-token.json")
            )
            if not path.exists() and legacy_path.exists():
                return legacy_path
            return path
        legacy_raw = self.get("GOOGLE_CALENDAR_TOKEN_PATH", "")
        if legacy_raw:
            return resolve_env_path(self.root, legacy_raw)
        legacy_default = resolve_env_path(self.root, "master/env/.gcal-token.json")
        if legacy_default.exists():
            return legacy_default
        return resolve_env_path(self.root, "master/env/.google-account-token.json")

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.get("GOOGLE_CALENDAR_TIME_ZONE", "Africa/Johannesburg"))

    @property
    def default_task_duration(self) -> int:
        raw = self.get("GOOGLE_CALENDAR_TASK_DEFAULT_DURATION_MINUTES", "60")
        return max(1, int(raw))

    @property
    def default_block_duration(self) -> int:
        raw = self.get("GOOGLE_CALENDAR_BLOCK_DEFAULT_DURATION_MINUTES", "240")
        return max(1, int(raw))


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

    block = subparsers.add_parser("create-block", help="Create a Time Blocks event.")
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
    sync.add_argument("--json", action="store_true", help="Emit JSON summary.")

    return parser.parse_args()


def resolve_env_path(root: Path, raw: str) -> Path:
    path = Path(os.path.expanduser(raw))
    if not path.is_absolute():
        path = root / path
    return path


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_env(root: Path) -> Env:
    env_dir = root / "master" / "env"
    values = parse_env_file(env_dir / ".env.base")
    values.update(parse_env_file(env_dir / ".env"))
    return Env(root=root, env_dir=env_dir, values=values)


def require_client(env: Env) -> tuple[str, str]:
    client_id = env.get("GOOGLE_ACCOUNT_CLIENT_ID", env.get("GOOGLE_CALENDAR_CLIENT_ID"))
    client_secret = env.get("GOOGLE_ACCOUNT_CLIENT_SECRET", env.get("GOOGLE_CALENDAR_CLIENT_SECRET"))
    if not client_id or not client_secret:
        raise GCalError(
            "Missing GOOGLE_ACCOUNT_CLIENT_ID or GOOGLE_ACCOUNT_CLIENT_SECRET. "
            "Add them to master/env/.env."
        )
    return client_id, client_secret


def read_token(env: Env) -> dict[str, Any]:
    if not env.token_path.exists():
        raise GCalError("No Google token found. Run `vault gcal auth` first.")
    return json.loads(env.token_path.read_text(encoding="utf-8"))


def write_token(env: Env, token: dict[str, Any]) -> None:
    env.token_path.parent.mkdir(parents=True, exist_ok=True)
    env.token_path.write_text(json.dumps(token, indent=2, sort_keys=True), encoding="utf-8")
    try:
        env.token_path.chmod(0o600)
    except OSError:
        pass


def token_expired(token: dict[str, Any]) -> bool:
    return float(token.get("expires_at", 0)) < time.time() + 60


def token_request(payload: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def refresh_token(env: Env, token: dict[str, Any]) -> dict[str, Any]:
    client_id, client_secret = require_client(env)
    if not token.get("refresh_token"):
        raise GCalError("Stored token has no refresh_token. Run `vault gcal auth` again.")
    refreshed = token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        }
    )
    token.update(refreshed)
    token["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
    write_token(env, token)
    return token


def access_token(env: Env) -> str:
    token = read_token(env)
    if token_expired(token):
        token = refresh_token(env, token)
    return str(token["access_token"])


def api_request(
    env: Env,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{API_ROOT}{path}"
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {access_token(env)}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise GCalError(f"Google Calendar API error {exc.code}: {raw}") from exc


def api_request_optional(env: Env, method: str, path: str, **kwargs: Any) -> dict[str, Any] | None:
    try:
        return api_request(env, method, path, **kwargs)
    except GCalError as exc:
        if "API error 404" in str(exc) or "API error 410" in str(exc):
            return None
        raise


class OAuthHandler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        OAuthHandler.code = params.get("code", [None])[0]
        OAuthHandler.error = params.get("error", [None])[0]
        body = b"Google Calendar authorization complete. You can close this tab."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def command_auth(env: Env) -> int:
    client_id, client_secret = require_client(env)
    server = HTTPServer(("127.0.0.1", 0), OAuthHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    url = f"{AUTH_URL}?{query}"
    print(f"Opening browser for Google Calendar authorization:\n{url}")
    webbrowser.open(url)
    server.handle_request()
    if OAuthHandler.error:
        raise GCalError(f"OAuth failed: {OAuthHandler.error}")
    if not OAuthHandler.code:
        raise GCalError("OAuth did not return an authorization code.")
    token = token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": OAuthHandler.code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    )
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    write_token(env, token)
    print(f"Wrote token to {env.token_path}")
    return 0


def calendar_name(env: Env, key: str) -> str:
    return env.get(CALENDAR_ENV_KEYS[key], DEFAULT_CALENDAR_NAMES[key])


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
        {"dateTime": start_dt.isoformat(), "timeZone": env.get("GOOGLE_CALENDAR_TIME_ZONE", "Africa/Johannesburg")},
        {"dateTime": end_dt.isoformat(), "timeZone": env.get("GOOGLE_CALENDAR_TIME_ZONE", "Africa/Johannesburg")},
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
) -> dict[str, Any]:
    start = parse_local_datetime(start_value, env)
    end = parse_local_datetime(end_value, env) if end_value else start + dt.timedelta(minutes=env.default_block_duration)
    payload: dict[str, Any] = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": env.get("GOOGLE_CALENDAR_TIME_ZONE", "Africa/Johannesburg")},
        "end": {"dateTime": end.isoformat(), "timeZone": env.get("GOOGLE_CALENDAR_TIME_ZONE", "Africa/Johannesburg")},
    }
    if private:
        payload["extendedProperties"] = {"private": private}
    return payload


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
    for folder in sorted(root.glob("[0-9][0-9]-*")):
        if not folder.is_dir():
            continue
        home = folder / "HOME.md"
        if not home.exists():
            continue
        text = home.read_text(encoding="utf-8")
        parsed = parse_frontmatter(text)
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
    for task in read_tasks(env.root):
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
