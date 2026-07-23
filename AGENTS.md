# Agent Instructions

Root workspace is one Obsidian vault with context folders. `AGENTS.md` is direct-edit source of truth. `CLAUDE.md` is a symlink to it. Bootstrap/export copies root `AGENTS.md`; agent setup scripts only ensure symlinks.

## Always

- Do not read plaintext `.env`, token, key, kubeconfig, or secrets paths unless explicitly asked.
- Use `[[Obsidian links]]`, not Markdown links, inside vault notes.
- Follow README breadcrumbs before acting: nearest `README.md`, then relevant `README-<topic>.md`, then command/tool docs.
- If a workflow needs SOP or quick start docs, put it in the relevant folder as `README-<topic>.md`.
- Use skills for reusable agent capabilities with trigger rules; use folder READMEs for vault SOPs and tool usage.
- Put future agent plans in `.agents/plans/`.
- Put repo-scoped skills in `.agents/skills/`.
- Put implicit shared skills in `_system/agents/auto-skills/`, explicit-only skills in `_system/agents/manual-skills/`, and `gh skill --dir` installs in `_system/agents/gh-skills/`; organize recursively with `_lower-kebab` group folders, then run `vault skills sync --dry-run` and `--apply`.
- Ignore incidental `.obsidian/` git churn.
- Do not bulk-move, restructure, delete, or overwrite user content unless explicitly asked.
- Code Folder and Computer Topology auto skill is private source of truth for machine access and general `~/Code/` placement; use folder/repo docs before changing code.

## First Read

1. Run `vault inventory` for live periods, contexts, task state, and source-note routing.
2. Use the routing index below, then follow folder READMEs until reaching the relevant SOP/tool/command doc.
3. Read relevant `<context-folder>/<context-folder>.md` before changing entity operating rules.
4. For public bootstrap/export work, read `_system/bootstrap/README.md` and `_system/docs/commands/Bootstrap Export.md`.

## Folder Map

- `_system/`: operating layer for shared Obsidian assets, agents, bootstrap, commands, config, docs, inboxes, migrations, state, sync, and tools. Read `_system/README.md`.
- `_system/agents/`: shared skills and skill storage. Read `_system/agents/README.md`.
- `_system/tools/`: reusable tools outside `vault`. Read `_system/tools/README.md`.
- `_system/bootstrap/`: fresh install, public export, release, and upgrade framework.
- `_system/commands/`: `vault` dispatcher, commands, internals, and tests.
- `_system/docs/`: command, Obsidian, and workflow documentation.
- `_system/config/`: vault, dependency, calendar, Dashboard, skill-instance, topology, and env configuration. Read `_system/config/README.md`.
- `_system/state/`: ignored local reports, backups, and install/export state.
- `_library/`: learning, research dumps, swipe files, source material, thoughts. Read `_library/LIBRARY.md` before organizing it.
- `_wiki/`: synthesized reusable knowledge.
- `other/`: archive/holding area only when explicitly asked.
- Context folders: source-of-truth workspaces with local `<context-folder>.md` routing notes and `_obsidian/` operating folders.

## Core Docs

- `_system/README.md`: vault architecture, folder model, data model, context folder rules.
- `_system/docs/commands/README.md`: `vault` command index and command docs routing.
- `_system/docs/commands/README-reference.md`: full command and bootstrap script inventory.
- `_system/docs/obsidian/README.md`: Obsidian profile/plugins/templates/UI.
- `_system/bootstrap/README.md`: bootstrap/export/upgrade mechanics.
- `_system/config/README.md`: config ownership and skill-config separation.
- `_system/config/env/README.md`: env workflow; placeholders only in tracked files.
- Machine registry, primary/worker sync, connection routing, and code topology: [[_system/agents/auto-skills/_infrastructure/code-folder-and-computer-topology/SKILL|Code Folder and Computer Topology skill]].

## Agent Routing Index

- Current state: `vault inventory`, source context notes, `Dashboard.md`.
- Tasks/projects/epics: `_system/docs/commands/Tasks And Projects.md`, then `<context-folder>/_obsidian/<tasks|projects|epics>/`.
- Calendar/time blocks: `_system/docs/commands/Google Calendar.md`, then `vault gcal`.
- Content: `_system/README.md#Content`, `_system/docs/commands/Content Schedules.md`, then content-enabled `<context-folder>/_obsidian/content/`.
- Scripts and `vault` commands: `_system/docs/commands/README.md`; open only the needed script doc.
- General tools and invoices: `_system/tools/README.md`, then relevant `README-<topic>.md` or tool README.
- Skills: `_system/agents/README.md`, `_system/agents/README-skills.md`, `_system/docs/commands/Agent Skills Sync.md`.
- Dependency repos: `_system/docs/commands/Dependency Repos.md`, then `vault deps`.
- Bootstrap/export/upgrade: `_system/bootstrap/README.md`, `_system/docs/commands/<Bootstrap Export|Public Vault Upgrade>.md`.
- Obsidian profile/UI/theme: `_system/docs/obsidian/README.md`, then `_system/docs/obsidian/editing_obsidian.md` if editing UI/CSS/plugin behavior.
- Attachments: `_system/docs/commands/Attachments.md`.
- Private Git and pointer-only media: `_system/docs/commands/README-git.md`.
- Env/auth: `_system/config/env/README.md`.
- Library changes: `_library/LIBRARY.md`.

## Core Paths

- Tasks: `<context-folder>/_obsidian/tasks/`
- Projects: `<context-folder>/_obsidian/projects/`
- Epics: `<context-folder>/_obsidian/epics/`
- Periodic notes: `<context-folder>/_obsidian/periodic/<daily|weekly|monthly|quarterly|yearly>/`
- Entity operating notes: `<context-folder>/<context-folder>.md`
- Content: `<context-folder>/_obsidian/content/`
- Content schedules: `<context-folder>/_obsidian/content-schedules/`
- Attachments: owning top-level folder's `_obsidian/attachments/`
- Brain Dump import: `_system/inbox/BRAIN_DUMP.md`

## Operating SOPs

- Create TaskNotes tasks only for executable next actions, reminders, or decisions needing follow-up.
- Route unspecific capture to current default context from `vault inventory`.
- Use `scheduled` for work/surface date and `due` for deadline.
- Use native time fields: `timeEstimate`, `timeEntries`, `pomodoros`; do not use `duration`.
- Use `vault gcal create-event` for concrete appointments/travel/meetings/reservations; use `create-block` only for explicit time blocking.
- Use `_obsidian/content` for owned content items/ideas/publication definitions; use `_obsidian/tasks` for executable work about content.
- Keep proof-source notes explicit: commitment, data source, manual/automated status, missing-proof task/warning.
- External dependency repos live under `~/Code/open_source/<repo-name>` and are tracked in `_system/config/deps.json`.
- `_system/agents/skills` is generated symlink-only catalog. Never install content there; `vault skills sync --apply` projects auto, manual, and GitHub-managed sources into it.
