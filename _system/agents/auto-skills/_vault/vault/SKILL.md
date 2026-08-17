---
name: vault
description: Locate and use Matt Derman's personal Workspace vault containing tasks, projects, epics, library notes, Impression knowledge, personal brand material, and personal notes. Use when the user asks for vault context, Workspace notes, personal knowledge, Impression notes, task/project/epic routing, TaskNotes tasks, or Matt Derman-specific reference material.
---

# Vault

## Host Gate — Do This First

Before resolving `vault root` or reading any task-specific Vault file, identify the current operating system and workspace. If the host is Linux or the working directory is a non-iCloud/retired Vault clone, follow [[README-vault-host-boundary|Vault Host Boundary]] and stop. Do not inspect the requested note, message or create another task, hand off, wait, poll, use SSH, or act as a coordinator.

## Enter the Installed Vault

Resolve the installation through the dispatcher; never hard-code an iCloud or `~/Code` path:

```bash
cd "$(vault root)"
git config --local --get vault.machine-id 2>/dev/null || cat "$HOME/.config/vault/machine-id"
git config --local --get vault.checkout-mode 2>/dev/null || printf '%s\n' icloud-gitless
```

Read root `AGENTS.md` before task-specific Vault access. Vault work is supported only in the full iCloud Vault on a registered Mac. On a Gitless iCloud worker Mac, never run Vault Git or refresh; wait for iCloud upload and hand the final commit to the primary.

Then run `vault inventory` as the live routing source. It prints periods, default capture, context/source paths, task state, epics, and projects. Add `--json` when machine parsing helps.

## Low-Context Lookups

Use `rg` filename-first, then inspect only frontmatter/opening notes:

```bash
sed -n '1,60p' "business/_obsidian/tasks/starter-task.md"
```

Prefer inventory output and existing names over remembered examples. Useful focused queries:

```bash
rg -l '^status: in-progress$' */_obsidian/tasks 2>/dev/null | head -20
rg -l '^status: (idea|cogs-are-turning|draft|planning-scripting|scheduled)$' */_obsidian/content/items 2>/dev/null | head -20
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

Inventory reads tasks, projects, epics, and contexts live. Run `vault refresh --skip-gcal --skip-git-maintenance` only when Dashboard, schedules, or periodic views should regenerate.

Every completed Vault task reaches the primary Mac, where it stages, commits, and pushes the entire current worktree, including unrelated, incomplete, generated, and incidental `.obsidian` changes. Follow root `AGENTS.md` for media verification, final fetch/merge, and push commands. Do not report completion before the push succeeds or an exact blocker is identified.

## Google Calendar

Create specific calendar events on the default Google Calendar:

```bash
vault gcal create-event --title "Event title" --start "2026-06-02T19:30" --end "2026-06-02T20:30" --apply
```

Use `vault gcal create-event` for appointments, travel, meetings, reservations, and other concrete dated events. It writes to `primary` unless `--calendar` or `_system/local/calendar.json` says otherwise.

Use `vault gcal create-block` only when user explicitly asks for time blocking or broad planning blocks on `Time Blocks`.

## Skills

Implicit skills live under grouped `_system/agents/auto-skills`; explicit-only skills under grouped `_system/agents/manual-skills`; GitHub-managed installs under `_system/agents/gh-skills`.
`_system/agents/skills` is generated flat symlink-only catalog. Never install content there.
Organizer folders use `_lower-kebab` and may nest. Skill folder basename must match `SKILL.md` frontmatter name. Names must be globally unique.
Run `vault skills sync --dry-run`, then `vault skills sync --apply`. Sync enforces auto/manual invocation policy, updates moved dependency projections, rebuilds catalog, and maintains per-skill global links without importing discovery targets.
Use dependency type `auto-skill` or `manual-skill`. Run `vault deps sync --apply` after dependency repo changes.
Restart Codex or open new task after sync because current task caches catalog.

Repo-local `.agents/skills` folders are real directories reserved for repo-scoped skills and should not be symlinked. Repo `.claude/skills` may symlink to `../.agents/skills` so Claude reads those same repo-scoped skills.

If user asks to create/update implicit skill, work under `auto-skills`. If explicit-only, use `manual-skills`.

If user asks to store a skill but not make it discoverable, use `_system/agents/skills-dump`.

Skill changes do not require generated agent-context refresh; routing comes from source skills and live inventory.

## Public Vault Export

If user says "publish the public vault", "release the public vault", or similar:

1. Finish requested source-vault changes first.
2. Run `vault release publish --dry-run --bump patch` and inspect the planned SemVer, dependency lock hash, and public repo actions.
3. Run `vault release publish --bump patch` unless the user requested `--bump minor`, `--bump major`, or `--version X.Y.Z`.
4. Read `export_root` from `_system/bootstrap/bootstrap-export.json`; confirm resolved export repo is clean and GitHub release/tag exists.

This updates `MDerman/the-context-vault-template` from the source vault export, bumps `_system/bootstrap/release.json`, snapshots `_system/local/dependencies.lock.json`, commits public export, tags `vX.Y.Z`, pushes, and creates a GitHub Release.

Use `vault bootstrap-export --force` only for local export inspection or exceptional manual repair. Public releases must use `vault release publish` so installed vaults can report installed and attempted upgrade versions.
