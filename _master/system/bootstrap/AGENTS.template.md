---
generated: true
generated_at: {{generated_at}}
managed_by: "{{managed_marker}}"
---
If editing this agent file, edit `_master/system/bootstrap/AGENTS.template.md`, then rerun `python3 _master/system/bootstrap/generate_agents.py`.

# Agent Instructions

Root workspace is one Obsidian vault with context folders. `CLAUDE.md` is a symlink to this file.

## Always

- Do not read plaintext `.env`, token, key, kubeconfig, or secrets paths unless explicitly asked.
- Use `[[Obsidian links]]`, not Markdown links, inside vault notes.
- Put future agent plans in `.agents/plans/`.
- Put repo-scoped skills in `.agents/skills/`.
- Put active shared agent skills in `_master/agents/skills/`.
- Put manual-only skill pack sources in `_master/agents/skill-packs/`; expose them through `_master/agents/skills/manual/` with implicit invocation disabled.
- Put dormant non-discoverable skills in `_master/agents/skills-dump/`.
- Ignore incidental `.obsidian/` git churn.
- Do not bulk-move, restructure, delete, or overwrite user content unless explicitly asked.

## First Read

1. Read `_master/system/context/CONTEXT.md` | current generated vault state, active periods, tasks, schedules, first-look files.
2. Use `_master/README.md#Agent Routing Index` to choose the next doc/path for the task type.
3. Read relevant context folder note, for example `business/impression.md`, before routing or storing info.
4. Read relevant `<context-folder>/<context-folder>.md` before changing entity operating rules.
5. For public bootstrap/export work, read `_master/system/bootstrap/bootstrap-public-README.md` and `_master/system/README-vault-system-and-bootstrapped.md`.

## Map

- Active context folders: {{active_context_folders}}.
- Archived context folders: {{archived_context_folders}}.
- Configured context folders: {{configured_context_folders}}.
- Content-enabled context folders: {{content_enabled_context_folders}}.
- Default task/periodic note capture context folder: `{{default_context_folder}}`.
- `_master/`: operating layer. Read `_master/README.md` for its folder map, docs, tooling SOPs, and skill SOPs.
- `_library/`: learning, research dumps, swipe files, source material, random thoughts.
- `_wiki/`: synthesized reusable knowledge.
- `other/`: archive/holding area for old, excess, uncertain, or random dumps. Only used if explicitly asked.

Use each context folder's inside-folder note for local routing. Use `_master/01-Context.md` for exact folder shapes, content schemas, TaskNotes details, attachments, and Obsidian profile model.
Before renaming, organizing, adding, or removing files under `_library/`, read `_library/LIBRARY.md`.

## Agent Routing

For detailed routing and common `rg` commands, read `_master/README.md#Agent Routing Index`.

- Current state and work routing: `vault inventory`, `_master/system/context/CONTEXT.md`, `_master/Dashboard.md`.
- Tasks/projects/epics: `_master/system/context/script-docs/Tasks And Projects.md`, then `<context-folder>/_obsidian/<tasks|projects|epics>/`.
- Content: `_master/01-Context.md#Content`, `_master/system/context/script-docs/Content Schedules.md`, then content-enabled `<context-folder>/_obsidian/content/`.
- Calendar: `_master/system/context/script-docs/Google Calendar.md`, then `vault gcal`.
- Scripts/tools: `_master/README.md`, `_master/system/context/SCRIPTS.md`, `_master/system/context/SCRIPT-REFERENCE.md`, `_master/general-tools/`, `_master/system/bootstrap/Brewfile`.
- Dependency repos: `_master/system/context/script-docs/Dependency Repos.md`, then `vault deps`.
- Skills: `_master/README.md#Skill SOP`, `_master/system/context/script-docs/Agent Skills Sync.md`.
- Bootstrap/export/upgrade: `_master/system/README-vault-system-and-bootstrapped.md`, `_master/system/context/script-docs/Bootstrap Export.md`, `_master/system/context/script-docs/Public Vault Upgrade.md`.
- Obsidian profile/UI/theme: `_master/system/context/OBSIDIAN-PROFILE.md`, `_master/system/obsidian_notes/editing_obsidian.md`.
- Attachments: `_master/system/context/script-docs/Attachments.md`; attachments live under owning root's `_obsidian/attachments/`.
- Env/auth: `_master/env/README-env-tooling.md`; keep real values in ignored local env files only.

## Core Paths

- Tasks: `<context-folder>/_obsidian/tasks/`
- Projects: `<context-folder>/_obsidian/projects/`
- Epics: `<context-folder>/_obsidian/epics/`
- Periodic notes: `<context-folder>/_obsidian/periodic/<daily|weekly|monthly|quarterly|yearly>/`
- Entity operating rules: `<context-folder>/<context-folder>.md`
- Content: `<context-folder>/_obsidian/content/`
- Content schedules: `<context-folder>/_obsidian/content-schedules/`
- Note attachments: owning top-level folder's `_obsidian/attachments/`
- Brain Dump import: `_master/system/inbox/BRAIN_DUMP.md`

Low-context lookup: run `vault inventory` first, then use `rg --files` or the common searches in `_master/README.md#Low-Context Searches`. Inspect only frontmatter/opening lines unless more is needed. If exact Obsidian Base order matters, check `tasknotes_manual_order` or use Obsidian.

## Vault Commands

Use `vault --help` first. Main vault-related scripts that complement Obsidian workflows live in `_master/system/scripts/`.
Other random tools and scripts live in `_master/general-tools/`; document their dependencies in `_master/system/bootstrap/Brewfile` when possible.

Run first-time setup with:

```bash
_master/system/bootstrap/init_vault.sh
```

`vault attachments` writes reports and quarantined import leftovers outside the vault under `~/Downloads/vault-generated/`, then opens that folder in Finder.

Read `_master/system/context/SCRIPTS.md` before refresh/setup commands. Read `_master/system/context/SCRIPT-REFERENCE.md` before secondary or one-time scripts.

## Operating Rules

- Create TaskNotes tasks only for executable next actions, reminders, or decisions needing follow-up.
- Route tasks by context: {{active_context_folders}} unless user names another context.
- Link projects and epics when obvious.
- Use native TaskNotes dates: `scheduled` = work/surface date; `due` = deadline. Do not add dates unless explicitly asked or clearly needed.
- Use native time fields: `timeEstimate`, `timeEntries`, `pomodoros`. Do not use `duration`.
- Use `vault gcal create-event` for appointments/travel/meetings/reservations; use `vault gcal create-block` only for explicit time blocking.
- Agents may read calendars with `vault gcal list --days 7 --calendar all --json`; `Scheduled Tasks` and `Due Tasks` mirror TaskNotes dates.
- Missed cadence: create one recovery task or recommendation, not repeated guilt tasks.
- Use `_obsidian/content` for owned content items, ideas, and publication definitions; use `_obsidian/tasks` for executable work about content.
- {{content_enabled_note}}
- `<context-folder>/<context-folder>.md` stores entity/context operating rules.
- Proof sources should state commitment, data source, manual/automated status, and missing-proof task/warning.
- Until proof automation exists, ask user to confirm missing facts or mark them manual.
- Custom plugin / `context_nine_obsidian_plugin`: `~/Code/context_nine_obsidian_plugin/`.
- External dependency repos live under `~/Code/open_source/<repo-name>` and are tracked in `_master/system/config/deps.json`; use `vault deps` to clone, pull, and rebuild projections.
- If asked to create shared active skills, use `_master/agents/skills`; manual-only discoverable skills use `_master/agents/skill-packs`; non-discoverable stored skills use `_master/agents/skills-dump`.
