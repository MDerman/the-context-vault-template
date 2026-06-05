---
type: agent-reference
status: enabled
---
# Context Folders

Create/register a new context folder:

```bash
vault folder -n new-context-folder -s active
vault folder -n new-context-folder -s archived
```

Use `--content-enabled` when the context folder should have `_obsidian/content` infrastructure.

Implementation script: `_master/system/scripts/folder.py`.
