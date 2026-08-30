---
type: agent-reference
status: enabled
---

# Business Toolkit

This note is the navigation home for the business toolkit. The canonical literal scaffold lives under `_system/bootstrap/templates/context-folders/business/`. Selecting `--folder-template business` for a new context installs its ordinary folder tree and managed templates. A context is considered configured only when `_obsidian/business-toolkit.json` exists; there is no business context type.

## Interactive installer

```bash
vault business-toolkit
```

The wizard lists registered contexts, accepts a multi-selection, and allows component or group exclusions.

## Preview and apply

```bash
vault business-toolkit sync --context-folders business,studio
vault business-toolkit sync --context-folders business,studio
vault business-toolkit sync --configured
vault business-toolkit status --configured
vault business-toolkit unconfigure --context-folders studio
```

Available groups are `meetings`, `product`, `gtm`, `operations`, and `skills`. Component ids are listed in the canonical pack manifest.

Explicit targets may be any registered context. Normal sync never creates, deletes, or restructures ordinary folders. It protects locally changed installed templates and changed managed icons. Apply mode preflights all selected contexts: a terminal asks once before overwriting all conflicts, a non-interactive run aborts without mutation, and `--force` explicitly replaces them.

Excluding a previously installed component removes its managed Templater rule, unchanged installed template, and unchanged managed icon. Operating folders and business notes are never deleted.

Each configured context stores its selection, installed hashes, icon ownership, and pack version in `_obsidian/business-toolkit.json`. Desktop and mobile Iconize files are reconciled when present; unrelated settings and custom icons are preserved.

`unconfigure` safely removes unchanged managed templates, rules, icons, and the marker. Use `--force` only when intentionally discarding locally changed managed files.

Periodic templates, TaskNotes templates, generated Bases, context notes, and Excalidraw setup remain owned by the core bootstrap generator.
