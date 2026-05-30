---
generated: true
generated_at: 2026-05-30T20:40:35
managed_by: "managed-by: _master/system/bootstrap/bootstrap_vault.py"
---
# Personalized Quickstart

Open this whole folder as the root Obsidian vault. Context folders are content workspaces inside the root vault, not standalone Obsidian vaults.

## Mental Model

- Root vault: master control panel across all context folders.
- Context folders: source-of-truth workspaces.
- `_master`: operating manual, generated dashboards, setup scripts, shared templates, agent context, agent skills, reusable scripts, media, and Mac/dev tools.
- `_library`: learning material, research, swipe files, downloaded examples, lead magnets, and source material.
- `_wiki`: synthesized knowledge built by LLMs using `_wiki/AGENTS.md` and `_wiki/karpathy-initial-proompt.md`.
- `other`: archive/dump zone for excess context folders and miscellaneous files.

## Context Folders

- `claudeche`
- `ctx9`
- `dev`
- `business`
- `personal-brand`
- `personal`

Default capture context folder:

- `personal`

Default active context folders:

- `ctx9`
- `business`
- `personal-brand`
- `personal`

Each context folder has an inside-folder note named after the folder, for example `business/business.md`. Its `status` property controls the default agent periodic rollups:

- `status: active`: included when you run the periodic generator with no context folder args.
- `status: archived`: kept available but excluded from default rollups.
- blank or missing status: not active.

Its `content_enabled` property controls whether bootstrap scaffolds content infrastructure:

- `content_enabled: true`: create content folders, content schedule folders, publication notes, cadence config, and content Bases.
- `content_enabled: false`: no content scaffold by default.

Its `default_capture` property marks the context folder that receives unspecific tasks and periodic capture.

Content-enabled context folders:

- `business`
- `personal-brand`

The context folder note can keep a short body, but the frontmatter is the control panel:

```yaml
---
status: active
content_enabled: false
default_capture: true
---
```

Context folder operating folders start with `_` so normal folders can sit directly under each context folder.

```text
<context-folder>/
  <context-folder>.md
  _obsidian/
    attachments/
    bases/
    content/
    excalidraw/
    epics/
    periodic/
      daily/
      weekly/
      quarterly/
      yearly/
    projects/
    tasks/
    templates/
      periodic/
  <real context-specific folders, such as docs or projects/>
```

Content-enabled context folders also get:

```text
<context-folder>/_obsidian/content/content-cadence.json
<context-folder>/_obsidian/content-schedules/
<context-folder>/_obsidian/content/
  publications/
  items/
  ideas/
  archive/
```

`_obsidian/content/content-cadence.json` controls recurring publication cadence, `schedule_format`, and `publication_order`. Normal refresh is create-only for content schedules and maintains the `Current content schedule:` line in the context folder note; run `vault content --force` only when intentionally regenerating an existing managed schedule note.

The context folder note is the entity's durable operating source for Identity and Momentum. For personal-brand entities, Social Selling lives as a third-level section inside Momentum. Each context folder owns its local periodic templates under `_obsidian/templates/periodic`. `_master/_obsidian/templates/shared` is for root-level shared non-periodic templates, entity-note templates, content templates, and the default TaskNotes template.

## Agent Files

- `AGENTS.md`: generated instructions for Codex, Claude, and other coding agents. Edit `_master/system/bootstrap/AGENTS.template.md`, then rerun `python3 _master/system/bootstrap/generate_agents.py`.
- `CLAUDE.md`: symlink to `AGENTS.md`.
- `.agents/skills`: agent skills folder.
- `.claude/skills`: symlink to `.agents/skills`.
- `_master/system/context/CONTEXT.md` and `_master/system/context/context.json`: generated current state for agents.
- `_master/system/context/*.md`: generated readable files for agents plus durable agent operating notes.

Context folders do not carry agent symlinks or their own agent workspaces. Open the root vault when working with agents.

## Root-Only Workflow

Use the root vault as your daily control panel:

1. Create tasks with TaskNotes from the root vault.
2. Choose a context to route the task into the right context folder.
3. Use daily, weekly, quarterly, and yearly periodic notes. Monthly periodic notes are intentionally not used.
4. Open the current flat rollup in `_master/system/context/` for readable rollups across active context folders.
5. Open `_master/_obsidian/bases` and `_master/_obsidian/bases` for dashboards and task views.

Task routing:

```text
No context or default context -> personal/_obsidian/tasks
@business              -> business/_obsidian/tasks
@dev                     -> dev/_obsidian/tasks
```

Periodic notes:

```text
Context folder source notes: <context-folder>/_obsidian/periodic/<daily|weekly|quarterly|yearly>/
Agent rollups:       _master/system/context/<period-id>.md
```

The generator creates missing context folder periodic notes from each context folder's own `_obsidian/templates/periodic/<period>-template.md` file. Each active context folder can keep lean local prompts for its own operating rhythm.

Agent rollups inline each context folder source note so agents can read them without Obsidian Sync Embeds:

````md
_Source: `business/_obsidian/periodic/quarterly/2026-Q2.md`_
````

Context folder periodic notes remain the editable source of truth. Sync Embeds notes live at `_master/system/obsidian_notes/beta_plugins_docs/README-sync-embeds.md`.

Agent periodic generator:

```bash
vault periodic
vault periodic --all
vault periodic --context-folders dev,claudeche
```

`context.py` calls this generator and the content schedule generator for the default refresh path, so one context refresh updates context, current 4-week content schedules, realized system notes, and current agent periodic rollups.

No args means active context folders from context folder notes. `--all` means all configured context folders. `--context-folders` means only that one-off context folder list.

Periodic cleanup:

```bash
python3 _master/system/scripts/delete_master_periodic_notes_for_now.py
python3 _master/system/scripts/delete_master_periodic_notes_for_now.py --context-folders dev,claudeche
```

No args deletes the current generated master rollups under `_master/system/context`. Use `--context-folders` or `--all` when you also want to clean current context folder source notes.

Add a context folder:

```bash
vault folder -n new-context-folder -s active
vault folder -n new-context-folder -s archived
```

Root Obsidian settings live in the current root `.obsidian` folder. Bootstrap does not copy or patch profile settings.

## Where Things Go

- Active context folder operating material: the matching context folder.
- Tasks: `<context-folder>/_obsidian/tasks`.
- Projects: `<context-folder>/_obsidian/projects`.
- Epics: `<context-folder>/_obsidian/epics`.
- Entity operating note: `<context-folder>/<context-folder>.md`.
- Content assets for content-enabled entities: `<context-folder>/_obsidian/content`.
- Content schedules for content-enabled entities: `<context-folder>/_obsidian/content-schedules`.
- Periodic notes: `<context-folder>/_obsidian/periodic`.
- Learning, research, downloaded templates, lead magnets: `_library`.
- Durable synthesized knowledge: `_wiki`.
- Reusable assets/scripts/media: `_master`.
- Old or uncertain material: `other`.

Context folders are not learning folders. If learning from `_library` or `_wiki` belongs in a context folder, rewrite it as an operating artifact first: SOP, keep-in-mind note, training note, checklist, playbook, decision record, policy, or active reference.

## TaskNotes Shorthand

TaskNotes stores each task as one Markdown note with YAML frontmatter. Its natural language parser can extract structure from the task title/body.

- `#tag`: adds an Obsidian tag.
- `@context`: sets context. In this setup, context also controls which context folder `_obsidian/tasks` folder is used.
- `+project`: links a simple project.
- `+[[Project Name]]`: links a project note, usually from `<context-folder>/_obsidian/projects`.
- `tomorrow`, `next Friday`, `January 15 at 3pm`: parsed as dates/times.
- `high`, `normal`, `low`: parsed as priority words.
- `!`: configurable priority trigger; TaskNotes supports it, but it may need to be enabled in settings.
- `backlog`, `up-next`, `to-be-resumed`, `ongoing`, `in-progress`, `done`, `archived`: configured status words.
- `*`: configurable status trigger.
- `2h`, `30min`, `1h30m`: parsed as time estimates.
- `daily`, `weekly`, `every Monday`: parsed as recurrence.

Examples:

```text
Prepare launch checklist tomorrow @business #marketing high
Review contract next Friday @dev +[[Client Work]] in-progress
Draft weekly reflection @personal 30min
```

Useful docs:

- TaskNotes NLP syntax: https://tasknotes.dev/features/inline-tasks/
- TaskNotes task properties: https://tasknotes.dev/settings/task-properties/

## First Things To Open

- `_master/01-Context.md`
- `_master/system/context/<today>.md`
- `_master/_obsidian/bases/content-kanban.base`
- `_master/_obsidian/bases/tasks-home.base`
- `_master/_obsidian/bases/tasks-today.base`
