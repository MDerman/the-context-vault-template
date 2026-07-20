# Agents

Agent skills, skill storage, and agent-facing symlink helpers.

Read next:

- [[_system/agents/README-skills|Skill SOP]] for skill SOPs.
- [[_system/docs/commands/Agent Skills Sync|Agent Skills Sync]] for sync command details.

Folders:

- `auto-skills/`: implicitly invokable skill sources, organized under recursive `_lower-kebab` groups.
- `manual-skills/`: explicit-only skill sources, organized under recursive `_lower-kebab` groups.
- `gh-skills/`: publisher-managed skills installed with `gh skill --dir`.
- `skills/`: generated flat symlink-only catalog. Never install or move source content here.
- `skills-dump/`: dormant non-discoverable skills.
- `backups/`: generated backups from skill/deps sync flows.

Canonical command:

```bash
vault skills sync --dry-run
vault skills sync --apply
```

Implementation lives at `_system/agents/sync_skills.py`; bootstrap invokes it directly.
