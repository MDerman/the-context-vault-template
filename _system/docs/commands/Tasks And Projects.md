---
type: agent-reference
status: enabled
---
# Tasks And Projects

TaskNotes uses one Markdown file per task under `<context-folder>/_obsidian/tasks/`. Create tasks only for executable next actions, reminders, or decisions needing follow-up.

Projects and epics are ordinary Obsidian notes:

```text
<context-folder>/_obsidian/projects/
<context-folder>/_obsidian/epics/
```

Use epics for larger themes, projects for concrete workstreams, and tasks for executable work.

## Commands

Create a TaskNotes task with validated existing project/epic links:

```bash
vault task create business "Follow up with partner" --project "Partnerships" --epic "Growth" --status up-next
```

Create a project note:

```bash
vault project create business "New Project" --epic "Growth" --status backlog
```

Use `vault inventory` first so task links use actual project and epic names. Use `vault task create --help` and `vault project create --help` for optional `due`, `scheduled`, `timeEstimate`, and dry-run flags.

## Task Model

Configured statuses:

- `backlog`
- `up-next`
- `to-be-resumed`
- `ongoing`
- `in-progress`
- `done`
- `archived`

Default status is `backlog`. Unspecific capture routes to current `default_capture` context.

Keep routing and hierarchy separate:

```yaml
---
title: Example task
status: backlog
priority: normal
scheduled:
due: 2026-06-01
timeEstimate: 60
contexts:
  - business
projects:
  - "[[business/_obsidian/projects/Example Project|Example Project]]"
epic: "[[business/_obsidian/epics/Example Epic|Example Epic]]"
tags:
  - task
---
```

- `scheduled`: date to start, surface, or intentionally work on task.
- `due`: deadline.
- New tasks should not receive `scheduled` by default.
- Never use `due_date` or `scheduled_date`; Bases, inventory, and Dashboard read native `due` and `scheduled`.
- `timeEstimate`: planned effort in minutes.
- `timeEntries`: TaskNotes time-tracking records.
- `pomodoros`: Pomodoro records/counts.
- Never use generic `duration` for TaskNotes effort.

Sprints are not modeled. Ignore imported sprint data unless explicitly archiving it.

## TaskNotes Shorthand

- `#tag`: tag.
- `@context`: context and folder routing.
- `+project` or `+[[Project Name]]`: project link.
- `tomorrow`, `next Friday`, `January 15 at 3pm`: date/time.
- `high`, `normal`, `low`: priority.
- configured status word or `*`: status.
- `2h`, `30min`, `1h30m`: estimate.
- `daily`, `weekly`, `every Monday`: recurrence.

`!` is configurable priority trigger and may require TaskNotes setting.

## Projects And Epics

Project frontmatter:

```yaml
---
type: project
status: backlog
contexts:
  - business
epic: "[[business/_obsidian/epics/Example Epic|Example Epic]]"
---
```

Epic frontmatter:

```yaml
---
type: epic
status: backlog
contexts:
  - business
---
```

## Bases

Vault-wide Bases live under `_system/_obsidian/bases/`; context dashboards live under each context folder's `_obsidian/bases/`.

Vault-wide task/project/epic views include:

- `_system/_obsidian/bases/tasks-today.base`
- `_system/_obsidian/bases/tasks-this-week.base`
- `_system/_obsidian/bases/epics-all.base`

Context views include `context-dashboard.base`, `projects-dashboard.base`, and `epics-dashboard.base`. Vault-wide project/epic views include active context folders by default; archived folders remain available but excluded.

TaskNotes Kanban Bases group columns by `status` and use `projects` as horizontal swimlanes. TaskNotes command views remain separate from dashboard Bases.

Google Calendar mirrors `scheduled` and `due` to separate calendars. Event/block/mirror rules: [[Google Calendar]].

## Low-Context Searches

Use `vault inventory` first. Then use `rg` filename-first and inspect opening lines only:

```bash
sed -n '1,60p' "business/_obsidian/tasks/starter-task.md"
```

Common queries:

```bash
rg -l '^\s*epic:.*Current dev' business/_obsidian/tasks
rg -l '^status: in-progress$' business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks | head -5
for s in in-progress ongoing to-be-resumed up-next backlog; do rg -l "^status: $s$" business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks; done | head -50
```

If exact Obsidian Base order matters, check `tasknotes_manual_order` or use Obsidian.

Implementation scripts: `_system/commands/task.py`, `_system/commands/project.py`.
