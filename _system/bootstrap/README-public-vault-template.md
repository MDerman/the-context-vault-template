# Context Vault

Context Vault is a local-first Obsidian and Markdown system that keeps notes, tasks, and agent context in one filesystem, part of the free and open-source developer system at [ctx9.com](https://ctx9.com).

## Install with your agent

Install the skill for each agent you use:

```bash
gh skill install MDerman/the-context-vault-template skills/ctx9-install-context-vault --agent codex --scope user
gh skill install MDerman/the-context-vault-template skills/ctx9-install-context-vault --agent claude-code --scope user
```

Start a new Codex or Claude Code session, then tell your agent:

> Use $ctx9-install-context-vault to install Context Vault. Ask me where it should live, run the setup wizard with me, and verify the finished Vault.

## Problems this solves

- Notes, tasks, projects, and agent context stop drifting across separate apps.
- Business, personal, and public work keep their own boundaries without losing shared structure.
- Your working context stays readable, portable, and under your control.

## How I solved it

- I made the filesystem and Markdown the source of truth, with Obsidian as the interface.
- I use context folders for distinct areas of life and work, each with its own tasks, projects, templates, and attachments.
- I added small commands and setup wizards for repeatable maintenance without hiding the underlying files.
- I kept the skill system separate and optional, so the Vault works on its own.
