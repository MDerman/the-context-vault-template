---
name: vault
description: Locate and use Matt Derman's personal Workspace vault containing tasks, projects, epics, library notes, Impression knowledge, personal brand material, and personal notes. Use when the user asks for vault context, Workspace notes, personal knowledge, Impression notes, task/project/epic routing, TaskNotes tasks, or Matt Derman-specific reference material.
---

Vault root: use `vault root`.

First move:

```bash
cd "$(vault root)"
vault inventory
```

Use `vault inventory` as low-context routing source. It prints context folders, TaskNotes statuses, epics, and projects with paths. Add `--json` if machine parsing helps. Read `AGENTS.md` only when layout or policy detail matters.

## Low-Context Lookups

Use `rg` filename-first, then inspect only frontmatter/opening notes:

```bash
sed -n '1,60p' "business/_obsidian/tasks/starter-task.md"
```

Common queries:

```bash
rg -l '^\s*epic:.*Current dev' business/_obsidian/tasks
rg -l '^status: in-progress$' business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks | head -5
for s in in-progress ongoing to-be-resumed up-next backlog; do rg -l "^status: $s$" business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks; done | head -50
rg -l '^status: (idea|cogs-are-turning|draft|planning-scripting|scheduled)$' business/_obsidian/content/items personal-brand/_obsidian/content/items 2>/dev/null | head -50
```

If exact Obsidian Base drag order matters, check `tasknotes_manual_order` or use the Base in Obsidian.

Create routed TaskNotes task using existing names from inventory:

```bash
vault task create business "Task title" --project "Existing Project" --epic "Existing Epic" --status backlog --priority normal
```

Useful optional task flags: `--due YYYY-MM-DD`, `--scheduled YYYY-MM-DD`, `--time-estimate MINUTES`, `--body TEXT`, `--dry-run`.

Create missing routing objects:

```bash
vault project create business "New Project" --epic "Existing Epic" --status backlog
vault epic create business "New Epic" --status in-progress
vault folder --name 06-new-context --status active
```

After changing tasks/projects/epics/contexts, run `vault context` when agent-readable rollups should refresh.

## Google Calendar

Create specific calendar events on the default Google Calendar:

```bash
vault gcal create-event --title "Event title" --start "2026-06-02T19:30" --end "2026-06-02T20:30" --apply
```

Use `vault gcal create-event` for appointments, travel, meetings, reservations, and other concrete dated events. It writes to `primary` unless `--calendar` or `_master/system/config/calendar.json` says otherwise.

Use `vault gcal create-block` only when user explicitly asks for time blocking or broad planning blocks on `Time Blocks`.

## Skills

Active shared agent skills live in `_master/agents/skills`.
Dependency-projected active skill must use whole-directory symlink at `_master/agents/skills/<skill>`. Never use real directory containing symlinked `SKILL.md`; Codex omits that layout from skill catalog. Run `vault deps sync --apply`, then verify discovery in fresh Codex task because existing tasks cache catalog.
Manual-only skills live in `_master/agents/manual-skills` and are exposed as individual symlinks in `_master/agents/skills`, for example `_master/agents/skills/gws-gmail -> ../manual-skills/gws-gmail`. They must include `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.
GitHub-managed skills installed with `gh skill --dir` live in `_master/agents/gh-skills` and are exposed as individual symlinks in `_master/agents/skills`, for example `_master/agents/skills/skybridge -> ../gh-skills/skybridge`.
After adding a new manual-only skill, run `_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --dry-run`, then `_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --apply` to create the `_master/agents/skills/<skill> -> ../manual-skills/<skill>` symlink. Do not create manual-skill symlinks by hand.
After installing or updating a GitHub-managed skill, run the same sync script so Codex and Claude discover it.

Repo-local `.agents/skills` folders are real directories reserved for repo-scoped skills and should not be symlinked. Repo `.claude/skills` may symlink to `../.agents/skills` so Claude reads those same repo-scoped skills.

If user asks to create or update an active skill, work there.

If user asks to store a skill but not make it discoverable, use `_master/agents/skills-dump`.

After changing skills, run `vault context` only if agent-readable generated docs need refresh.

## Public Vault Export

If user says "publish the public vault", "release the public vault", or similar:

1. Finish requested source-vault changes first.
2. Run `vault release publish --dry-run --bump patch` and inspect the planned SemVer, dependency lock hash, and public repo actions.
3. Run `vault release publish --bump patch` unless the user requested `--bump minor`, `--bump major`, or `--version X.Y.Z`.
4. Confirm `~/Code/vault-public` is clean and the GitHub release/tag exists.

This updates `MDerman/the-context-vault-template` from the source vault export, bumps `_master/system/bootstrap/state/release.json`, snapshots `_master/system/config/dependencies.lock.json`, commits public export, tags `vX.Y.Z`, pushes, and creates a GitHub Release.

Use `vault bootstrap-export --force` only for local export inspection or exceptional manual repair. Public releases must use `vault release publish` so installed vaults can report installed and attempted upgrade versions.
