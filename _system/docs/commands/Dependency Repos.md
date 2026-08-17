---
type: agent-reference
status: enabled
---
# Dependency Repos

External repos the vault depends on are tracked separately from skills.

Config:

```text
_system/local/deps.json
```

Commands:

```bash
vault deps status
vault deps sync --dry-run
vault deps sync --apply
vault deps sync --repo <dependency-id> --apply
vault deps project-auto-skills --apply
```

Use dependency repos for any external checkout the vault should keep fresh during `vault upgrade --apply`. Open source checkouts belong under:

```text
~/Code/open_source/<repo-name>
```

Each repo can define projections. A projection maps one repo folder into a vault target. Skill projections are only one projection type.

Set `"sync_enabled": false` on a repo to pause it without forgetting it:

```json
{
  "id": "example-skills",
  "sync_enabled": false,
  "projections": [
    {
      "source": "skills/example",
      "target": "_system/agents/manual-skills/_example/example-skill",
      "type": "manual-skill"
    }
  ]
}
```

A disabled repo remains in `deps.json`, and its existing materialized projections remain discoverable. Dependency sync does not clone, fetch, check out, rebuild projections, or run setup for it. It also does not recreate a disabled projection if its target is later removed. Omit `sync_enabled` or set it to `true` to resume normal syncing. `vault deps status` reports the repo and its projections as disabled.

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
- A skill projection target basename is its local frontmatter name. Its projected H1 is prefixed from the vault's nested organizer hierarchy; optional `title_override` replaces that generated title. Upstream source stays unchanged.
- `agents/openai.yaml` preserves upstream metadata while vault owns invocation policy: false for `manual-skill`, true for `auto-skill`.
- Existing unmanaged targets are backed up before replacement.
- `vault skills sync --apply` owns flat catalog symlink and updates dependency config/marker when wrapper moves.
- Use `type: manual-skill-pack` with `skill_prefix` for a category directory whose direct child directories are skills. The pack projection copies root files such as `README.md`, projects every skill with the prefix, and rewrites README links and slash-invocations to the local names. Set `rewrite_skill_sources` to all jointly projected category roots when skills invoke siblings across categories.

Current tracked repos:

- `frontend-slides` -> `~/Code/open_source/frontend-slides`
- `agent-canvas` -> `~/Code/open_source/agent-canvas`
- `googleworkspace-cli` -> `~/Code/open_source/googleworkspace-cli`
- `marketingskills` -> `~/Code/open_source/marketingskills`
- `claude-seo` -> `~/Code/open_source/claude-seo`
- `swan-gtm-skills` -> `~/Code/open_source/gtm-skills`
- `mattpocock-skills` -> `~/Code/open_source/mattpocock-skills` (sync disabled; projected snapshot retained)

Current projected auto skills:

- `agent-canvas`

Current projected manual skills:

- `frontend-slides`
- `gws-shared`
- `gws-drive`
- `gws-gmail`
- `gws-calendar`
- `gws-sheets`
- all skills from the Marketing Skills dependency under `_corey-marketing-skills/`, using the `corey-` discovery prefix
- all skills from the Claude SEO dependency under `_claude-seo/`, using the `claude-seo-` discovery prefix
- all public skills from the Swan GTM Skills dependency under `_swan-gtm-skills/`, using the `swan-gtm-` discovery prefix
- the retained engineering and productivity snapshots from Matt Pocock's Skills dependency under `_matt-p-skills/`, using the `mp-` discovery prefix (repo sync disabled)

When adding a new external repo with skills:

1. Add the repo to `_system/local/deps.json`.
2. Add projections for only the skill folders that should be exposed.
3. Use `type: manual-skill` for explicit-only skills or `type: auto-skill` for implicit skills.
4. Run `vault deps sync --dry-run`.
5. If output is right, run `vault deps sync --apply`.
6. Start fresh Codex task and confirm discovery; current tasks cache catalog.

`vault deps sync --apply` clones missing repos, checks out release-locked commits when present, rebuilds managed wrappers, runs skill sync when projections change, then runs setup hooks.

Repos with `sync_enabled: false` are skipped by both full dependency sync and `project-auto-skills`; their current projections are left untouched.

Use repeatable `--repo <dependency-id>` selectors when only specific dependencies should be updated and projected.

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
