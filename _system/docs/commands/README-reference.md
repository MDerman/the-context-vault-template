---
type: agent-reference
status: enabled
---
# Script Reference

This is the fuller script reference. Use `_system/docs/commands/README.md` for normal workflows.

## Main Scripts

- `vault.py`: terminal dispatcher installed as `vault` in `~/.local/bin`; forwards subcommands to the scripts below.
- `refresh.py`: sole full-refresh entrypoint; runs optional Brain Dump ingestion, best-effort Google Calendar mirror, content schedules, source/vault periodic notes, `Dashboard.md`, and best-effort Git maintenance.
- `refresh_schedule.py`: registers, unregisters, reports, and runs the macOS LaunchAgent daily refresh wrapper.
- `dashboard.py`: private renderer used by `refresh.py`; it is not a `vault` command.
- `content.py`: generates fixed 4-week content schedule notes from enabled `_obsidian/content/content-cadence.json` files and maintains the `Current content schedule:` line in each enabled context folder note. Supports `schedule_format`, `publication_order`, and `--force` to regenerate existing managed schedule notes.
- `periodic.py`: creates current context source periodic notes, carries daily checklists forward, and generates vault Sync Embed rollups under `_system/_obsidian/periodic/`.
- `brain_dump.py`: imports the Brain Dump Apple Note into its single vault import file, copies attachments, and can clear the source note.
- `brain_dump_triage.py`: creates optional Brain Dump batch backups/proposals, maintains triage Base, clears import file, and applies approved proposals.
- `epic.py`: creates, renames, deletes, lists, and syncs context folder epics; keeps task links, per-epic TaskNotes Kanban Bases, and managed vault task kanban epic views in sync.
- `gcal.py`: uses GWS credentials for Google Calendar API calls, reads vault calendar behavior from `_system/config/calendar.json`, creates required vault calendars, lists calendar events for agents, creates specific default-calendar events, creates `Time Blocks`, and two-way mirrors TaskNotes `scheduled`/`due` dates to `Scheduled Tasks`/`Due Tasks`.
- `folder.py`: creates/registers a context folder from the scaffold template.
- `attachments.py`: dry-runs, applies, and verifies attachment cleanup so note attachments live under each owning top-level root folder's `_obsidian/attachments` directory. Reports and quarantined import leftovers are written outside the vault under `~/Downloads/vault-generated/`.
- `backup.py`: backs up root `.obsidian` under `_system/state/backups/obsidian-profile/`.
- `bootstrap_export.py`: exports the public bootstrap vault from current vault state using `_system/bootstrap/bootstrap-export.json`.
- `release.py`: publishes SemVer public vault releases by bumping release metadata, locking dependencies, exporting, committing, tagging, pushing, and creating the GitHub Release.
- `_system/agents/sync_skills.py`: validates grouped auto/manual/GH skill sources, enforces invocation policy, repairs dependency moves, and rebuilds flat catalog plus per-skill global links. Use `vault skills sync`.

## Bootstrap Scripts

- `_system/bootstrap/init_vault.sh`: first-run fresh/exported vault setup entrypoint.
- `_system/bootstrap/bootstrap_vault.py`: scaffolds/reconciles context folders, templates, Bases, starter notes, and generated setup docs.
- `_system/bootstrap/agents/ensure-agent-file-symlinks.py`: ensures `CLAUDE.md`, `.agents/skills`, and `.claude/skills` symlinks/dirs without rewriting `AGENTS.md`.
- `_system/bootstrap/Brewfile`: Homebrew formulas for bootstrap-managed CLI dependencies.
- `_system/bootstrap/install_dependencies.sh`: installs/checks local CLI dependencies from the bootstrap Brewfile.
- `_system/bootstrap/install_agent_canvas.py`: checks, builds, and repairs editable Agent Canvas CLI/package links through dependency setup hooks.
- `_system/bootstrap/install_vault_command.py`: installs the `vault` dispatcher symlink.

## Secondary Scripts

- `generate_epic_kanban_views.py`: low-level helper that generates one TaskNotes Kanban Base file per epic. Prefer `vault epic sync` for normal use.
- `script_utils.py`: shared helper code for vault scripts. It is not meant to be run directly.
