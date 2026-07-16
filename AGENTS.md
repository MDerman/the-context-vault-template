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
- Put implicit shared skills in `_master/agents/auto-skills/`, explicit-only skills in `_master/agents/manual-skills/`, and `gh skill --dir` installs in `_master/agents/gh-skills/`; organize recursively with `_lower-kebab` group folders, then run `vault skills sync --dry-run` and `--apply`.
- Ignore incidental `.obsidian/` git churn.
- Do not bulk-move, restructure, delete, or overwrite user content unless explicitly asked.
- Computers and Code Topology auto skill is private source of truth for machine access and general `~/Code/` placement; use folder/repo docs before changing code.

## First Read

1. Read `_master/system/context/CONTEXT.md` for current generated state.
2. Run `vault inventory` for low-context routing.
3. Use the routing index below, then follow folder READMEs until reaching the relevant SOP/tool/command doc.
4. Read relevant `<context-folder>/<context-folder>.md` before changing entity operating rules.
5. For public bootstrap/export work, read `_master/system/README.md` and `_master/system/context/script-docs/Bootstrap Export.md`.

## Folder Map

- `_master/`: operating layer, scripts, bootstrap, generated context, agent skills, reusable tools. Read `_master/README.md`.
- `_master/agents/`: shared skills and skill storage. Read `_master/agents/README.md`.
- `_master/general-tools/`: reusable tools outside `vault`. Read `_master/general-tools/README.md`.
- `_master/system/`: bootstrap, public export, `vault` scripts, generated context, system docs.
- `_master/env/`: env tooling docs and tracked placeholders; real values stay ignored.
- `_library/`: learning, research dumps, swipe files, source material, thoughts. Read `_library/LIBRARY.md` before organizing it.
- `_wiki/`: synthesized reusable knowledge.
- `other/`: archive/holding area only when explicitly asked.
- Context folders: source-of-truth workspaces with local `<context-folder>.md` routing notes and `_obsidian/` operating folders.

## Core Docs

- `_master/01-Context.md`: vault architecture, folder model, data model, context folder rules.
- `_master/system/context/README-scripts.md`: `vault` command index and command docs routing.
- `_master/system/context/README-script-reference.md`: full script inventory and one-time script cautions.
- `_master/system/context/README-obsidian-profile.md`: Obsidian profile/plugins/templates/UI.
- `_master/system/README.md`: bootstrap/export/system mechanics.
- `_master/env/README.md`: env workflow; placeholders only in tracked files.

## Agent Routing Index

- Current state: `vault inventory`, `_master/system/context/CONTEXT.md`, `_master/Dashboard.md`.
- Tasks/projects/epics: `_master/system/context/script-docs/Tasks And Projects.md`, then `<context-folder>/_obsidian/<tasks|projects|epics>/`.
- Calendar/time blocks: `_master/system/context/script-docs/Google Calendar.md`, then `vault gcal`.
- Content: `_master/01-Context.md#Content`, `_master/system/context/script-docs/Content Schedules.md`, then content-enabled `<context-folder>/_obsidian/content/`.
- Scripts and `vault` commands: `_master/system/context/README-scripts.md`; open only the needed script doc.
- General tools and invoices: `_master/general-tools/README.md`, then relevant `README-<topic>.md` or tool README.
- Skills: `_master/agents/README.md`, `_master/agents/README-skills.md`, `_master/system/context/script-docs/Agent Skills Sync.md`.
- Dependency repos: `_master/system/context/script-docs/Dependency Repos.md`, then `vault deps`.
- Bootstrap/export/upgrade: `_master/system/README.md`, `_master/system/context/script-docs/<Bootstrap Export|Public Vault Upgrade>.md`.
- Obsidian profile/UI/theme: `_master/system/context/README-obsidian-profile.md`, then `_master/system/obsidian_notes/editing_obsidian.md` if editing UI/CSS/plugin behavior.
- Attachments: `_master/system/context/script-docs/Attachments.md`.
- Env/auth: `_master/env/README.md`.
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
- Brain Dump import: `_master/system/inbox/BRAIN_DUMP.md`

## Operating SOPs

- Create TaskNotes tasks only for executable next actions, reminders, or decisions needing follow-up.
- Route unspecific capture to current default context from `CONTEXT.md`/`vault inventory`.
- Use `scheduled` for work/surface date and `due` for deadline.
- Use native time fields: `timeEstimate`, `timeEntries`, `pomodoros`; do not use `duration`.
- Use `vault gcal create-event` for concrete appointments/travel/meetings/reservations; use `create-block` only for explicit time blocking.
- Use `_obsidian/content` for owned content items/ideas/publication definitions; use `_obsidian/tasks` for executable work about content.
- Keep proof-source notes explicit: commitment, data source, manual/automated status, missing-proof task/warning.
- External dependency repos live under `~/Code/open_source/<repo-name>` and are tracked in `_master/system/config/deps.json`.
- `_master/agents/skills` is generated symlink-only catalog. Never install content there; `vault skills sync --apply` projects auto, manual, and GitHub-managed sources into it.
