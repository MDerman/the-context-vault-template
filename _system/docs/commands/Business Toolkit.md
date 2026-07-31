---
type: agent-reference
status: enabled
---

# Business Toolkit

The navigation home is [[_library/business_toolkit/README|Business Toolkit]], and the canonical literal scaffold lives at [[_system/bootstrap/templates/business-context/README|Business Context Scaffold]]. Fresh business contexts receive its complete ordinary folder tree. Registration and later synchronization install only selected managed templates, Templater rules, state, and 📋 Iconize markers for operating folders that already exist.

## Interactive installer

```bash
vault business-toolkit
```

The wizard lists current business contexts, accepts a multi-selection, and allows component or group exclusions.

## Preview and apply

```bash
vault business-toolkit sync --context-folders business,studio
vault business-toolkit sync --context-folders business,studio --apply
vault business-toolkit sync --configured --apply
vault business-toolkit status --all-business
```

Available groups are `meetings`, `product`, `gtm`, `operations`, and `skills`. Component ids are listed in the canonical pack manifest.

Normal sync never creates, deletes, or restructures ordinary business folders. It protects locally changed installed templates and changed managed icons. Apply mode preflights all selected contexts: a terminal asks once before overwriting all conflicts, a non-interactive run aborts without mutation, and `--force` explicitly replaces them.

Excluding a previously installed component removes its managed Templater rule, unchanged installed template, and unchanged managed icon. Operating folders and business notes are never deleted.

Each configured context stores its selection, installed hashes, icon ownership, and pack version in `_obsidian/business-toolkit.json`. Desktop and mobile Iconize files are reconciled when present; unrelated settings and custom icons are preserved.

Periodic templates, TaskNotes templates, generated Bases, context notes, and Excalidraw setup remain owned by the core bootstrap generator.
