---
type: agent-reference
status: enabled
---
# Context Folders

Context folders are source-of-truth operating workspaces inside root Obsidian vault. They are not standalone vaults and do not own separate Obsidian profiles or agent symlinks.

Use current generated inventory instead of hardcoded folder lists:

```bash
vault inventory
```

## Control Note

Each folder owns `<context-folder>/<context-folder>.md`. Frontmatter controls discovery and generation:

```yaml
---
status: active
content_schedules_enabled: true
default_capture: true
---
```

- `status: active`: included in default rollups.
- `status: archived`: retained but excluded from default rollups.
- blank/missing status: not active.
- Blog, social-content, and newsletter support is inferred from their capability folders.
- `content_schedules_enabled: true`: participates in cadence and schedule refresh. Omit it otherwise.
- `default_capture: true`: preferred unspecific capture destination; fallback is first active folder.

Context note also holds local routing and entity operating sections. Headings such as `Identity`, `Momentum`, and personal-brand `Social Selling` are optional human organization. Generators do not extract or duplicate heading content.

## Structure

```text
<context-folder>/
  <context-folder>.md
  _obsidian/
    attachments/
    bases/
    content/            # selected capabilities only
    content-schedules/  # schedule-enabled only
    epics/
    excalidraw/
    periodic/
      daily/
      weekly/
      monthly/
      quarterly/
      yearly/
    projects/
    tasks/
    templates/periodic/
  <ordinary context-specific folders>
```

Operating folders use `_obsidian` so ordinary context-specific folders remain visually distinct. No default `notes` folder.

Context folders hold current docs, assets, tasks, periodic notes, SOPs, internal training, decisions, and active references. Samples, downloaded templates, course notes, and research dumps belong in `_library`; reusable synthesis belongs in `_wiki`.

## Create And Register

Create/register a new context folder:

```bash
vault folder -n new-context-folder -s active
vault folder -n new-context-folder -s archived
```

Creation is core-first. Add only the capabilities needed:

```bash
vault folder -n publication -s active --blog
vault folder -n creator -s active --blog --social-content --newsletters
vault folder -n creator -s active --content-schedules
vault folder -n creator -s active --folder-template personal-brand
vault folder -n studio -s active --folder-template business
```

- `--blog` creates blog item and publication folders.
- `--social-content` creates social posts, YouTube, ideas, and archive folders.
- `--newsletters` creates newsletter item and publication folders.
- `--content-schedules` creates cadence/schedule infrastructure and persists schedule participation.
- `--folder-template personal-brand|business` applies one physical pack during new-context creation only.

Content flags may be added while registering an existing context. A folder template cannot: it is a creation-time seed and its name is never persisted.

Creation writes control note, creates operating structure and local templates/shared-template links, then refreshes discovered context wiring.

Physical packs are directly browsable under `_system/bootstrap/templates/context-folders/`. They do not define a context type. The `personal-brand` pack seeds `brand`, `audience`, `offers`, `products`, `writing`, `media`, and `relationships`; the `business` pack seeds the established operating scaffold and configures its managed toolkit.

`--context-type` and `--content-enabled` were removed. Use the independent capability, schedule, and folder-template options above.

Use `status: archived` for inactive-but-kept folders. Rename through `vault folder` command so structured path/context references update together.

Implementation script: `_system/commands/folder.py`.
