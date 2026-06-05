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

Implementation scripts: `_master/system/scripts/task.py`, `_master/system/scripts/project.py`.
