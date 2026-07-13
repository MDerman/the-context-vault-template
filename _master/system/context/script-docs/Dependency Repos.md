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

A repo may also define a vault-owned setup hook:

```json
"setup": {
  "script": "_master/system/bootstrap/install_agent_canvas.py"
}
```

Setup scripts must live inside vault. `vault deps status` checks hook health and reports `setup: ok`, `needs-setup`, or `pending`. Sync invokes hooks without shell interpolation after repo and projection sync. Clone/update forces build; unchanged repos repair unhealthy setup only. Hook failure stops install or upgrade before state advances.

Manual skill projection rules:

- Source stays in the external repo checkout.
- Target is usually `_master/agents/manual-skills/<skill>`.
- The vault creates a managed projection dir at the target.
- `SKILL.md` and source assets are symlinked from the repo.
- `agents/openai.yaml` is vault-owned and sets `policy.allow_implicit_invocation: false`.
- Existing unmanaged targets are backed up before replacement.

Active skill projection rules:

- Target is `_master/agents/skills/<skill>`.
- Target itself must be whole-directory symlink to dependency checkout skill folder.
- `SKILL.md` must be regular source file reached through directory symlink, never symlink inside real target directory.
- Reason: Codex omits real directories containing symlinked `SKILL.md` from skill catalog.
- `vault deps sync --apply` migrates old managed per-file layouts automatically.

Current tracked repos:

- `frontend-slides` -> `~/Code/open_source/frontend-slides`
- `agent-canvas` -> `~/Code/open_source/agent-canvas`
- `googleworkspace-cli` -> `~/Code/open_source/googleworkspace-cli`

Current projected active skills:

- `agent-canvas`

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
6. For active skill, start fresh Codex task and confirm `$<skill>` autocomplete or run catalog probe from [[_master/agents/README-skills|Skill SOP]].

`vault deps sync --apply` clones missing repos, checks out release-locked commits when present, rebuilds managed projections, runs `_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --apply` when skill projections changed, then runs setup hooks. Manual-skill projections remain sourced under `_master/agents/manual-skills`; sync exposes each one as an individual symlink in `_master/agents/skills` so Codex and Claude can discover it.

Dirty or divergent dependency repos stop the sync with a clear error. Resolve local changes in the dependency repo first, then retry.

## Agent Canvas Local Development

Agent Canvas skill and reference files are projected directly from the editable checkout. Changes under `skills/agent-canvas/` become visible to agents without copying files.

Fresh public install and `vault upgrade --apply` install Bun/Node, clone checkout, build CLI/web app, run `bun link`, and create `~/.local/bin/agent-canvas`. CLI source changes need a rebuild. Links remain pointed at checkout:

```bash
cd ~/Code/open_source/agent-canvas
bun run build
agent-canvas --version
```

Run `vault deps sync --apply` to repair dependencies, build output, package link, or global command. Existing unrelated `~/.local/bin/agent-canvas` commands are never overwritten.

Generated `node_modules/` and `dist/` paths are ignored. Tracked local edits make the dependency repo dirty, so later `vault deps sync --apply` runs stop instead of overwriting local work.
