---
type: agent-reference
status: enabled
---
# Content Schedules

Generate current content schedule notes directly:

```bash
vault content
```

Content schedule notes live in `<context-folder>/_obsidian/content-schedules/` and normal refresh is create-only. `_obsidian/content/content-cadence.json` controls `schedule_format` and `publication_order`. The generator also keeps the `Current content schedule:` line in the context folder note.

Supported `schedule_format` values:

- `weekly`
- `weeklyThenByPublication`
- `publicationThenByWeek`

Regenerate an existing managed schedule note with:

```bash
vault content --context-folders personal-brand --date 2026-05-13 --force
```

Implementation script: `_master/system/scripts/content.py`.
