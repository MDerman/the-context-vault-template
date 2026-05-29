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

## Skills

Active shared agent skills live in `_master/agents/skills`, symlinked to `.agents/skills`.

If user asks to create or update an active skill, work there.

If user asks to store a skill but not make it active, use `_master/agents/skills-dump`.

After changing skills, run `vault context` only if agent-readable generated docs need refresh.

## Public Vault Export

If user says "export the public vault", "publish the public vault", or similar:

1. Finish requested source-vault changes first.
2. Run `vault bootstrap-export --force`.
3. `cd ~/Code/vault-public`.
4. Inspect `git status` and diff for secrets, local config, accidental backups, or unrelated files.
5. Commit all intended public export changes with a relevant message.
6. Push the public repo remote.

This updates `MDerman/the-context-vault-template` from the source vault export.
