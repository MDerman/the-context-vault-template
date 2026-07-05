---
type: agent-reference
status: enabled
---
# Google Calendar

### First-Time Google Workspace Setup

The vault Google Calendar helper uses GWS credentials. `vault gcal` keeps the TaskNotes mirror logic locally, but Calendar API calls go through the `gws` CLI.

```bash
gws auth setup
gws auth login --scopes calendar,drive
```

`gws auth setup` creates or configures the Google Cloud/OAuth pieces. `gws auth login` opens browser OAuth and stores encrypted credentials in GWS's normal config outside the vault.

`vault gcal auth` is compatibility help only; it prints the GWS commands above.

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
vault gcal sync-tasks --dry-run --prune-orphaned-task-events
```

`--prune-orphaned-task-events` deletes only vault-owned mirror events in `Scheduled Tasks` and `Due Tasks` whose event IDs are no longer referenced by any current TaskNotes task. This catches deleted task files without deleting manual calendar events or live mirrored tasks whose stored `taskPath` is stale.

Agents should use `vault gcal create-event` for concrete appointments, travel, meetings, reservations, and dated personal or business events. It writes to the default calendar (`primary`) unless `--calendar` or the calendar config says otherwise. Use `vault gcal create-block` only when the user explicitly asks for time blocking or broad planning blocks. Broad work planning should usually use `Time Blocks`; add TaskNotes `scheduled` only when a task genuinely needs a specific work date/time.

When Obsidian is open, Context Nine runs `vault gcal sync-tasks --apply` every 5 minutes. `vault refresh` runs `vault gcal sync-tasks --apply --prune-orphaned-task-events` once before regenerating context.

Implementation script: `_master/system/scripts/gcal.py`. GWS credentials live outside the vault. Tracked vault calendar behavior config lives in `_master/system/config/calendar.json`. Process environment variables can still override calendar settings for local emergency runs, but `_master/env/.env` is no longer part of normal calendar config.
