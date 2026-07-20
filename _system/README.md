# System Operating Layer

Concise source of truth for vault architecture, ownership, and routing. Detailed SOPs live in linked topic docs.

## Start Here

- [[AGENTS]]: agent behavior and global routing.
- [[Dashboard|Dashboard]]: Obsidian home and current rollups.
- [[_system/docs/commands/README|Scripts]]: `vault` command index.
- [[_system/docs/obsidian/README|Obsidian Profile]]: plugins, templates, Bases, mobile profile, and UI.
- [[_system/bootstrap/README|Bootstrap]]: public export, installs, releases, and upgrades.
- [[_system/agents/README|Agents]]: shared skills and skill storage.
- [[_system/tools/README|General Tools]]: tools outside `vault`.

## Mental Model

```text
root workspace = only Obsidian vault and control panel
context folders = source-of-truth operating workspaces
_system = operating docs, scripts, generated state, skills, and shared Obsidian support
_library = raw and semi-processed learning/source material
_wiki = synthesized reusable knowledge
other = archive or holding area used only intentionally
```

Context folders are folders inside root vault, not standalone vaults. Open root workspace for Obsidian and agent work.

Use `vault inventory` for current registered contexts, statuses, projects, and epics. Do not hardcode current working set into architecture docs.

## Context Folders

Each context folder owns current operating information for one entity or domain:

```text
<context-folder>/
  <context-folder>.md
  _obsidian/
    attachments/
    bases/
    content/            # content-enabled only
    content-schedules/  # content-enabled only
    epics/
    excalidraw/
    periodic/<period>/
    projects/
    tasks/
    templates/periodic/
  <ordinary context-specific folders>
```

Context folder note is local routing/control note. Main controls:

```yaml
---
status: active
content_enabled: false
default_capture: true
---
```

- `status: active`: included by default in generated rollups.
- `status: archived`: retained but excluded from default rollups.
- blank/missing status: not active.
- `content_enabled: true`: enables content storage, cadence, schedules, and views.
- `default_capture: true`: preferred context for unspecific capture; fallback is first active context.
- Entity operating sections such as `## Identity` and `## Momentum` are optional human organization, not generator inputs.

Context folders hold source-of-truth docs, assets, tasks, decisions, SOPs, training, periodic notes, and active references. Samples, courses, research dumps, and learning notes belong in `_library`; durable synthesis belongs in `_wiki`.

Commands and full rules: [[_system/docs/commands/Context Folders|Context Folders]].

## Ownership And Core Paths

- Tasks: `<context-folder>/_obsidian/tasks/`
- Projects: `<context-folder>/_obsidian/projects/`
- Epics: `<context-folder>/_obsidian/epics/`
- Periodic notes: `<context-folder>/_obsidian/periodic/<daily|weekly|monthly|quarterly|yearly>/`
- Content: `<context-folder>/_obsidian/content/`
- Content schedules: `<context-folder>/_obsidian/content-schedules/`
- Attachments: owning top-level folder's `_obsidian/attachments/`
- Shared Bases: `_system/_obsidian/bases/`
- Shared templates: `_system/_obsidian/templates/shared/`
- Shared Excalidraw: `_system/_obsidian/excalidraw/`

Context-owned operating folders use `_obsidian` so ordinary work folders remain visually distinct. No default `notes` folder.

## Tasks, Projects, And Epics

- TaskNotes tasks: executable next actions, reminders, or decisions needing follow-up.
- Projects: concrete workstreams stored as ordinary Obsidian notes.
- Epics: larger themes/areas grouping projects and tasks.
- Task routing/hierarchy uses separate `contexts`, `projects`, and `epic` fields.
- Use `scheduled` for intended work/surface date; use `due` for deadline.
- Use `timeEstimate`, `timeEntries`, and `pomodoros`; never generic `duration`.

Commands, schemas, statuses, shorthand, and Bases: [[_system/docs/commands/Tasks And Projects|Tasks And Projects]].

Calendar mirror/event rules: [[_system/docs/commands/Google Calendar|Google Calendar]].

## Periodic Notes

Context folder periodic notes are editable source of truth. Generated vault rollups combine them through Sync Embeds.

Templates live under each context folder's `_obsidian/templates/periodic/`. Commands and generated paths: [[_system/docs/commands/Periodic Rollups|Periodic Rollups]].

## Content

`_obsidian/content` stores owned content items, ideas, publication definitions, and drafts. It is not task system; executable work about content belongs in `_obsidian/tasks`.

Content state lives in note frontmatter. `publish_date` drives calendar views; `status` drives kanban views. Cadence config generates fixed four-week schedule notes.

Schemas, views, cadence formats, and commands: [[_system/docs/commands/Content Schedules|Content System And Schedules]].

## Attachments

Attachments belong to top-level folder owning note. Obsidian paste inbox is `_system/_obsidian/attachments/_inbox`; routing command moves imports to correct owner.

SOP: [[_system/docs/commands/Attachments|Attachments]].

## System Folder

- `_obsidian/`: shared Bases, templates, attachments, Excalidraw, and vault rollups.
- `agents/`: auto/manual/GitHub-managed skill sources and generated catalog.
- `bootstrap/`: public install, export, release, and upgrade framework.
- `commands/`: `vault` dispatcher, commands, internals, and tests.
- `config/`: vault, dependency, calendar, and Dashboard configuration.
- `docs/`: command, Obsidian, and workflow documentation.
- `env/`: env workflow docs and tracked placeholders.
- `inbox/`: Brain Dump and attachment ingestion files.
- `migrations/`: empty registry for future public-upgrade migrations.
- `state/`: ignored local backups, reports, install state, and export manifest.
- `sync/`: rclone backup/sync tooling.
- `tools/`: reusable tools outside `vault` dispatcher.

Generated files carry managed markers. Edit source notes/docs, not generated outputs.

## Refresh And Generated Views

`vault refresh` is full refresh entrypoint. It updates Calendar task mirrors, content schedules, source periodic notes, vault Sync Embed rollups, root `Dashboard.md`, and local Git maintenance. Brain Dump ingestion remains opt-in with `--sync-brain-dump`.

Agents use live `vault inventory` output and source notes; no persistent agent-context packets are generated.

Current command behavior: [[_system/docs/commands/Refresh|Refresh]].

## Library And Wiki

`_library` stores learning material, references, swipe files, imports, templates being studied, course material, research dumps, and source notes. Read [[_library/LIBRARY|Library]] before organizing it.

`_wiki` stores clearer, reusable synthesis guided by [[_wiki/AGENTS]] and [[_wiki/karpathy-initial-proompt]]. Promote learned material into a context folder only when it becomes an operating artifact.

## Other Workflows

- Relay sharing: [[_system/docs/workflows/README-relay-collaboration|Relay Collaboration]].
- Brain Dump routing: [[_system/docs/workflows/README-brain-dump-routing|Brain Dump Routing]].
- Bootstrap/export: [[_system/bootstrap/README|Bootstrap]].
- Mobile profile: [[_system/docs/obsidian/README#Mobile Profile|Mobile Profile]].

## Naming And Migration

- Use `README.md` for folder doorway docs.
- Use `README-<topic>.md` for companion SOPs, references, and quick starts.
- Use `AGENTS.md` only for agent behavior and routing.
- Move legacy material one small slice at a time into matching context folder. Never bulk-migrate because new structure exists.
