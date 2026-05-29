---
type: operating-system
system_id: "00"
system: start-here
status: enabled
---
# 00-StartHere

This is the entry point for the operating systems layer.

The root vault is the command center. The numbered context folders are the source-of-truth workspaces. The system notes below explain how the vault is structured, what each entity is trying to become, and how tasks, calendar blocks, periodic notes, and agents keep the work moving.

## Read Order

1. Read [[01-Context]] to understand the vault, plugins, scripts, tasks, periodic notes, `library`, `wiki`, and generated agent context.
2. Read [[02-Identity]] and fill or review the identity answers for every active entity.
3. Read [[03-Momentum]] and fill or review the cadence, task, calendar, accountability, and social selling answers for every active entity.

## Current Active Entities

- `01-personal`: personal life, health, relationships, finances, default capture, and personal accountability.
- `02-personal-brand`: personal brand, writing, media, audience, authority, and enabled social selling.
- `03-business`: Impression product and business execution. Content storage is enabled; recurring content/social cadence stays off until its cadence JSON is enabled.

## What To Do In The Morning

1. Open `master/system/context/CONTEXT.md`.
2. Open today's agent daily rollup under `master/system/context/`.
3. Open [[03-Momentum]] to see the embedded momentum systems for active entities.
4. Check `master/_obsidian/bases/tasks-today.base` and `master/_obsidian/bases/tasks-home.base`.
5. Check `master/_obsidian/bases/content-kanban.base` only when content is part of the day. Use entity content calendar views when publish dates matter, and `_obsidian/content-schedules` when planning the 4-week cadence. The content board uses `kanban-bases-view`, grouped into vertical `status` lanes.
6. Run the refresh wrapper before deciding what to work on.

Manual refresh:

```bash
vault refresh
```

Refresh ingests the configured Brain Dump Apple Note first. It writes to `master/system/inbox/BRAIN_DUMP.md`, configured in `master/system/config.json`.

## System Source Files

Context folder answers live in root `DECLARATION.md` files so section headings can be embedded into the master system notes:

```text
<context-folder>/DECLARATION.md#Identity
<context-folder>/DECLARATION.md#Momentum
```

Social Selling, when relevant, lives inside the entity's `Momentum` declaration section.

## Content Source Files

Content-enabled entities have `_obsidian/content/`:

```text
<context-folder>/_obsidian/content/publications/
<context-folder>/_obsidian/content/items/
<context-folder>/_obsidian/content/ideas/
<context-folder>/_obsidian/content-schedules/
<context-folder>/_obsidian/bases/
```

Current content-enabled entities:

- `02-personal-brand`: Matt Derman blog, Copy and Context, YouTube, LinkedIn, X, Substack Notes.
- `03-business`: Impression blog and AI LinkedIn Insights.

Content notes are storage and planning. Tasks still live in `_obsidian/tasks`. A content note becomes work only when it has a real next action, status, date, blocker, or project.

## Future Compiler Model

The intended shape is:

- `DECLARATION.md` files are the source.
- `refresh.py` is the current refresh wrapper.
- `context.py` is the current compiler.
- Flat generated files under `master/system/context/*.md` are compact AI-readable outputs.
- Context folder `_obsidian/periodic/*` notes and Bases are the daily runtime.

V1 creates the source files and the documentation. V1.1 adds `_obsidian/content`, publication definitions, Bases views, dry-run migration scripts, and a local refresh wrapper with Brain Dump ingestion. Proof-checking scripts beyond Apple Notes come later.
