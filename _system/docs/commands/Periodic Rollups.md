---
type: agent-reference
status: enabled
---
# Periodic Rollups

## Source Notes

Context folder periodic notes are editable source of truth:

```text
<context-folder>/_obsidian/periodic/daily/YYYY-MM-DD.md
<context-folder>/_obsidian/periodic/weekly/YYYY-Www.md
<context-folder>/_obsidian/periodic/monthly/YYYY-MM.md
<context-folder>/_obsidian/periodic/quarterly/YYYY-Qn.md
<context-folder>/_obsidian/periodic/yearly/YYYY.md
```

Root Periodic Notes defaults to `personal`. Opening today's daily note creates or opens `personal/_obsidian/periodic/daily/YYYY-MM-DD.md`.

Missing source notes are created from each context folder's local `_obsidian/templates/periodic/<period>-template.md`. `personal` has filled starter templates; other folders may intentionally use blank templates.

## Generated Rollups

Vault rollups use Sync Embeds and live under:

```text
_system/_obsidian/periodic/<period>/<period-id>.md
```

Context source notes remain editable. Generated vault rollups are read-only derived views. Dashboard links current daily, weekly, monthly, quarterly, and yearly vault rollups.

## Generate

Generate current source notes and vault periodic rollups:

```bash
vault periodic
```

Useful variants:

```bash
vault periodic --all
vault periodic --context-folders dev,claudeche
```

Context folder periodic notes remain editable source of truth. Vault rollups live under `_system/_obsidian/periodic/<period>/` and use Sync Embeds. `vault refresh` calls periodic generator automatically.

Dashboard unfinished monthly-SOP reminders inspect source monthly notes directly, using historic vault monthly rollups as period indexes. No copied agent-periodic notes are generated.

Periodic templates may include `{{current_content_schedule_sync_embed}}`. Generator replaces it with Sync Embed pointing at active four-week content schedule when context has enabled cadence config.

Implementation script: `_system/commands/periodic.py`.
