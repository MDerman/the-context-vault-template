---
type: agent-reference
status: enabled
---
# Tasks And Projects

Create a TaskNotes task with validated existing project/epic links:

```bash
vault task create business "Follow up with partner" --project "Partnerships" --epic "Growth" --status up-next
```

Create a project note:

```bash
vault project create business "New Project" --epic "Growth" --status backlog
```

Use `vault inventory` first so task links use actual project and epic names. Use `vault task create --help` and `vault project create --help` for optional `due`, `scheduled`, `timeEstimate`, and dry-run flags.

## Low-Context Searches

Use `vault inventory` first. Then use `rg` filename-first and inspect opening lines only:

```bash
sed -n '1,60p' "business/_obsidian/tasks/starter-task.md"
```

Common queries:

```bash
rg -l '^\s*epic:.*Current dev' business/_obsidian/tasks
rg -l '^status: in-progress$' business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks | head -5
for s in in-progress ongoing to-be-resumed up-next backlog; do rg -l "^status: $s$" business/_obsidian/tasks personal-brand/_obsidian/tasks personal/_obsidian/tasks; done | head -50
```

If exact Obsidian Base order matters, check `tasknotes_manual_order` or use Obsidian.

Implementation scripts: `_master/system/scripts/task.py`, `_master/system/scripts/project.py`.
