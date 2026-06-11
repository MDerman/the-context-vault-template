---
type: agent-reference
status: enabled
---
# SCRIPT-REFERENCE

This is the fuller script reference. Use `_master/system/context/SCRIPTS.md` for normal workflows.

## Main Scripts

- `vault.py`: terminal dispatcher installed as `vault` in `~/.local/bin`; forwards subcommands to the scripts below.
- `refresh.py`: runs the vault refresh pipeline; by default it ingests the Brain Dump Apple Note, runs the Google Calendar task mirror, regenerates agent context, updates `_master/Dashboard.md`, and removes stale generated non-monthly agent periodic rollups unless `--keep-agent-periodic-history` is passed.
- `refresh_schedule.py`: registers, unregisters, reports, and runs the macOS LaunchAgent daily refresh wrapper.
- `context.py`: generates compact agent-readable state, `_master/Dashboard.md`, current content schedules, realized system notes, and current periodic rollups.
- `content.py`: generates fixed 4-week content schedule notes from enabled `_obsidian/content/content-cadence.json` files and maintains the `Current content schedule:` line in each enabled context folder note. Supports `schedule_format`, `publication_order`, and `--force` to regenerate existing managed schedule notes.
- `periodic.py`: generates current daily, weekly, monthly, quarterly, and yearly flat agent rollups under `_master/system/context/`; historic monthly rollups are preserved for dashboard carry-forward reminders.
- `brain_dump.py`: imports the Brain Dump Apple Note into its single vault import file, copies attachments, and can clear the source note.
- `_master/agents/skills/brain-dump-organizer/scripts/triage.py`: creates Brain Dump organizer backups/proposals, maintains the triage Base, clears the import file, and applies approved proposals.
- `epic.py`: creates, renames, deletes, lists, and syncs context folder epics; keeps task links, per-epic TaskNotes Kanban Bases, and managed master task kanban epic views in sync.
- `gcal.py`: authorizes Google Calendar, creates required vault calendars, lists calendar events for agents, creates specific default-calendar events, creates `Time Blocks`, and two-way mirrors TaskNotes `scheduled`/`due` dates to `Scheduled Tasks`/`Due Tasks`.
- `folder.py`: creates/registers a context folder from the scaffold template.
- `attachments.py`: dry-runs, applies, and verifies attachment cleanup so note attachments live under each owning top-level root folder's `_obsidian/attachments` directory. Reports and quarantined import leftovers are written outside the vault under `~/Downloads/vault-generated/`.
- `backup.py`: backs up root `.obsidian` under `_master/system/backup/`.
- `bootstrap_export.py`: exports the public bootstrap vault from current vault state using `_master/system/bootstrap/bootstrap-export.json`.

## Bootstrap Scripts

- `_master/system/bootstrap/init_vault.sh`: first-run fresh/exported vault setup entrypoint.
- `_master/system/bootstrap/bootstrap_vault.py`: scaffolds/reconciles context folders, templates, Bases, starter notes, and generated setup docs.
- `_master/system/bootstrap/generate_agents.py`: renders root `AGENTS.md` from `AGENTS.template.md` and discovered context folders with folder-note frontmatter.
- `_master/system/bootstrap/install_dependencies.sh`: installs/checks local CLI dependencies.
- `_master/system/bootstrap/install_vault_command.py`: installs the `vault` dispatcher symlink.
- `_master/system/bootstrap/sync-agent-skills.sh`: links local coding-agent skill folders to `_master/agents/skills`.

## Secondary Scripts

- `delete_master_periodic_notes_for_now.py`: deletes current generated agent periodic notes and can optionally clean selected context folder source notes. Use carefully.
- `generate_epic_kanban_views.py`: low-level helper that generates one TaskNotes Kanban Base file per epic. Prefer `vault epic sync` for normal use.
- `script_utils.py`: shared helper code for vault scripts. It is not meant to be run directly.

## One-Time Scripts

Do not run one-time scripts unless the user explicitly asks for that exact migration or cleanup.

- `one_time_flatten_uct_courses.py`: flattens UCT course pages and normalizes Brainfood learning notes.
- `one_time_migrate_matt_content_to_content_system.py`: dry-run migration planner for old Matt blog/YouTube notes into `_obsidian/content`.
- `one_time_notion_import_cleanup.py`: cleanup for imported Notion exports and attachment routing.

When using one-time scripts, dry-run first whenever the script supports it, inspect the output, and avoid deleting original source material unless the user explicitly confirms deletion.
One-time import reports should be written outside the vault under `~/Downloads/vault-generated/import-reports/`.
