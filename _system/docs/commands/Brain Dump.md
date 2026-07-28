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

Implementation script: `_system/commands/brain_dump.py`.

Use [[_system/agents/manual-skills/_vault/triage-brain-dump-section/SKILL|Triage Brain Dump Section]] for reviewed, section-level routing.

Optional batch proposal commands remain available:

```bash
vault triage prepare
vault triage clear-import
vault triage apply
```

Batch flow implementation: `_system/commands/brain_dump_triage.py`. It creates backups under `_system/inbox/BRAIN_DUMP_BACKUPS/`, proposal notes under `_system/inbox/BRAIN_DUMP_PROPOSALS/`, and review Base at `_system/_obsidian/bases/BRAIN_DUMP_TRIAGE.base`.
