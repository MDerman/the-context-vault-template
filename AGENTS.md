---
generated: true
generated_at: 2026-05-29T19:02:59
managed_by: "managed-by: _master/system/bootstrap/generate_agents.py"
---
If editing this agent file, edit `_master/system/bootstrap/AGENTS.template.md`, then rerun `python3 _master/system/bootstrap/generate_agents.py`.

# Agent Instructions

Root workspace is one Obsidian vault with context folders. `CLAUDE.md` is a symlink to this file.

## Always

- Do not read plaintext `.env`, token, key, kubeconfig, or secrets paths unless explicitly asked.
- Use `[[Obsidian links]]`, not Markdown links, inside vault notes.
- Put future agent plans in `.agents/plans/`.
- Put active agent skills in `.agents/skills/`.
- Put dormant skills in `_master/agents/skills-dump/`.
- Ignore incidental `.obsidian/` git churn.
- Do not bulk-move, restructure, delete, or overwrite user content unless explicitly asked.

## First Read

1. Read `_master/system/context/CONTEXT.md` | current generated vault state, active periods, tasks, schedules, first-look files.
2. Read relevant context folder `HOME.md` before routing or storing info.
3. Read relevant `<context-folder>/DECLARATION.md` before changing entity operating rules.
4. Open detail docs only when needed: `_master/01-Context.md`, `_master/system/context/SCRIPTS.md` | normal vault commands and refresh workflows, `_master/system/context/SCRIPT-REFERENCE.md` | full script inventory and one-time script cautions, `_master/system/context/OBSIDIAN-PROFILE.md` | Obsidian profile, plugins, UI settings, templates, Sync Embeds.
5. For public bootstrap/export docs, read `_master/system/bootstrap/README-bootstrap.md` (public README source) and `_master/system/bootstrap/bootstrapdocs.md` (internal bootstrap mechanics).

## Map

- Active context folders: `business`, `personal-brand`, `personal`.
- Archived context folders: `claudeche`, `dev`.
- Configured context folders: `claudeche`, `dev`, `business`, `personal-brand`, `personal`.
- Content-enabled context folders: `business`, `personal-brand`.
- Default task/periodic note capture context folder: `personal`.
- `_master/`: operating layer, bootstrap, scripts, generated agent packets, dashboards, reusable tools, agent skills, media, and Mac/dev tools.
- `_library/`: learning, research dumps, swipe files, source material, random thoughts.
- `_wiki/`: synthesized reusable knowledge.
- `other/`: archive/holding area for old, excess, uncertain, or random dumps. Only used if explicitly asked.

Use each context folder's `HOME.md` for local routing. Use `_master/01-Context.md` for exact folder shapes, content schemas, TaskNotes details, attachments, and Obsidian profile model.

## Routing Cheats

- Tasks: `<context-folder>/_obsidian/tasks/`
- Projects: `<context-folder>/_obsidian/projects/`
- Epics: `<context-folder>/_obsidian/epics/`
- Periodic notes: `<context-folder>/_obsidian/periodic/<daily|weekly|quarterly|yearly>/`
- Entity operating rules: `<context-folder>/DECLARATION.md`
- Content: `<context-folder>/_obsidian/content/`
- Content schedules: `<context-folder>/_obsidian/content-schedules/`
- Note attachments: owning top-level folder's `_obsidian/attachments/`
- Brain Dump import: `_master/system/inbox/BRAIN_DUMP.md`

## Low-Context Lookups

Use `rg` filename-first, then inspect only frontmatter/opening notes:

```bash
sed -n '1,60p' "business/_obsidian/tasks/starter-task.md"
```

Common queries:

```bash
rg -l '^\s*epic:.*Current dev' business/_obsidian/tasks
rg -l '^status: in-progress$' business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks | head -5
for s in in-progress ongoing to-be-resumed up-next backlog; do rg -l "^status: $s$" business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks; done | head -50
rg -l '^status: (idea|cogs-are-turning|draft|planning-scripting|scheduled)$' business/_obsidian/content/items personal-brand/_obsidian/content/items 2>/dev/null | head -50
```

If exact Obsidian Base drag order matters, check `tasknotes_manual_order` or use the Base in Obsidian.

## Scripts

Use `vault --help` first. Main vault-related scripts that complement Obsidian workflows live in `_master/system/scripts/`.
Other random tools and scripts live in `_master/general-tools/`.

Common commands: `vault refresh`, `vault context`, `vault content`, `vault periodic`, `vault sync`, `vault triage`, `vault attachments`, `vault epic`, `vault gcal`, `vault folder`, `vault bootstrap-export`, `vault upgrade`.

Run first-time setup with:

```bash
_master/system/bootstrap/init_vault.sh
```

`vault attachments` writes reports and quarantined import leftovers outside the vault under `~/Downloads/vault-generated/`, then opens that folder in Finder.

Read `_master/system/context/SCRIPTS.md` before refresh/setup commands. Read `_master/system/context/SCRIPT-REFERENCE.md` before secondary or one-time scripts.

## Task Rules

- Create TaskNotes tasks only for executable next actions, reminders, or decisions needing follow-up.
- Route tasks by context: `business`, `personal-brand`, `personal` unless user names another context.
- Link projects and epics when obvious.
- Use native dates: `scheduled` = start/surface/work date; `due` = deadline. Do not add dates unless explicitly asked or clearly needed.
- Use native time fields: `timeEstimate`, `timeEntries`, `pomodoros`. Do not use `duration`.
- Use Google Calendar `Time Blocks` for broad planning blocks. Do not create arbitrary events on personal/business calendars.
- `Scheduled Tasks` and `Due Tasks` mirror TaskNotes `scheduled`/`due`; use `vault gcal sync-tasks` to mirror.
- Agents may read calendars with `vault gcal list --days 7 --calendar all --json`.
- Missed cadence: create one recovery task or recommendation, not repeated guilt tasks.

## Content Rules

- Use `_obsidian/content` for owned content items, ideas, and publication definitions.
- Use `_obsidian/content-schedules` for generated 4-week planning pages.
- Use `DECLARATION/content-cadence.json` for recurring publication cadence, `schedule_format`, and `publication_order`.
- Use `type: content` for content items and `type: publication` for publication definitions.
- Use `_obsidian/tasks` for executable work about content.
- Content storage is enabled for: `business`, `personal-brand`.

## Declarations And Proof

- `DECLARATION.md` stores entity/context operating rules.
- Proof sources should state commitment, data source, manual/automated status, and missing-proof task/warning.
- Until proof automation exists, ask user to confirm missing facts or mark them manual.

## Local Hooks

- Custom plugin / `context_nine_obsidian_plugin`: `~/Code/context_nine_obsidian_plugin/`.
- Obsidian styling/functionality guide: `_master/system/obsidian_notes/editing_obsidian.md`.

## Skills And Agents Settings

If asked to create skills, add them to `_master/agents/skills` (symlinked to `.agents/skills`).
If asked to store but not make active a skill, add it to `_master/agents/skills-dump`.

## Agents Can

- summarize current tasks and periodic notes;
- create or update TaskNotes tasks when asked;
- propose calendar blocks from the Momentum rules;
- create `_obsidian/content` notes when asked or when migrating source drafts;
- promote useful `_library` or old-note material into system docs when asked;
- update `DECLARATION.md` when the user changes operating rules.
