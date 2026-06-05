---
type: agent-reference
status: enabled
---
# Agent Skills Sync

Preview or apply local coding-agent skill symlinks:

```bash
_master/system/bootstrap/sync-agent-skills.sh --dry-run
_master/system/bootstrap/sync-agent-skills.sh --apply
```

The script links local skill targets such as `~/.codex/skills` and `~/.claude/skills` to this vault's `_master/agents/skills`.
