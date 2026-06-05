---
type: agent-reference
status: enabled
---
# Brain Dump

Import the configured Apple Note directly:

```bash
vault sync
```

Brain Dump Apple Note deletion/clearing is only allowed through `refresh.py` or `brain_dump.py`, after the content and attachments have been written to the vault. Clearing must leave the Apple Note title in the body, so Notes/iCloud never collapses the source note title.

Implementation script: `_master/system/scripts/brain_dump.py`.

Organize the imported Brain Dump inbox through the vault skill:

```bash
vault triage prepare
vault triage clear-import
vault triage apply
```

The organize flow creates backups under `_master/system/inbox/BRAIN_DUMP_BACKUPS/`, proposal notes under `_master/system/inbox/BRAIN_DUMP_PROPOSALS/`, and the review Base at `_master/_obsidian/bases/BRAIN_DUMP_TRIAGE.base`.
