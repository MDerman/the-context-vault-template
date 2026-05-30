---
type: agent-reference
status: enabled
---
# OBSIDIAN-PROFILE

This note holds Obsidian profile, plugin, and UI configuration details that should not crowd `AGENTS.md`.

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
_master/_obsidian/attachments/_inbox
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

Reuse existing palette IDs by preset name instead of hardcoding new colors. Root `_obsidian` folders and `_master` should use the Obsidian purple preset. `personal-brand/Youtube Factory` should use the YouTube red preset.

When creating a new context folder, add File Color entries for the new root folder and its `_obsidian` subtree because coloring the bootstrap template does not retarget copied paths automatically.

## Templater

Templater folder templates route note creation by folder path. Settings live at:

```text
.obsidian/plugins/templater-obsidian/data.json
```

Useful examples:

```md
<% tp.file.title %>
<% tp.date.now("YYYY-MM-DD") %>
<% tp.file.folder(true).split('/')[0] %>
```

Each context folder owns its local periodic templates:

```text
<context-folder>/_obsidian/templates/periodic/
```

Shared non-periodic templates live in:

```text
_master/_obsidian/templates/shared/
```

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

Master Bases live in:

```text
_master/_obsidian/bases/
```

Context folder Bases live in:

```text
<context-folder>/_obsidian/bases/
```

Content calendars use `calendar-bases` views over the `publish_date` property. Do not convert content notes into native Full Calendar event notes.

Content kanban uses `kanban-bases-view` through `content-kanban.base`; status columns are vertical lanes, and platform switching happens through separate Base views.

The old Markdown Kanban plugin is available but is not the `_obsidian/content` source of truth.

## Sync Embeds

Sync Embeds turns embedded notes into editable blocks. Older Obsidian-facing rollups and system notes may use this syntax:

````md
```sync
![[personal/_obsidian/periodic/daily/2026-05-10]]
```
````

Reference notes for the installed beta plugin live at:

```text
_master/system/obsidian_notes/beta_plugins_docs/README-sync-embeds.md
```

Agent periodic rollups under `_master/system/context` are generated as plain readable Markdown so agents do not need Obsidian plugin rendering.

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
