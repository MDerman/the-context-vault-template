---
type: agent-reference
status: enabled
---
# Content System And Schedules

Content-enabled context folders store owned content under `_obsidian/content`. This includes items, ideas, publication definitions, drafts, and planning state. Executable work about content belongs in `_obsidian/tasks`, not content storage.

## Structure

```text
<context-folder>/_obsidian/content/
  content-cadence.json
  publications/
    blogs/
    newsletters/
    youtube/
  items/
    blog-posts/
    newsletter-issues/
    youtube-videos/
    social-posts/
  ideas/
  archive/
<context-folder>/_obsidian/content-schedules/
```

## Schemas

Content item:

```yaml
---
type: content
entity: personal-brand
content_kind: blog-post
platform: blog
publication: personal-brand
status: idea
publish_date:
source:
repurposed_from:
cta:
conversion_goal:
---
```

Publication:

```yaml
---
type: publication
entity: personal-brand
publication_type: newsletter
publication_id: copy-and-context
name: Copy and Context
status: active
primary_cta:
---
```

## Views

Vault rollups:

```text
_system/_obsidian/bases/content-calendar.base
_system/_obsidian/bases/content-kanban.base
```

Context views:

```text
<context-folder>/_obsidian/bases/content-dashboard.base
<context-folder>/_obsidian/bases/content-queue.base
<context-folder>/_obsidian/bases/content-calendar.base
<context-folder>/_obsidian/bases/content-kanban.base
```

Calendar views use `publish_date`; dragging item updates that property. Kanban views group by `status` with platform-specific views for Blog, Newsletter, YouTube, LinkedIn, X, Substack, and broad Social items. Content state remains note frontmatter, not Markdown Kanban files or Full Calendar event-note schema.

## Schedule Generation

Generate current content schedule notes directly:

```bash
vault content
```

`vault refresh` runs content generation automatically before periodic generation so periodic templates can embed current schedule.

Content schedule notes live in `<context-folder>/_obsidian/content-schedules/` and normal refresh is create-only. `_obsidian/content/content-cadence.json` controls `schedule_format` and `publication_order`. The generator also keeps the `Current content schedule:` line in the context folder note.

Supported `schedule_format` values:

- `weekly`
- `weeklyThenByPublication`
- `publicationThenByWeek`

`publicationThenByWeek` is default. `publication_order` controls publication heading order. Schedule window is fixed four weeks.

Regenerate an existing managed schedule note with:

```bash
vault content --context-folders personal-brand --date 2026-05-13 --force
```

Implementation script: `_system/commands/content.py`.
