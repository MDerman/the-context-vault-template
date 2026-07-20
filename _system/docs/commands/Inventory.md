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

Inventory reads source notes on every invocation and writes nothing. Output includes:

- current daily, weekly, monthly, quarterly, and yearly IDs;
- default capture context;
- context status, type, content flag, control-note path, and current periodic paths;
- current vault rollup and content-schedule paths;
- task counts, active routing-task links, and backlog counts;
- epics and projects.

`--json` returns same live state for machine parsing. Use relevant source paths from inventory; no persistent agent-routing packets exist.

Implementation script: `_system/commands/inventory.py`.
