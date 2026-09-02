# Context Vault

Context Vault is a local-first Obsidian and Markdown system that keeps notes, tasks, and agent context in one filesystem, part of the free and open-source developer system at [ctx9.com](https://ctx9.com).

It uses [Context Nine](https://community.obsidian.md/plugins/context-nine), its companion plugin listed in Obsidian's Community Plugin directory.

## Install with your agent

Install the skill for each agent you use:

```bash
gh skill install MDerman/the-context-vault-template skills/ctx9-install-context-vault --agent codex --scope user
gh skill install MDerman/the-context-vault-template skills/ctx9-install-context-vault --agent claude-code --scope user
```

Start a new Codex or Claude Code session, then tell your agent:

> Use $ctx9-install-context-vault to install Context Vault. Ask me where it should live, run the setup wizard with me, and verify the finished Vault.

### What gets installed

Your agent creates the Vault in a folder you choose, asks you to name three context folders, installs the configured Obsidian plugins and command-line tools, adds the `vault` command, starts local Git/LFS history, and registers a daily refresh on macOS. The optional CTX9 skill system is a separate yes-or-no choice. Open the finished folder in Obsidian. Your notes, tasks, projects, views, and agent instructions are ordinary Markdown files, so Obsidian and your agent work from the same source.

## Ten things to try first

1. Open `Dashboard.md`. It collects your current tasks, periodic notes, and links into each context.
2. If you kept the starter name, open `business/_obsidian/bases/tasks-kanban.base`. Click the plus button in a status column to create a task already routed to that context and status. `Alt+T` opens the task dialog from anywhere.
3. Ask your agent to create an epic called `Launch` in `business`, or run `vault epic create business "Launch"`. The command creates the epic note and its task view.
4. Click today in the Calendar sidebar to open your daily note. Write what happened, what matters, and what should become a task.
5. Ask your agent: `Run vault inventory. Tell me what was installed, how my contexts are organized, and what skills are available.` If you skipped the optional skill system, it should say so.
6. Tap the left `Shift` key twice. Omnisearch finds notes across the Vault and tolerates small typos.
7. Press `Cmd+P` to run any Obsidian command. Press `Cmd+Shift+P` for core Global Search and its search syntax.
8. Hover a folder in the File Explorer and press `Cmd+N`. The new note is created in that folder. With no folder hovered, it behaves like Obsidian's normal new-note command.
9. Press `Cmd+Shift+F` to reveal the open note in the File Explorer. This is useful when search or links have taken you deep into the Vault.
10. Open Relay settings and sign in when you want collaboration. Share one context folder or another explicit folder with someone else, work together with live cursors, and keep every unshared folder private.

## Problems this solves

- Notes, tasks, projects, and agent context stop drifting across separate apps.
- Business, personal, and public work keep their own boundaries without losing shared structure.
- Your working context stays readable, portable, and under your control.

## How I solved it

- I made the filesystem and Markdown the source of truth, with Obsidian as the interface.
- I use context folders for distinct areas of life and work, each with its own tasks, projects, templates, and attachments.
- I added small commands and setup wizards for repeatable maintenance without hiding the underlying files.
- I kept the skill system separate and optional, so the Vault works on its own.
