---
type: agent-reference
status: enabled
---
# Agent Context

Regenerate compact agent-readable state:

```bash
vault context
```

This writes:

```text
_master/system/context/CONTEXT.md
_master/system/context/context.json
_master/system/context/*.md
_master/Dashboard.md
```

It also creates current 4-week content schedule notes for content-enabled context folders with enabled `_obsidian/content/content-cadence.json`.
By default it removes stale generated agent periodic rollups; pass `--keep-agent-periodic-history` through `refresh.py` or `context.py` to preserve them.

Implementation script: `_master/system/scripts/context.py`.
