# Obsidian Settings And Examples

This note combines recommended Obsidian settings with quick Markdown and callout examples.

## Recommended Settings

### General

| Setting | Recommended |
| --- | --- |
| Automatic updates | Off |
| Receive early access versions | On |
| Notify if startup takes longer than expected | On |

### Editor

| Setting | Recommended |
| --- | --- |
| Always focus new tabs | On |
| Default view for new tab | Editing view |
| Default editing mode | Live Preview |
| Show editing mode in status bar | On |
| Readable line length | On |
| Strict line breaks | Off |
| Properties in document | On |
| Fold heading | On |
| Fold indent | On |
| Show line number | Off |
| Show indentation guides | On |
| Right-to-left | Off |
| Spellcheck | On |
| Auto pair brackets | On |
| Auto pair Markdown syntax | On |
| Smart indent lists | On |
| Indent using tabs | On |
| Indent visual width | Default, 4 |
| Auto convert pasted HTML to Markdown | On |
| Vim key bindings | Off |

### Files And Links

| Setting | Recommended |
| --- | --- |
| Default location for new notes | Vault folder/current folder, depending on context |
| Default location for new attachments | `_master/_obsidian/attachments/_inbox` as the temporary paste inbox |
| New link format | Shortest path when possible |
| Use wikilinks | On |
| Show all file types | Off |
| Confirm file deletion | On |
| Deleted files | Move to system trash |
| Allow URI callbacks | On |

Current root `.obsidian/app.json` uses:

```json
{
  "promptDelete": false,
  "attachmentFolderPath": "_master/_obsidian/attachments/_inbox",
  "alwaysUpdateLinks": true,
  "newFileLocation": "current"
}
```

### Appearance

| Setting | Recommended |
| --- | --- |
| Base color scheme | Dark |
| Font size | Default, 16 |
| Quick font size adjustment | Off |
| Show inline title | On |
| Show tab title bar | On |
| Show ribbon | On |
| Zoom level | Default, 100% |
| Native menus | On |
| Window frame style | Hidden |
| Translucent window | Off |
| Hardware acceleration | On |

## Markdown Examples

````md
**bold**
*italic*

[External link](https://example.com)
[[Internal note link]]
[[Internal note link|Custom display text]]
![[Embedded note or image]]

1. First
2. Second
3. Third

- Bullet
- Bullet

> Block quote

# Heading 1
## Heading 2
### Heading 3

`inline code`

%% hidden comment %%

```
code block
```
````

## Property Examples

```md
---
aliases:
  - Alternate Name
tags:
  - obsidian
  - reference
publish_date: 2026-05-11
status: active
---
```

## Callout Examples

```md
> [!note]
> Note.

> [!abstract]
> Abstract, summary, or TLDR.

> [!info]
> Information.

> [!todo]
> Action item.

> [!tip]
> Tip, hint, or important note.

> [!success]
> Success, check, or done.

> [!question]
> Question, help, or FAQ.

> [!warning]
> Warning, caution, or attention.

> [!failure]
> Failure, fail, or missing.

> [!danger]
> Danger or error.

> [!bug]
> Bug.

> [!example]
> Example.

> [!quote]
> Quote or cite.
```

Foldable callouts:

```md
> [!info]+ Open by default
> This starts expanded.

> [!info]- Closed by default
> This starts collapsed.
```
