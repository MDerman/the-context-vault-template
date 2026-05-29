---
name: vault
description: Locate and use Matt Derman's personal Workspace vault containing tasks, projects, epics, library notes, Impression knowledge, personal brand material, and personal notes. Use when the user asks for vault context, Workspace notes, personal knowledge, Impression notes, task/project/epic routing, TaskNotes tasks, or Matt Derman-specific reference material.
---

Vault root: use `vault root`.

First move:

```bash
cd "$(vault root)"
vault inventory
```

Use `vault inventory` as low-context routing source. It prints context folders, TaskNotes statuses, epics, and projects with paths. Add `--json` if machine parsing helps. Read `AGENTS.md` only when layout or policy detail matters.

Create routed TaskNotes task using existing names from inventory:

```bash
vault task create business "Task title" --project "Existing Project" --epic "Existing Epic" --status backlog --priority normal
```

Useful optional task flags: `--due YYYY-MM-DD`, `--scheduled YYYY-MM-DD`, `--time-estimate MINUTES`, `--body TEXT`, `--dry-run`.

Create missing routing objects:

```bash
vault project create business "New Project" --epic "Existing Epic" --status backlog
vault epic create business "New Epic" --status in-progress
vault folder --name 06-new-context --status active
```

After changing tasks/projects/epics/contexts, run `vault context` when agent-readable rollups should refresh.
