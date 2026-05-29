# Obsidian Keyboard Shortcuts

Notation: `Cmd` means the macOS Command key. `Mod` in Obsidian settings maps to `Cmd` on macOS.

## Current Custom Hotkeys

These come from `.obsidian/hotkeys.json` and are the source-of-truth custom bindings for this vault.

| Shortcut | Command | Notes |
| --- | --- | --- |
| `Ctrl+-` | Go back | Replaces the older `Cmd+Option+Left` habit. |
| `Ctrl+Shift+-` | Go forward | Pair with `Ctrl+-` for browser-like navigation. |
| `Alt+T` | TaskNotes: create new task | Plain task capture shortcut. Binding this prevents macOS from inserting `†`. |
| `Alt+Cmd+T` | Obsidian Master Plugin: capture selection to new TaskNotes task | Opens the native TaskNotes create dialog. If Markdown is selected, the selection is added to task details on save; with no selection, it behaves like normal TaskNotes new task. |
| `Alt+Cmd+Y` | Obsidian Master Plugin: append selection to existing TaskNotes task | Pick an existing task and append the selected block under `## Captures`. |
| `Alt+R` | Templater: replace templates in active file | Useful for previewing or applying template syntax. |
| `Cmd+Backspace` | Obsidian Master Plugin: delete hovered or selected file | Uses Obsidian's normal delete confirmation and trash behavior. Does not fall back to deleting the active note. |
| `Alt+Cmd+Backspace` | Obsidian: delete current file | Deliberate current-note delete shortcut, using Obsidian's native confirmation flow. |
| `Cmd+N` | Obsidian Master Plugin: new note in hovered folder | When hovering a folder in the file explorer, creates the note there; otherwise falls back to Obsidian's normal new note command. |
| `Cmd+1` | File Explorer: open | Focuses the left file tree. |
| `Cmd+2` | Obsidian Master Plugin: focus first main pane | Main editor pane 1 in the left/main/right navigation cluster. |
| `Cmd+3` | Obsidian Master Plugin: focus second main pane | Main editor pane 2; creates a second vertical pane if needed. |
| `Cmd+4` | Obsidian Master Plugin: focus right sidebar | Expands and focuses the right sidebar. |
| `Alt+Up` | Move line up | Editor line movement. |
| `Alt+Down` | Move line down | Editor line movement. |
| `Ctrl+D` | Delete line | From Code Editor Shortcuts. |
| `Cmd+F` | Omnisearch: In-file search | Search inside the active Markdown note and jump to a match. |
| `Shift then Shift` | Omnisearch: Vault search | Doubleshift double-tap shortcut for fast vault search. |
| `Cmd+Shift+F` | Omnisearch: Vault search | Fallback fast vault search hotkey. |
| `Cmd+Shift+P` | Global search | Core Global Search remains available here. |
| `Ctrl+Alt+Cmd+5` | Workspaces: open modal | Load or manage saved layouts. |

## Essential Daily Hotkeys

| Shortcut | Action |
| --- | --- |
| `Cmd+O` | Quick Switcher: find or create a note. |
| `Cmd+P` | Command Palette: run any command and rediscover hotkeys. |
| `Cmd+N` | New note; when hovering a folder in the file explorer, create it in that folder. |
| `Cmd+1` | Focus the File Explorer in the left sidebar. |
| `Cmd+2` | Focus the first main editor pane. |
| `Cmd+3` | Focus the second main editor pane, creating it if needed. |
| `Cmd+4` | Focus the right sidebar. |
| `Cmd+F` | Omnisearch In-file search inside the current Markdown note. |
| `Shift then Shift` | Omnisearch Vault search across the vault. |
| `Cmd+Shift+F` | Omnisearch Vault search fallback. |
| `Cmd+Shift+P` | Core Global Search across the vault. |
| `Cmd+E` | Toggle edit/reading view. |
| `Cmd+B` | Bold selected text. |
| `Cmd+I` | Italicize selected text. |
| `Cmd+K` | Create link from selected text. |
| `Cmd+Enter` | Create or toggle a Markdown task checkbox. |
| `Alt+T` | Open the TaskNotes new task dialog. |
| `Cmd+Shift+T` | Reopen the last closed tab. |
| `Cmd+W` | Close current tab. |
| `Alt+Cmd+Backspace` | Delete the current open file with Obsidian's normal confirmation. |
| `Cmd+Shift+W` | Good candidate for close all other tabs, if configured. |
| `Cmd+G` | Open Graph View. |

## Tab Opening Behavior

Open Tab Settings changes default note-opening behavior without adding a new hotkey.

- Normal note opens create a new tab after the active tab instead of replacing the current tab.
- If the note is already open, Obsidian switches to the existing tab instead of opening a duplicate.
- Duplicate prevention applies across tab groups, split panes, and popup windows.
- In split workspaces, normal new tabs prefer the same tab group.
- `Cmd+Click` and middle-click remain explicit new-tab gestures, but they prefer the opposite tab group when possible and may open in the background.

## Mouse And Modifier Workflows

- Click a note or wikilink normally to open it in a new tab instead of replacing the current tab.
- `Cmd+Click` a wikilink to explicitly open the note in a new tab, preferring the opposite tab group when possible.
- Middle-click a note or wikilink to explicitly open it in a new tab, also preferring the opposite tab group when possible.
- `Option+Click` inside a note to add another cursor.
- `Shift+Click` Focus Mode's button to focus only the active tab, if Focus Mode is enabled.
- Right-click a TaskNotes task to start time tracking.
- Right-click a file explorer item or a Bases kanban card to get the Obsidian Master Plugin delete action.
- Hover a Bases kanban card or file explorer item and press `Cmd+Backspace` to delete it with Obsidian's normal confirmation. Use `Alt+Cmd+Backspace` when you intentionally want to delete the current open note instead.

## TaskNotes Shortcuts And Input

| Shortcut or Syntax | Action |
| --- | --- |
| `Alt+T` | Open the native TaskNotes new task dialog. |
| `Alt+Cmd+T` | Open the native TaskNotes new task dialog, with selected Markdown injected into details on save. |
| `Alt+Cmd+Y` | Append the selected Markdown block to an existing TaskNotes task. |
| `#tag` | Add an Obsidian tag in TaskNotes natural-language input. |
| `@business` | Set task context and route it to that context folder's `_obsidian/tasks` folder. |
| `+project` or `+[[Project Name]]` | Link a project. Use sparingly; contexts and tags are preferred here. |
| `$backlog`, `$up-next`, `$to-be-resumed`, `$ongoing`, `$in-progress`, `$done` | Set task status from TaskNotes natural-language input. |
| `$` | Status trigger in TaskNotes NLP. This replaces the older `*` status trigger. |
| `!high`, `!normal`, `!low`, `!none` | Set task priority from TaskNotes natural-language input. |
| `!important` | Priority alias added by Obsidian Master Plugin; creates priority `high`. |
| Epic picker | In TaskNotes create/edit modals, choose from `_obsidian/epics` instead of typing the epic link manually. |
| `tomorrow`, `next Friday`, `January 15 at 3pm` | Date/time parsing. |
| `2h`, `30min`, `1h30m` | Time estimates. |
| `daily`, `weekly`, `every Monday` | Recurrence parsing. |

Tasks should usually use contexts first and tags as sub-project/grouping labels.

## Daily Notes And Navigation

- Use Calendar/Periodic Notes to jump by date from the sidebar.
- Configure `Daily Notes: open next daily note`, `Daily Notes: open previous daily note`, and `Daily Notes: open today's daily note` if you want dedicated date-navigation hotkeys.
- Current general back/forward navigation is `Ctrl+-` and `Ctrl+Shift+-`.

## Search Workflow

- `Shift then Shift` opens `Omnisearch: Vault search`, the preferred fast search for finding notes by relevance.
- `Cmd+Shift+F` also opens `Omnisearch: Vault search` as a normal fallback hotkey.
- `Cmd+F` opens `Omnisearch: In-file search`, which searches the active Markdown note and jumps to a selected match with `Enter`.
- `Cmd+Shift+P` keeps core Global Search available for built-in search syntax.
- Doubleshift provides the double-tap behavior. Its settings map left Shift double-tap to `omnisearch:show-modal`.

## Hotkey Discovery

Use `Cmd+P` to open the Command Palette and search for a command. Obsidian shows configured hotkeys next to commands, which is the fastest way to remember custom bindings.
