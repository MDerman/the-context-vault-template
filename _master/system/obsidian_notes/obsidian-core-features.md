# Obsidian Core Features

This note covers the built-in Obsidian ideas a new user should understand before worrying about extra plugins.

## Notes, Links, And Search

- Use `[[Note Name]]` to create a wikilink. Start typing after `[[` and Obsidian will autocomplete existing notes.
- If the note does not exist yet, pressing `Enter` on the autocomplete result creates it and links the current note to it.
- Use `[[Note Name#Heading]]` to link to a heading inside a note.
- Use `[[Note Name^block-id]]` to link to a specific block. Use display text with a pipe, for example `[[Note Name#Heading|friendly label]]`.
- Use `![[Note Name]]` to transclude another note into the current note.
- Use Quick Switcher (`Cmd+O`) to find or create notes quickly.
- Use core Global Search (`Cmd+Shift+P`) when you need built-in search syntax. `Cmd+Shift+F` is configured for Omnisearch Vault search.

## Markdown Basics

Obsidian files are plain Markdown, so the content remains portable.

```md
**bold**
*italic*
[external link](https://example.com)
[[Internal Link]]
![[local-image.png]]

1. Numbered item
2. Numbered item

- Bullet item
- Bullet item

> Block quote

# Heading 1
## Heading 2
### Heading 3

`inline code`

%% hidden comment %%
```

Useful writing shortcuts:

- `Cmd+B`: bold selected text.
- `Cmd+I`: italicize selected text.
- `Cmd+K`: turn selected text into a link.
- `Cmd+Enter`: create or toggle a basic Markdown task checkbox.
- `Option+Click`: add another cursor for multi-cursor editing.

## Tags, Properties, And Aliases

- Use `#tag` in note text for local tags.
- Use frontmatter/properties at the top of a note for file-level metadata.
- Use nested tags like `#journal/win` when the tag needs hierarchy.
- Add aliases when a note should be found by multiple names.

```md
---
aliases:
  - Alternate Name
tags:
  - reference
  - obsidian
publish_date: 2026-05-11
---
```

`Cmd+:` opens the property flow for adding a property in the active note.

## Tasks

Obsidian supports simple Markdown tasks without a plugin:

```md
- [ ] Follow up on this
- [x] Already done
```

This vault uses TaskNotes for serious task management, so use basic Markdown tasks for quick checklists and TaskNotes for dated, contextual, tracked work. See [[obsidian-plugins-reference]].

## Callouts

Callouts make important sections easier to scan.

```md
> [!note]
> General note.

> [!tip]
> Useful suggestion.

> [!warning]
> Risk or caution.

> [!success]
> Completed or positive outcome.
```

Common callout types:

- `note`, `abstract`, `summary`, `tldr`
- `info`, `todo`
- `tip`, `hint`, `important`
- `success`, `check`, `done`
- `question`, `help`, `faq`
- `warning`, `caution`, `attention`
- `failure`, `fail`, `missing`
- `danger`, `error`, `bug`
- `example`
- `quote`, `cite`

Make a callout foldable with `+` or `-` after the type:

```md
> [!info]+ Expanded by default
> Content here.

> [!info]- Collapsed by default
> Content here.
```

## Files, Attachments, And Exports

- Drag an image or file into a note to attach it and create the embed/link automatically.
- The root vault attachment folder is configured as the temporary inbox `_master/_obsidian/attachments/_inbox`.
- The vault convention is to route note attachments to the owning top-level folder's `_obsidian/attachments` directory, such as `_library/_obsidian/attachments`.
- Export a note through the note menu with `Export to PDF`.
- Use `Copy Obsidian URL` from the note menu when another app needs to link directly back to a note.

## Tabs, Graphs, And Navigation

- `Cmd+Click` a wikilink to open it in a new tab.
- Pin important tabs from the note menu so new notes do not replace them.
- Reopen a recently closed tab with `Cmd+Shift+T`.
- Use Graph View for the whole vault and Local Graph for the current note's immediate connections.
- Drag Local Graph, Backlinks, Tags, or Outline panes into sidebars when you want them always visible.
