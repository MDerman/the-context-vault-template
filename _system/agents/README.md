# Agents

Agent skills, skill storage, and agent-facing symlink helpers.

Read next:

- [[_system/agents/README-skills|Skill SOP]] for skill SOPs.
- [[_system/local/README|Local Vault Data]] for skill/config separation.
- [[_system/docs/commands/Agent Skills Sync|Agent Skills Sync]] for sync command details.

Folders:

- `config/`: private-export-excluded versioned global `AGENTS.md` source and editable machine-role footer templates.
- `auto-skills/`: implicitly invokable skill sources, organized under recursive `_lower-kebab` groups.
- `manual-skills/`: explicit-only skill sources, organized under recursive `_lower-kebab` groups.
- `gh-skills/`: publisher-managed skills installed with `gh skill --dir`.
- `working-repos/`: generated tracked copies of explicitly selected repository-owned skills, flat under `<repo-id>/<projected-skill>`; edit the source repo, never these copies.
- `skills/`: generated flat symlink-only catalog. Never install or move source content here.
- `skills-dump/`: dormant non-discoverable skills.
- `backups/`: generated backups from skill/deps sync flows.

Canonical command:

```bash
vault skills sync --dry-run
vault skills sync --apply
```

Implementation lives at `_system/agents/sync_skills.py`. Regular sync also uses `_system/agents/global_agent_configuration.py` to ensure Vault aliases and render the current machine's `~/.codex/AGENTS.md` plus Claude alias. Bootstrap calls that same shared alias function rather than carrying a second implementation.
