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

Monthly periodic notes are generated from blank default templates. Historic monthly agent rollups are kept so unchecked monthly SOP items can keep appearing on the generated dashboard.

Implementation script: `_master/system/scripts/periodic.py`.
