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
content_enabled: false
default_capture: true
---
```

- `status: active`: included in default rollups.
- `status: archived`: retained but excluded from default rollups.
- blank/missing status: not active.
- `content_enabled: true`: scaffolds content storage, cadence config, schedules, and views.
- `default_capture: true`: preferred unspecific capture destination; fallback is first active folder.

Context note also holds local routing and entity operating sections. Headings such as `Identity`, `Momentum`, and personal-brand `Social Selling` are optional human organization. Generators do not extract or duplicate heading content.

## Structure

```text
<context-folder>/
  <context-folder>.md
  _obsidian/
    attachments/
    bases/
    content/            # content-enabled only
    content-schedules/  # content-enabled only
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

Use `--content-enabled` when the context folder should have `_obsidian/content` infrastructure.

Creation writes control note, creates operating structure and local templates/shared-template links, then refreshes discovered context wiring.

Use `status: archived` for inactive-but-kept folders. Rename through `vault folder` command so structured path/context references update together.

Implementation script: `_system/commands/folder.py`.
