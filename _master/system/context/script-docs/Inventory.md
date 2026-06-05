---
type: agent-reference
status: enabled
---
# Inventory

Print low-context routing inventory for agents:

```bash
vault inventory
vault inventory --active-only
vault inventory --json
```

This lists context folders, configured TaskNotes statuses, epics, and projects without loading the larger agent context docs.

Implementation script: `_master/system/scripts/inventory.py`.
