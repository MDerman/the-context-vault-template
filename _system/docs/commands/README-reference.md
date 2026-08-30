---
type: agent-reference
status: enabled
---
# Script Reference

This is the fuller script reference. Use `_system/docs/commands/README.md` for normal workflows.

## Main Scripts

- `vault.py`: terminal dispatcher installed as `vault` in `~/.local/bin`; forwards subcommands to the scripts below.
- `remote_access.py`: local-Mac `vault access` entrypoint for worktree safety, shared leases, and optional receipt/upload diagnostics. The reviewed deployable host/client/controller lives in the existing `infra-onboard-machine` skill. Remote Linux launchers intercept `vault access` outside the mount.
- `refresh.py`: sole full-refresh entrypoint; runs required Git preflight before generated changes, optional Brain Dump ingestion, best-effort Google Calendar mirror, content schedules, source/vault periodic notes, `Dashboard.md`, and best-effort Git maintenance.
- `refresh_schedule.py`: registers, unregisters, reports, and runs the macOS LaunchAgent daily refresh wrapper.
- `mac_startup.py`: validates private per-machine startup opt-ins and application bundle identifiers, installs or removes the copied macOS `RunAtLoad` runtime, archives configured legacy LaunchAgents, reports state, and runs enabled actions. Explicit `--provision-disabled` supports reviewed onboarding without fleet enablement. Use `vault mac-startup`.
- `dashboard.py`: private renderer used by `refresh.py`; it is not a `vault` command.
- `content.py`: generates fixed 4-week content schedule notes from enabled `_obsidian/content/content-cadence.json` files and maintains the `Current content schedule:` line in each enabled context folder note. Supports `schedule_format`, `publication_order`, and `--force` to regenerate existing managed schedule notes.
- `periodic.py`: creates current context source periodic notes, non-destructively carries daily task-section content forward, and generates vault Sync Embed rollups under `_system/_obsidian/periodic/`.
- `brain_dump.py`: imports the Brain Dump Apple Note into its single vault import file, copies attachments, and can clear the source note.
- `brain_dump_triage.py`: creates optional Brain Dump batch backups/proposals, maintains triage Base, clears import file, and applies approved proposals.
- `epic.py`: creates, renames, deletes, lists, and syncs context folder epics; keeps task links, per-epic TaskNotes Kanban Bases, and managed vault task kanban epic views in sync.
- `gcal.py`: uses GWS credentials for Google Calendar API calls, reads vault calendar behavior from `_system/local/calendar.json`, creates required vault calendars, lists calendar events for agents, creates specific default-calendar events, creates `Time Blocks`, and two-way mirrors TaskNotes `scheduled`/`due` dates to `Scheduled Tasks`/`Due Tasks`.
- `folder.py`: creates/registers a context folder from the scaffold template.
- `business_toolkit.py`: installs, synchronizes, or safely unconfigures the marker-owned business folder/template pack for any registered context.
- `attachments.py`: dry-runs, applies, and verifies attachment cleanup so note attachments live under each owning top-level root folder's `_obsidian/attachments` directory. Reports and quarantined import leftovers are written outside the vault under `~/Downloads/vault-generated/`.
- `backup.py`: backs up root `.obsidian` under `_system/local/state/backups/obsidian-profile/`.
- `bootstrap_export.py`: exports the public bootstrap vault from current vault state using `_system/bootstrap/bootstrap-export.json`.
- `release.py`: publishes SemVer public vault releases by bumping release metadata, locking dependencies, exporting, committing, tagging, pushing, and creating the GitHub Release.
- `git_media.py`: generates and verifies pointer-only media manifests, checks local LFS objects, and installs no-upload pre-push hook. Use `vault git-media`.
- `git_maintenance.py`: keeps normal Git history shallow and compacts local Git objects. Use `vault git-maintenance`.
- `git_preflight.py`: fetches and fast-forwards clean `master` before refresh changes files. Use `vault git-preflight`.
- `worker_bootstrap.py`: keeps iCloud worker Macs Gitless, recoverably retires only the expected legacy external Git directory, and writes machine-local identity plus refresh prohibition; reviewed onboarding can target one disabled Mac worker through `--provision-disabled`. Use `vault worker-sync` only for Mac workers.
- `_system/agents/_package/src/sync_agents.py`: canonical default-apply fleet orchestrator for portable skills, Codex/Claude settings, and rendered instructions. Use `ctx9-agents sync`; add component selectors or `--dry-run` when needed.
- `_system/agents/_package/src/sync_skills.py`: validates grouped auto/manual/GH skill sources, materializes selected repo-owned projections, enforces invocation policy, repairs dependency moves, and rebuilds the Vault-local flat catalog.
- `_system/agents/_package/src/skill_snapshots.py`: builds and installs verified point-in-time global skill copies while preserving unmanaged skills.
- `_system/agents/_package/src/global_agent_configuration.py`: shared Vault alias, machine-footer rendering, and atomic home-file reconciliation used by regular sync, bootstrap, and fleet deployment.
- `_system/agents/skills/auto/_infrastructure/infra-sync-code-workspaces/scripts/sync_code_workspaces.py`: reconciles registered Code repositories and invokes the same primary-owned Codex/Claude configuration sync used during onboarding.
- `_system/agents/skills/auto/_infrastructure/infra-sync-code-workspaces/scripts/sync_agent_configuration.py`: previews, applies, or verifies personal Codex/Claude configuration without changing repositories.
- `snippets.py`: checks and materializes canonical text blocks inside configured files across registered repositories. Use `vault snippets`.

## Bootstrap Scripts

- `_system/bootstrap/init_vault.sh`: first-run fresh/exported vault setup entrypoint.
- `_system/bootstrap/offer_machine_setup.py`: testable optional post-init prompt that invokes `vault machine setup` only on explicit yes and always skips under non-interactive setup.
- `_system/bootstrap/bootstrap_vault.py`: scaffolds/reconciles context folders, templates, Bases, starter notes, and generated setup docs.
- `_system/deps/packages.yaml`: approved cross-platform public Vault dependencies.
- `_system/deps/install.py`: installs and verifies the public dependency manifest; bootstrap's wrapper only invokes it.
- `_system/bootstrap/install_vault_command.py`: installs the `vault` dispatcher symlink.

## Secondary Scripts

- `generate_epic_kanban_views.py`: low-level helper that generates one TaskNotes Kanban Base file per epic. Prefer `vault epic sync` for normal use.
- `script_utils.py`: shared helper code for vault scripts. It is not meant to be run directly.
