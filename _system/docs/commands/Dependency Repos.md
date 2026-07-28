---
type: agent-reference
status: enabled
---
# Dependency Repos

External repos the vault depends on are tracked separately from skills.

Config:

```text
_system/config/deps.json
```

Commands:

```bash
vault deps status
vault deps sync --dry-run
vault deps sync --apply
vault deps project-auto-skills --apply
```

Use dependency repos for any external checkout the vault should keep fresh during `vault upgrade --apply`. Open source checkouts belong under:

```text
~/Code/open_source/<repo-name>
```

Each repo can define projections. A projection maps one repo folder into a vault target. Skill projections are only one projection type.

A repo may also define a vault-owned setup hook:

```json
"setup": {
  "script": "_system/bootstrap/install_agent_canvas.py"
}
```

Setup scripts must live inside vault. `vault deps status` checks hook health and reports `setup: ok`, `needs-setup`, or `pending`. Sync invokes hooks without shell interpolation after repo and projection sync. Clone/update forces build; unchanged repos repair unhealthy setup only. Hook failure stops install or upgrade before state advances.

Skill projection rules:

- Source stays in the external repo checkout.
- Target lives under grouped `_system/agents/manual-skills` or `_system/agents/auto-skills` source.
- The vault creates a managed projection dir at the target.
- Skill files and supporting assets are materialized from upstream for cross-machine portability and refresh on dependency sync.
- `agents/openai.yaml` preserves upstream metadata while vault owns invocation policy: false for `manual-skill`, true for `auto-skill`.
- Existing unmanaged targets are backed up before replacement.
- `vault skills sync --apply` owns flat catalog symlink and updates dependency config/marker when wrapper moves.

Current tracked repos:

- `frontend-slides` -> `~/Code/open_source/frontend-slides`
- `agent-canvas` -> `~/Code/open_source/agent-canvas`
- `googleworkspace-cli` -> `~/Code/open_source/googleworkspace-cli`

Current projected auto skills:

- `agent-canvas`

Current projected manual skills:

- `frontend-slides`
- `gws-shared`
- `gws-drive`
- `gws-gmail`
- `gws-calendar`
- `gws-sheets`

When adding a new external repo with skills:

1. Add the repo to `_system/config/deps.json`.
2. Add projections for only the skill folders that should be exposed.
3. Use `type: manual-skill` for explicit-only skills or `type: auto-skill` for implicit skills.
4. Run `vault deps sync --dry-run`.
5. If output is right, run `vault deps sync --apply`.
6. Start fresh Codex task and confirm discovery; current tasks cache catalog.

`vault deps sync --apply` clones missing repos, checks out release-locked commits when present, rebuilds managed wrappers, runs skill sync when projections change, then runs setup hooks.

`vault deps project-auto-skills --apply` only repairs auto-skill projections from dependency checkouts already present. It never fetches, checks out, builds, or modifies dependency repos. Worker vault sync uses this before skill sync so dirty dependency development checkouts remain untouched.

Dirty or divergent dependency repos stop the sync with a clear error. Resolve local changes in the dependency repo first, then retry.

## Agent Canvas Local Development

Agent Canvas skill and reference files are materialized from editable checkout by dependency projection. Run `vault deps project-auto-skills --apply` after editing `skills/agent-canvas/` to refresh projected files.

Fresh public install and `vault upgrade --apply` install Bun/Node, clone checkout, build CLI/web app, run `bun link`, and create `~/.local/bin/agent-canvas`. CLI source changes need a rebuild. Links remain pointed at checkout:

```bash
cd ~/Code/open_source/agent-canvas
bun run build
agent-canvas --version
```

Run `vault deps sync --apply` to repair dependencies, build output, package link, or global command. Existing unrelated `~/.local/bin/agent-canvas` commands are never overwritten.

Generated `node_modules/` and `dist/` paths are ignored. Tracked local edits make the dependency repo dirty, so later `vault deps sync --apply` runs stop instead of overwriting local work.
