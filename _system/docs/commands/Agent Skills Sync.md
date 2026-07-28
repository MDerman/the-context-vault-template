---
type: agent-reference
status: enabled
---
# Agent Skills Sync

Read [[_system/agents/README-skills|Skill SOP]] for source, grouping, policy, dependency, and collision rules.

```bash
vault skills sync --dry-run
vault skills sync --apply
```

Default mode is dry run. Canonical implementation lives at `_system/agents/sync_skills.py`; bootstrap and dependency sync invoke it directly.

Source roots:

- `_system/agents/auto-skills`: implicit invocation allowed.
- `_system/agents/manual-skills`: explicit invocation only.
- `_system/agents/gh-skills`: publisher metadata unchanged.
- `_system/agents/skills`: generated flat symlink catalog.

Use recursive `_lower-kebab` organizer folders. Sync validates every source and global collision before changing files, enforces auto/manual metadata, repairs moved dependency projections, rebuilds catalog, and maintains per-skill global links. It never imports target-only skills.

After apply, restart Codex or open new task because current task catalog is cached.
