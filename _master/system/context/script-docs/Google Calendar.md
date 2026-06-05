---
type: agent-reference
status: enabled
---
# Google Calendar

### First-Time Token Setup

The vault Google Calendar helper uses a local OAuth desktop-client flow. It does not reuse TaskNotes plugin tokens.

1. Go to Google Cloud Console and create or choose a project.
2. Enable the Google Calendar API for that project.
3. Configure the Google Auth Platform / OAuth consent screen. For personal use, keep the app in testing and add your own Google account as a test user if Google asks.
4. Create an OAuth client ID with application type `Desktop app`.
5. Copy the generated client ID and client secret into `_master/env/.env`:

```bash
GOOGLE_ACCOUNT_CLIENT_ID="..."
GOOGLE_ACCOUNT_CLIENT_SECRET="..."
GOOGLE_ACCOUNT_TOKEN_PATH="_master/env/.google-account-token.json"
```

`_master/env/.env` is ignored by git. Keep `_master/env/.env.base` as the tracked template only.

Then authorize the vault-owned Google Calendar helper:

```bash
vault gcal auth
```

This opens a browser, asks Google for Calendar access, and writes the local token to `_master/env/.google-account-token.json` by default. That token is ignored by git. The helper still accepts the older `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET`, and `.gcal-token.json` names during migration.

Relevant official Google docs:

- [Google Calendar API Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)
- [Create access credentials](https://developers.google.com/workspace/guides/create-credentials)
- [OAuth 2.0 for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app)

Create or find the required calendars:

```bash
vault gcal calendars ensure --dry-run
vault gcal calendars ensure --apply
```

The required calendars are:

- `Time Blocks`: broad manual or AI-created planning blocks.
- `Scheduled Tasks`: two-way mirror of TaskNotes `scheduled`.
- `Due Tasks`: two-way mirror of TaskNotes `due`.

`vault gcal calendars ensure --apply` also sets supported Google Calendar default popup reminders:

- `Time Blocks`: 0 minutes before event start.
- `Scheduled Tasks`: 0 minutes before event start.
- `Due Tasks`: 0 minutes before event start and 25 minutes before event start.

Google Calendar's API exposes calendar default reminders as minutes before event start. It does not expose the Google Calendar UI's separate all-day default reminder setting such as "0 days before at 9:00 AM"; set that all-day default manually in Google Calendar settings if needed.

Low-context calendar read for agents:

```bash
vault gcal list --days 7 --calendar all --json
```

Create a specific event on the default Google Calendar:

```bash
vault gcal create-event --title "Flight QR1372: Cape Town to Doha" --start "2026-06-02T19:30:00+02:00" --end "2026-06-03T06:00:00+03:00" --apply
```

Create a broad work block on `Time Blocks`:

```bash
vault gcal create-block --title "AppSumo Launch Block" --start "2026-05-18T09:00" --end "2026-05-18T13:00" --apply
```

Mirror TaskNotes dates:

```bash
vault gcal sync-tasks --dry-run
vault gcal sync-tasks --apply
```

Agents should use `vault gcal create-event` for concrete appointments, travel, meetings, reservations, and dated personal or business events. It writes to the default calendar (`primary`) unless `--calendar` or `GOOGLE_CALENDAR_DEFAULT_EVENT_CALENDAR` says otherwise. Use `vault gcal create-block` only when the user explicitly asks for time blocking or broad planning blocks. Broad work planning should usually use `Time Blocks`; add TaskNotes `scheduled` only when a task genuinely needs a specific work date/time.

When Obsidian is open, Context Nine runs `vault gcal sync-tasks --apply` every 5 minutes. `vault refresh` also runs the sync once before regenerating context.

Implementation script: `_master/system/scripts/gcal.py`. Local secrets live in `_master/env/.env`, with tracked placeholders in `_master/env/.env.base`.
