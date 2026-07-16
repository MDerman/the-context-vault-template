---
type: agent-reference
status: enabled
---
# Agent Skills Sync

Read [[_master/agents/README-skills|Skill SOP]] for source, grouping, policy, dependency, and collision rules.

```bash
vault skills sync --dry-run
vault skills sync --apply
```

Default mode is dry run. Canonical implementation lives at `_master/agents/sync_skills.py`. Old `_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh` command is compatibility wrapper only.

Source roots:

- `_master/agents/auto-skills`: implicit invocation allowed.
- `_master/agents/manual-skills`: explicit invocation only.
- `_master/agents/gh-skills`: publisher metadata unchanged.
- `_master/agents/skills`: generated flat symlink catalog.

Use recursive `_lower-kebab` organizer folders. Sync validates every source and global collision before changing files, enforces auto/manual metadata, repairs moved dependency projections, rebuilds catalog, and maintains per-skill global links. It never imports target-only skills.

After apply, restart Codex or open new task because current task catalog is cached.
