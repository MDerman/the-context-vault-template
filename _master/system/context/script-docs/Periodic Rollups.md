---
type: agent-reference
status: enabled
---
# Periodic Rollups

Generate current master Obsidian periodic rollups and agent-readable periodic rollups:

```bash
vault periodic
```

Useful variants:

```bash
vault periodic --all
vault periodic --context-folders dev,claudeche
vault periodic --keep-agent-periodic-history
```

Context folder periodic notes remain the editable source of truth. Master rollups live under `_master/_obsidian/periodic/<period>/` and use Sync Embeds for Obsidian. Agent rollups live under `_master/system/context/` as plain readable views.

Monthly periodic notes are intentionally not used.

Implementation script: `_master/system/scripts/periodic.py`.
