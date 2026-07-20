---
type: agent-reference
status: enabled
---
# Obsidian Profile

This note holds Obsidian profile, plugin, and UI configuration details that should not crowd `AGENTS.md`.

Companion references:

- [[obsidian-plugins-reference]]: installed/core plugins and configured workflows.
- [[obsidian-keyboard-shortcuts]]: current hotkeys.
- [[obsidian-core-features]]: non-plugin fundamentals.
- [[obsidian-settings-and-examples]]: recommended settings and Markdown examples.

## Root Profile

Root `.obsidian` is the only active Obsidian profile. Context folders do not have their own active profiles.

After changing root Obsidian settings or installing plugins, root `.obsidian` itself is the source of truth. Bootstrap does not copy or patch Obsidian profile settings.

## Mobile Profile

Mobile uses its own Obsidian config folder:

```text
.obsidian-mobile
```

On iPhone, set `Settings → Files and links → Override config folder` to `.obsidian-mobile`. This prevents desktop plugin state from re-enabling mobile-hostile plugins.

Refresh the mobile profile from the root desktop profile with:

```bash
vault mobile-profile
```

The mobile profile enables only TaskNotes, Calendar, Periodic Notes, Sync Embeds, Style Settings, File Color, and Iconize. It copies the current theme, enabled CSS snippets, those plugin folders/settings, and key core settings such as `daily-notes.json` from `.obsidian` into `.obsidian-mobile`.

## Attachments

Obsidian's built-in attachment destination is the temporary inbox:

```text
_system/_obsidian/attachments/_inbox
```

The vault convention is different from Obsidian's built-in routing: note attachments should live under the top-level root folder that owns the note:

```text
<root-folder>/_obsidian/attachments/
```

Use the standardization script to dry-run, apply, or verify routing:

```bash
vault attachments
vault attachments --apply
vault attachments --verify-only
```

## Git LFS

This vault uses Git LFS for media, design files, presentations, PDFs, archives, and common image formats including PNG, JPEG, GIF, WebP, HEIC, and raw camera files. New clones should run:

```bash
git lfs install
git lfs pull
```

Remote Git history is not rewritten by normal local maintenance. Use `vault git-maintenance --depth 1` only for local shallow pruning unless a deliberate remote force-rewrite is planned.

## File Colors And Icons

Iconize file/folder icons live in:

```text
.obsidian/plugins/obsidian-icon-folder/data.json
```

File Color folder colors live in:

```text
.obsidian/plugins/obsidian-file-color/data.json
```

For File Color, `palette` stores named color presets and `fileColors` stores vault-relative path assignments:

```json
{ "path": "personal-brand/Youtube Factory", "color": "<palette-id>" }
```

Reuse existing palette IDs by preset name instead of hardcoding new colors. Root `_obsidian` folders and `_system` should use the Obsidian purple preset. `personal-brand/Youtube Factory` should use the YouTube red preset.

When creating a new context folder, add File Color entries for the new root folder and its `_obsidian` subtree because coloring the bootstrap template does not retarget copied paths automatically.

## Templater

Templater folder templates route note creation by folder path. Settings live at:

```text
.obsidian/plugins/templater-obsidian/data.json
```

Useful examples:

```md
README-obsidian-profile
2026-07-08
_system
```

Each context folder owns its local periodic templates:

```text
<context-folder>/_obsidian/templates/periodic/
```

Shared non-periodic templates live in:

```text
_system/_obsidian/templates/shared/
```

Folder rules:

- `<context-folder>/_obsidian/periodic/daily` → local `daily-template.md`
- `<context-folder>/_obsidian/periodic/weekly` → local `weekly-template.md`
- `<context-folder>/_obsidian/periodic/monthly` → local `monthly-template.md`
- `<context-folder>/_obsidian/periodic/quarterly` → local `quarterly-template.md`
- `<context-folder>/_obsidian/periodic/yearly` → local `yearly-template.md`
- `<context-folder>/_obsidian/tasks` → `_system/_obsidian/templates/shared/default-tasks-template.md`

Periodic templates may include `{{current_content_schedule_sync_embed}}`; periodic generator replaces it with active four-week schedule embed when content cadence is enabled.

Shared entity-note templates live under `_system/_obsidian/templates/shared/entity-notes/` and are copied/adapted into context control notes. Vault rollups under `_system/_obsidian/periodic/` are script-owned and have no manual Templater rules.

## File Explorer Note Creation

Folder New Note Button adds a hover `+` button beside folders in the File Explorer. Click it to create a new note directly inside that folder.

Simple Folder Note treats a note with the same name as its folder as that folder's index note and opens it when the folder is clicked.

Installed plugin IDs:

```text
folder-new-note-button
simple-folder-note
```

`create-note-in-folder` is intentionally not installed.

## Bases, Calendars, And Kanban

Bases are dashboards over files and properties.

Vault-wide Bases live in:

```text
_system/_obsidian/bases/
```

Context folder Bases live in:

```text
<context-folder>/_obsidian/bases/
```

Content calendars use `calendar-bases` views over the `publish_date` property. Do not convert content notes into native Full Calendar event notes.

Content kanban uses `kanban-bases-view` through `content-kanban.base`; status columns are vertical lanes, and platform switching happens through separate Base views.

The old Markdown Kanban plugin is available but is not the `_obsidian/content` source of truth.

Task/project/epic Base inventory and grouping rules: [[_system/docs/commands/Tasks And Projects#Bases|Tasks And Projects]]. Content schemas/views: [[_system/docs/commands/Content Schedules#Views|Content System And Schedules]].

## Search And File Actions

Omnisearch (`omnisearch`) is preferred relevance-ranked search. Doubleshift (`obsidian-doubleshift`) maps double-tapping left Shift to Omnisearch vault search.

Primary shortcuts:

- `Shift` then `Shift`: Omnisearch vault search.
- `Cmd+Shift+F`: vault-search fallback.
- `Cmd+F`: Omnisearch in-file search for Markdown.
- `Cmd+Shift+P`: core Global Search.
- `Tab` from vault result: inspect matches within selected note.
- `Alt+T`: TaskNotes new task.
- `Alt+Cmd+T`: TaskNotes new task with selected Markdown in details.
- `Alt+Cmd+Y`: append selection to existing TaskNotes task and route selected attachments.
- `Cmd+Backspace`: delete hovered/selected file with normal confirmation.
- `Alt+Cmd+Backspace`: deliberate current-file delete.
- `Cmd+N`: create note in hovered File Explorer folder, else normal new-note behavior.

Omnisearch filters:

- `path:"somepath"`: path restriction.
- `ext:"png jpg"`, `ext:png`, or `.png`: extension restriction.
- `"exact expression"`: exact filter.
- `-exclusion`: remove notes containing term.

PDF, Office, and image indexing needs Text Extractor; extra indexing modes are currently disabled.

## Excalidraw

Shared Excalidraw folder and script source:

```text
_system/_obsidian/excalidraw/
_system/_obsidian/excalidraw/Scripts/
```

Bootstrap copies script folder into `<context-folder>/_obsidian/excalidraw/Scripts/`. Context Nine points at shared folder; context-owned drawings live in local `_obsidian/excalidraw/`.

## Sync Embeds

Sync Embeds turns embedded notes into editable blocks. Older Obsidian-facing rollups and system notes may use this syntax:

````md
```sync
![[personal/_obsidian/periodic/daily/2026-05-10]]
```
````

Reference notes for the installed beta plugin live at:

```text
_system/docs/obsidian/beta_plugins_docs/README-sync-embeds.md
```

Vault periodic rollups under `_system/_obsidian/periodic/` use Sync Embeds. Agents should inspect live routing with `vault inventory`, then open relevant context source notes.

### Test Public Sync Embeds Against Local Patch

Use this when checking whether public Sync Embeds still has a local patch bug, then restoring the patched build.

Plugin id:

```text
sync-embeds
```

Local patch repo:

```text
~/Code/open_source/sync-embeds
```

Install latest public release into this vault:

```bash
VAULT="$(vault root)"
PLUGIN="$VAULT/.obsidian/plugins/sync-embeds"
PATCH_BACKUP="$VAULT/.obsidian/plugins/sync-embeds.patched.$(date +%Y%m%d-%H%M%S)"

osascript -e 'quit app "Obsidian"'
cp -a "$PLUGIN" "$PATCH_BACKUP"

curl -L -o "$PLUGIN/main.js" https://github.com/uthvah/sync-embeds/releases/latest/download/main.js
curl -L -o "$PLUGIN/manifest.json" https://github.com/uthvah/sync-embeds/releases/latest/download/manifest.json
curl -L -o "$PLUGIN/styles.css" https://github.com/uthvah/sync-embeds/releases/latest/download/styles.css

open -a Obsidian
```

Minimal section-embed bug check:

````md
# Before
before content

# Target
first target line
second target line

# After
after content
````

Embed target:

````md
```sync
![[Bug Source#Target]]
```
````

Bug still exists if `first target line` is clipped, or `# After` appears inside the embed.

Restore patched local build:

```bash
REPO="~/Code/open_source/sync-embeds"
VAULT="$(vault root)"
PLUGIN="$VAULT/.obsidian/plugins/sync-embeds"

osascript -e 'quit app "Obsidian"'

cd "$REPO"
npm run build

cp main.js manifest.json styles.css "$PLUGIN/"

open -a Obsidian
```

Fast rollback if build is unnecessary:

```bash
osascript -e 'quit app "Obsidian"'
rm -rf "$PLUGIN"
cp -a "$PATCH_BACKUP" "$PLUGIN"
open -a Obsidian
```
