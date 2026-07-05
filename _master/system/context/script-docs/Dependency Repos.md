---
type: agent-reference
status: enabled
---
# Dependency Repos

External repos the vault depends on are tracked separately from skills.

Config:

```text
_master/system/config/deps.json
```

Commands:

```bash
vault deps status
vault deps sync --dry-run
vault deps sync --apply
```

Use dependency repos for any external checkout the vault should keep fresh during `vault upgrade --apply`. Open source checkouts belong under:

```text
~/Code/open_source/<repo-name>
```

Each repo can define projections. A projection maps one repo folder into a vault target. Skill projections are only one projection type.

Manual skill projection rules:

- Source stays in the external repo checkout.
- Target is usually `_master/agents/skill-packs/<skill>`.
- The vault creates a managed wrapper dir at the target.
- `SKILL.md` and source assets are symlinked from the repo.
- `agents/openai.yaml` is vault-owned and sets `policy.allow_implicit_invocation: false`.
- Existing unmanaged targets are backed up before replacement.

Current tracked repos:

- `frontend-slides` -> `~/Code/open_source/frontend-slides`
- `googleworkspace-cli` -> `~/Code/open_source/googleworkspace-cli`

Current projected manual skills:

- `frontend-slides`
- `gws-shared`
- `gws-drive`
- `gws-gmail`
- `gws-calendar`
- `gws-sheets`

When adding a new external repo with skills:

1. Add the repo to `_master/system/config/deps.json`.
2. Add projections for only the skill folders that should be exposed.
3. Use `type: manual-skill` for manual-only skills, or `type: active-skill` when a skill should live in `_master/agents/skills`.
4. Run `vault deps sync --dry-run`.
5. If output is right, run `vault deps sync --apply`.

`vault deps sync --apply` clones missing repos, fast-forward pulls existing clean repos, rebuilds managed projections, then runs `_master/system/bootstrap/sync-agent-skills.sh --apply` when skill projections changed.

Dirty or divergent dependency repos stop the sync with a clear error. Resolve local changes in the dependency repo first, then retry.
