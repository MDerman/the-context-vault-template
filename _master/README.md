# Master Folder

`_master` is the vault operating layer: shared agent context, reusable tooling, bootstrap code, generated dashboards, Obsidian system assets, and local automation.

## Folder Map

- `_master/_obsidian`: master dashboards, Bases, templates, Excalidraw assets, and system notes used across context folders.
- `_master/agents`: shared agent skills and skill storage. Active shared skills live in `_master/agents/skills`; manual-only skill pack sources live in `_master/agents/skill-packs`; dormant/non-discoverable skill storage lives in `_master/agents/skills-dump`.
- `_master/env`: local environment-variable tooling and tracked placeholders. See `[[_master/env/README-env-tooling|README-env-tooling]]`.
- `_master/general-tools`: default home for reusable scripts, Mac automation, one-off utilities, and tool folders that are not part of the `vault` command surface.
- `_master/system`: bootstrap, public export, migrations, generated context, vault command scripts, installer scripts, and system documentation. See `[[_master/system/README-vault-system-and-bootstrapped|README-vault-system-and-bootstrapped]]`.

## Core Docs

- `[[_master/01-Context|01-Context]]`: vault architecture, folder model, data model, and context folder rules.
- `[[_master/system/context/SCRIPTS|SCRIPTS]]`: normal `vault` command workflows.
- `[[_master/system/context/SCRIPT-REFERENCE|SCRIPT-REFERENCE]]`: fuller script inventory and one-time script cautions.
- `[[_master/system/context/OBSIDIAN-PROFILE|OBSIDIAN-PROFILE]]`: Obsidian profile, plugins, templates, UI, and Sync Embeds.
- `[[_master/system/bootstrap/bootstrap-public-README|bootstrap-public-README]]`: source for public root `README.md`.
- `[[_master/system/README-vault-system-and-bootstrapped|README-vault-system-and-bootstrapped]]`: internal bootstrap/export/system mechanics.

## Agent Routing Index

Use this when `AGENTS.md` says to discover progressively.

- Current vault state: read `[[_master/system/context/CONTEXT|CONTEXT]]`, run `vault inventory`, then use `[[_master/Dashboard|Dashboard]]` when a dashboard helps.
- Tasks, projects, epics: run `vault inventory`, read `[[_master/system/context/script-docs/Tasks And Projects|Tasks And Projects]]`, then use `<context-folder>/_obsidian/tasks`, `<context-folder>/_obsidian/projects`, and `<context-folder>/_obsidian/epics`.
- Calendar and time blocks: read `[[_master/system/context/script-docs/Google Calendar|Google Calendar]]`, then use `vault gcal`.
- Content: read `[[_master/01-Context#Content|01-Context / Content]]` and `[[_master/system/context/script-docs/Content Schedules|Content Schedules]]`, then use content-enabled `<context-folder>/_obsidian/content` and `<context-folder>/_obsidian/content-schedules`.
- Context folder create/register/rename: read `[[_master/system/context/script-docs/Context Folders|Context Folders]]`, then use `vault folder`.
- Scripts and vault commands: read `[[_master/system/context/SCRIPTS|SCRIPTS]]` first, `[[_master/system/context/SCRIPT-REFERENCE|SCRIPT-REFERENCE]]` for full inventory, then `vault <command> --help`.
- General tools and new CLIs: use `_master/general-tools`; add Homebrew formulas to `_master/system/bootstrap/Brewfile`.
- Dependency repos: use `[[_master/system/context/script-docs/Dependency Repos|Dependency Repos]]`; config lives at `_master/system/config/deps.json`.
- Skills: use this README's Skill SOP plus `[[_master/system/context/script-docs/Agent Skills Sync|Agent Skills Sync]]`.
- Bootstrap, public export, and upgrades: read `[[_master/system/README-vault-system-and-bootstrapped|README-vault-system-and-bootstrapped]]`, `[[_master/system/context/script-docs/Bootstrap Export|Bootstrap Export]]`, and `[[_master/system/context/script-docs/Public Vault Upgrade|Public Vault Upgrade]]`.
- Obsidian profile, theme, Bases, plugin settings, Sync Embeds: read `[[_master/system/context/OBSIDIAN-PROFILE|OBSIDIAN-PROFILE]]`; for styling/functionality, also read `_master/system/obsidian_notes/editing_obsidian.md`.
- Attachments: read `[[_master/system/context/script-docs/Attachments|Attachments]]`; attachments belong under the owning root folder's `_obsidian/attachments`.
- Brain Dump: read `[[_master/system/context/script-docs/Brain Dump|Brain Dump]]`; imported source lives at `_master/system/inbox/BRAIN_DUMP.md`.
- Env/auth/secrets: read `[[_master/env/README-env-tooling|README-env-tooling]]`; keep real values in ignored local files only.
- Library changes: read `_library/LIBRARY.md` before renaming, organizing, adding, or removing files under `_library`.
- Entity operating rules/proof: read the relevant `<context-folder>/<context-folder>.md`.

## Low-Context Searches

Use `vault inventory` first. Then use `rg` filename-first and inspect opening lines only:

```bash
sed -n '1,60p' "business/_obsidian/tasks/starter-task.md"
```

Common task/content queries:

```bash
rg -l '^\s*epic:.*Current dev' business/_obsidian/tasks
rg -l '^status: in-progress$' business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks | head -5
for s in in-progress ongoing to-be-resumed up-next backlog; do rg -l "^status: $s$" business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks; done | head -50
rg -l '^status: (idea|cogs-are-turning|draft|planning-scripting|scheduled)$' business/_obsidian/content/items personal-brand/_obsidian/content/items 2>/dev/null | head -50
```

If exact Obsidian Base drag order matters, check `tasknotes_manual_order` or use Obsidian.

## Tooling SOP

When adding a new script or tool:

1. Put general utilities under `_master/general-tools/<tool-name>/` by default.
2. Put reusable agent-facing vault commands under `_master/system/scripts/` only when they belong in the `vault` dispatcher.
3. Document general tools in their own local README when they need usage notes; document `vault` commands in `_master/system/context/script-docs/` and link them from `[[_master/system/context/SCRIPTS|SCRIPTS]]`.
4. Prefer Homebrew for CLI dependencies. Add required formulas to `_master/system/bootstrap/Brewfile` so new bootstrap installs can run the tools.
5. Update `_master/system/bootstrap/install_dependencies.sh` only when dependency installation behavior changes, not for every new formula.
6. Keep real auth, tokens, local credentials, and secrets out of tracked files. Document env names in `_master/env/.env.base` and the workflow in `[[_master/env/README-env-tooling|README-env-tooling]]`.

## Skill SOP

- Active shared skills: `_master/agents/skills/<skill>/SKILL.md`.
- Manual-only discoverable skills: `_master/agents/skill-packs/<skill>/SKILL.md`, symlinked into `_master/agents/skills/manual/<skill>`.
- External repos that the vault depends on are tracked in `_master/system/config/deps.json` and managed with `vault deps`.
- Clone external open source dependencies under `~/Code/open_source/<repo-name>`.
- If an external repo contains skills, do not copy the repo into the vault. Add a managed projection in `deps.json` from the repo skill folder to either `_master/agents/skill-packs/<skill>` for manual-only use or `_master/agents/skills/<skill>` for active shared use.
- Manual-skill projections create vault-owned wrapper dirs. The wrapper owns `agents/openai.yaml`; `SKILL.md` and related source files are symlinked back to the external repo checkout.
- Every manual-only skill must include `agents/openai.yaml` with:

```yaml
policy:
  allow_implicit_invocation: false
```

- Dormant/non-discoverable skills: `_master/agents/skills-dump/<skill>/`.
- After adding or changing dependency projections, run `vault deps sync --dry-run`, then `vault deps sync --apply` if the output is right.
- After changing shared skills or skill packs, run `_master/system/bootstrap/sync-agent-skills.sh --dry-run`, then `--apply` if the output is right.
