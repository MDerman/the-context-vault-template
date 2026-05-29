---
type: agent-reference
status: enabled
---
# SCRIPTS

Use the terminal command first:

```bash
vault --help
```

It is installed by `_master/system/bootstrap/install_vault_command.py` into `~/.local/bin/vault`.

Main script implementations live in:

```text
_master/system/scripts/
```

Vault Command Center command labels, argument arrays, and hover descriptions are shared through [[_master/system/scripts/vault-commands.json]]. Update that JSON when a cockpit-visible command description changes.

Use these for normal vault operations.

## Root

Print the current vault root discovered from the installed dispatcher:

```bash
vault root
```

## Init Vault

Run first-time setup after placing a fresh/exported vault in iCloud:

```bash
_master/system/bootstrap/init_vault.sh
```

Dry-run the default/configured setup:

```bash
_master/system/bootstrap/init_vault.sh --dry-run --non-interactive
```

The init script installs/checks dependencies, prompts for context folders, runs bootstrap, generates `AGENTS.md`, syncs agent skills, installs the `vault` command, and optionally sets up Git/LFS with the Git directory outside iCloud.
User Git/LFS is off by default; pass `--enable-git` when intentionally creating a personal vault repository.

Context-folder answers are stored in:

```text
_master/system/bootstrap/init-vault-config.json
```

Root `AGENTS.md` is generated from:

```text
_master/system/bootstrap/AGENTS.template.md
```

## Bootstrap Export

Export the public bootstrap vault from the current vault:

```bash
vault bootstrap-export --dry-run
vault bootstrap-export --force
```

The export writes a root `README.md` from `_master/system/bootstrap/README-bootstrap.md`. Internal bootstrap/export mechanics live in `_master/system/bootstrap/bootstrapdocs.md`. With `--force`, the exporter mirrors export-owned files into the configured export root while preserving repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs.

Default export root and context folder output mapping live in:

```text
_master/system/bootstrap/bootstrap-export.json
```

Implementation script: `_master/system/scripts/bootstrap_export.py`.

## Public Vault Upgrade

Public bootstrap installs keep upstream Git state outside iCloud and use it for setup updates:

```bash
vault upgrade status
vault upgrade --dry-run
vault upgrade --apply
vault upgrade doctor
vault upgrade repair-prompt
```

Install metadata lives in `.vault-bootstrap/install.json`; exported policy and release metadata live in `.vault-bootstrap/policy.json` and `.vault-bootstrap/release.json`. Upgrade reports live under `.vault-upgrade/`.

Implementation script: `_master/system/scripts/upgrade.py`.

## Agent Skills Sync

Preview or apply local coding-agent skill symlinks:

```bash
_master/system/bootstrap/sync-agent-skills.sh --dry-run
_master/system/bootstrap/sync-agent-skills.sh --apply
```

The script links local skill targets such as `~/.codex/skills` and `~/.claude/skills` to this vault's `_master/agents/skills`.

## Refresh

Current manual refresh:

```bash
vault refresh
```

The refresh wrapper ingests the configured Brain Dump Apple Note, runs the Google Calendar TaskNotes date mirror, regenerates agent context, then runs best-effort local Git maintenance.

Implementation script:

```bash
python3 _master/system/scripts/refresh.py
```

Brain Dump ingestion is configured in:

```text
_master/system/config.json
```

The default Apple Note is `Brain Dump`. New imports are inserted at the top of its single synced import file:

```text
_master/system/inbox/BRAIN_DUMP.md
```

Attachments are copied to:

```text
_master/system/inbox/BRAIN_DUMP_ATTACHMENTS/
```

After a successful write, the Apple Note body is cleared back to a blank placeholder. To ingest without clearing Brain Dump:

```bash
vault refresh --no-clear-brain-dump
```

To refresh all context folders:

```bash
vault refresh --all
```

To skip Brain Dump ingestion:

```bash
vault refresh --skip-brain-dump
```

To skip Google Calendar sync:

```bash
vault refresh --skip-gcal
```

To skip local Git maintenance:

```bash
vault refresh --skip-git-maintenance
```

Git maintenance keeps local history shallow at 5 commits by default and prunes unreachable local objects:

```bash
vault git-maintenance
vault git-maintenance --depth 5
```

Use `--git-depth N` on `vault refresh` to change the refresh-time depth.

## Agent Context

Regenerate compact agent-readable state:

```bash
vault context
```

This writes:

```text
_master/system/context/CONTEXT.md
_master/system/context/context.json
_master/system/context/*.md
_master/Dashboard.md
```

It also creates current 4-week content schedule notes for content-enabled context folders with enabled `DECLARATION/content-cadence.json`.
By default it removes stale generated agent periodic rollups; pass `--keep-agent-periodic-history` through `refresh.py` or `context.py` to preserve them.

Implementation script: `_master/system/scripts/context.py`.

## Inventory

Print low-context routing inventory for agents:

```bash
vault inventory
vault inventory --active-only
vault inventory --json
```

This lists context folders, configured TaskNotes statuses, epics, and projects without loading the larger agent context docs.

Implementation script: `_master/system/scripts/inventory.py`.

## Tasks And Projects

Create a TaskNotes task with validated existing project/epic links:

```bash
vault task create business "Follow up with partner" --project "Partnerships" --epic "Growth" --status up-next
```

Create a project note:

```bash
vault project create business "New Project" --epic "Growth" --status backlog
```

Use `vault inventory` first so task links use actual project and epic names. Use `vault task create --help` and `vault project create --help` for optional `due`, `scheduled`, `timeEstimate`, and dry-run flags.

Implementation scripts: `_master/system/scripts/task.py`, `_master/system/scripts/project.py`.

## Content Schedules

Generate current content schedule notes directly:

```bash
vault content
```

Content schedule notes live in `<context-folder>/_obsidian/content-schedules/` and normal refresh is create-only. `DECLARATION/content-cadence.json` controls `schedule_format` and `publication_order`. The generator also keeps the `Current content schedule:` line in the context folder `DECLARATION.md`.

Supported `schedule_format` values:

- `weekly`
- `weeklyThenByPublication`
- `publicationThenByWeek`

Regenerate an existing managed schedule note with:

```bash
vault content --context-folders personal-brand --date 2026-05-13 --force
```

Implementation script: `_master/system/scripts/content.py`.

## Periodic Rollups

Generate current agent-readable periodic rollups:

```bash
vault periodic
```

Useful variants:

```bash
vault periodic --all
vault periodic --context-folders dev,claudeche
vault periodic --keep-agent-periodic-history
```

Context folder periodic notes remain the editable source of truth. Agent rollups are generated readable views.

Monthly periodic notes are intentionally not used.

Implementation script: `_master/system/scripts/periodic.py`.

## Epics

Create an epic in a context folder and refresh the related TaskNotes views:

```bash
vault epic create business "New Epic"
```

This creates `<context-folder>/_obsidian/epics/<Epic>.md`, generates the per-epic Kanban Base under `<context-folder>/_obsidian/bases/`, and updates the managed epic views in [[_master/_obsidian/bases/tasks-kanban-v1.base]].

Useful variants:

```bash
vault epic list
vault epic sync
vault epic rename business "Old Epic" "New Epic"
vault epic delete business "New Epic"
vault epic delete business "New Epic" --force
```

Rename moves the epic note, updates its `title`, rewrites linked task references, regenerates per-epic task Bases, and updates the master task kanban epic views. Delete refuses to remove an epic while tasks still link to it unless `--force` is passed.

Implementation script: `_master/system/scripts/epic.py`.

## Google Calendar

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

Create a broad work block on `Time Blocks`:

```bash
vault gcal create-block --title "AppSumo Launch Block" --start "2026-05-18T09:00" --end "2026-05-18T13:00" --apply
```

Mirror TaskNotes dates:

```bash
vault gcal sync-tasks --dry-run
vault gcal sync-tasks --apply
```

Agents may create or edit `Time Blocks` but must not create arbitrary events on personal or business calendars. Broad work planning should usually use `Time Blocks`; add TaskNotes `scheduled` only when a task genuinely needs a specific work date/time.

When Obsidian is open, Context Nine runs `vault gcal sync-tasks --apply` every 5 minutes. `vault refresh` also runs the sync once before regenerating context.

Implementation script: `_master/system/scripts/gcal.py`. Local secrets live in `_master/env/.env`, with tracked placeholders in `_master/env/.env.base`.

## Brain Dump

Import the configured Apple Note directly:

```bash
vault sync
```

Brain Dump Apple Note deletion/clearing is only allowed through `refresh.py` or `brain_dump.py`, after the content and attachments have been written to the vault.

Implementation script: `_master/system/scripts/brain_dump.py`.

Organize the imported Brain Dump inbox through the vault skill:

```bash
vault triage prepare
vault triage clear-import
vault triage apply
```

The organize flow creates backups under `_master/system/inbox/BRAIN_DUMP_BACKUPS/`, proposal notes under `_master/system/inbox/BRAIN_DUMP_PROPOSALS/`, and the review Base at `_master/_obsidian/bases/BRAIN_DUMP_TRIAGE.base`.

## Attachments

Dry-run attachment routing and cleanup:

```bash
vault attachments
```

Apply the planned cleanup:

```bash
vault attachments --apply
```

Verify after cleanup:

```bash
vault attachments --verify-only
```

The vault convention is that note attachments live under the top-level root folder that owns the note, such as `_library/_obsidian/attachments` or `business/_obsidian/attachments`. Obsidian's built-in paste destination is the temporary inbox `_master/_obsidian/attachments/_inbox`.

Dry-run/apply reports and quarantined unreferenced import files are written outside the vault under `~/Downloads/vault-generated/`. After each dry-run or apply run, Finder opens that folder.

Implementation script: `_master/system/scripts/attachments.py`.

## Context Folders

Create/register a new context folder:

```bash
vault folder -n new-context-folder -s active
vault folder -n new-context-folder -s archived
```

Use `--content-enabled` when the context folder should have `_obsidian/content` infrastructure.

Implementation script: `_master/system/scripts/folder.py`.

## Obsidian Profile

Back up the root `.obsidian` profile:

```bash
vault backup
```

This writes a timestamped local copy under `_master/system/backup/obsidian-profile/`. The backup folder is git-ignored because plugin bundles are large.

Implementation script: `_master/system/scripts/backup.py`.

Create/update the iPhone-safe `.obsidian-mobile` profile:

```bash
vault mobile-profile
```

This writes `.obsidian-mobile/community-plugins.json`, copies the approved mobile plugin folders/settings, copies the current theme and enabled CSS snippets, syncs key core settings such as `daily-notes.json`, and prunes unapproved mobile plugin/theme/snippet folders by default. On iPhone, Obsidian must have `Settings → Files and links → Override config folder` set to `.obsidian-mobile`.

Implementation script: `_master/system/scripts/mobile_profile.py`.
