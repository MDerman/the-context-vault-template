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

The same command previews or applies local global-agent configuration. `_system/agents/config/AGENTS.md` is the versioned source; the current machine's footer is rendered from the private topology registry. Apply converges `~/.codex/AGENTS.md`, keeps `~/.claude/CLAUDE.md` linked to it, and ensures Vault `CLAUDE.md`, `.agents/skills`, and `.claude/skills` through the shared `_system/agents/global_agent_configuration.py` implementation. Public vaults without the private source or registry skip personal home configuration while retaining Vault-local alias setup.

Source roots:

- `_system/agents/auto-skills`: implicit invocation allowed.
- `_system/agents/manual-skills`: explicit invocation only.
- `_system/agents/gh-skills`: publisher metadata unchanged.
- `_system/agents/working-repos`: generated tracked copies of explicitly configured repository skills, flat under each repository ID.
- `_system/agents/skills`: generated flat symlink catalog.

Use recursive `_lower-kebab` organizer folders. Sync validates every source and global collision before changing files, materializes selected `skill_projections` from the private repository topology, enforces auto/manual metadata, repairs moved dependency projections, rebuilds catalog, and maintains per-skill global links. It never projects every registered repo automatically.

Repository projections use repo-relative source paths and become `<repo-id>-<local-name-without-l->`. A missing whole checkout preserves its valid tracked projection; a present checkout with a missing configured source fails. The generated local-repo tree is excluded from public bootstrap exports.

After apply, restart Codex or open new task because current task catalog is cached.
