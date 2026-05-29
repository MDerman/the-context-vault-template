---
type: plugin-ideas
status: seed
---
# FUTURE_PLUGIN_IDEAS

This note collects future local Obsidian plugin ideas for this workspace.

## Attachment Router

Problem: Obsidian's built-in attachment setting cannot route pasted files to the top-level root folder that owns the current note. The current workaround is to paste into `master/_obsidian/attachments/_inbox` and periodically run:

```bash
python3 master/system/scripts/attachments.py --apply
```

Desired behavior:

- When an image or file is pasted/dropped into a note, detect the active Markdown note.
- Determine the note's top-level root folder, such as `library`, `master`, `01-personal`, `02-personal-brand`, `03-business`, or `wiki`.
- Move the new attachment from the inbox to `<root-folder>/_obsidian/attachments/`.
- Rewrite the inserted embed/link in the note to point at the final attachment path.
- Preserve normal Obsidian embeds, preferably as `![[<root-folder>/_obsidian/attachments/<filename>]]`.
- Handle filename conflicts by reusing identical files or adding a suffix such as ` (2)`.
- Ignore generated reports, quarantined cleanup files, Apple Notes import attachments, and any manually managed media libraries.

Minimum plugin shape:

- Watch `master/_obsidian/attachments/_inbox` for new files.
- Use the active file or recent file-change context to identify the note that received the pasted link.
- Route only when the active note belongs to a known top-level root folder.
- Fail softly: if the active note cannot be determined, leave the file in the inbox for `attachments.py` to clean up later.
- Provide one command: `Route attachment inbox now`.

Open design questions:

- Whether future new pasted attachments should be flat under `<root-folder>/_obsidian/attachments/` or organized into date/note folders.
- Whether the plugin should rewrite to absolute vault paths or shortest Obsidian paths.
- Whether the plugin should also expose a command to route all existing inbox files, or leave batch cleanup to `attachments.py`.
