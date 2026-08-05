---
type: agent-reference
status: enabled
---
# Attachments

Dry-run attachment routing and cleanup:

```bash
vault attachments
```

Apply the planned cleanup:

```bash
vault attachments --apply
```

Verify after cleanup:

```bash
vault attachments --verify-only
```

Reconcile a fresh Notion Learning export against current vault notes. This is
read-only by default and writes an auditable manifest before any changes:

```bash
vault attachments --reconcile-learning-export "/path/to/LEARNINGRECON" --repair-deterministic-global
vault attachments --reconcile-learning-export "/path/to/LEARNINGRECON" --repair-deterministic-global --apply
```

Reconciliation preserves current note prose and frontmatter, restores missing
export embeds, renames generic media to globally unique note-derived basenames,
and refuses ambiguous note or attachment mappings.

The vault convention is that note attachments live under the top-level root folder that owns the note, such as `_library/_obsidian/attachments` or `business/_obsidian/attachments`. Obsidian's built-in paste destination is the temporary inbox `_system/_obsidian/attachments/_inbox`.

Dry-run/apply reports and quarantined unreferenced import files are written outside the vault under `~/Downloads/vault-generated/`. After each dry-run or apply run, Finder opens that folder.

Implementation script: `_system/commands/attachments.py`.
