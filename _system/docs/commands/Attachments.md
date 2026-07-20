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

The vault convention is that note attachments live under the top-level root folder that owns the note, such as `_library/_obsidian/attachments` or `business/_obsidian/attachments`. Obsidian's built-in paste destination is the temporary inbox `_system/_obsidian/attachments/_inbox`.

Dry-run/apply reports and quarantined unreferenced import files are written outside the vault under `~/Downloads/vault-generated/`. After each dry-run or apply run, Finder opens that folder.

Implementation script: `_system/commands/attachments.py`.
