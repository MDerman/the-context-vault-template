---
type: agent-reference
status: enabled
---
# Epics

Create an epic in a context folder and refresh the related TaskNotes views:

```bash
vault epic create business "New Epic"
```

This creates `<context-folder>/_obsidian/epics/<Epic>.md`, generates the per-epic Kanban Base under `<context-folder>/_obsidian/bases/`, and updates the managed epic views in [[_system/_obsidian/bases/tasks-kanban-v1.base]].

Useful variants:

```bash
vault epic list
vault epic sync
vault epic rename impression "Old Epic" "New Epic"
vault epic delete impression "New Epic"
vault epic delete impression "New Epic" --force
```

Rename moves the epic note, updates its `title`, rewrites linked task references, regenerates per-epic task Bases, and updates the vault task kanban epic views. Delete refuses to remove an epic while tasks still link to it unless `--force` is passed.

Implementation script: `_system/commands/epic.py`.
