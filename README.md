# The Context Vault Template

[Tutorial video](https://drive.google.com/file/d/1Rnlbrc10ckh9bnxiz_CkdLYXE0jTdyUI/view?usp=sharing)

## Install On New Mac

First run the install script from any terminal directory:

```bash
tmp="$(mktemp)" && curl -fsSL https://raw.githubusercontent.com/MDerman/the-context-vault-template/main/install.sh -o "$tmp" && sudo bash "$tmp" && rm -f "$tmp"
```

To install somewhere else, pass a target path:

```bash
tmp="$(mktemp)" && curl -fsSL https://raw.githubusercontent.com/MDerman/the-context-vault-template/main/install.sh -o "$tmp" && sudo bash "$tmp" "~/Documents/Obsidian/vault" && rm -f "$tmp"
```

Quoted `~` paths work too, for example `"~/Documents/Obsidian/vault"`.

Then open it in Obsidian:

1. Open Obsidian.
2. Choose "Open folder as vault".
3. Select the vault folder, usually `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`.

## Further Vault Overview

The goal of this vault is to have one Obsidian vault where everything related to your personal life, businesses, and other fields of life can live together while staying isolated. It is set up so agents, skills, and workflows have enough context to help schedule, evolve, update, code, and act as personal assistants for you and your business.

This is made possible by a custom plugin called Context Nine and by the Relay plugin and many others. Relay lets team members collaborate on selected folders into their vault. This assumes everyone on your team will be using this vault setup.

- Vault lives at `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault` unless you pass a custom target path as the first script argument.
- Public upstream Git state lives outside iCloud under `~/Library/Application Support/context-nine-vault-bootstrap/`.
- Vault-local bootstrap metadata lives under `_master/system/bootstrap/state/`.
- The installer runs with `sudo`, but writes the vault and bootstrap state as the user who invoked sudo.
- Vault folder has no public-repo `.git` pointer after install.
- `init_vault.sh` installs/checks command dependencies, creates starter context folders named `personal`, `personal-brand`, and `business`, asks whether to rename them, generates agent files, installs `vault` to `~/.local/bin/vault`, and adds that directory to zsh startup files.
- Context folder names must be lowercase slugs using letters, numbers, and hyphens. If you rename a starter folder during setup, the installer moves the folder and rewrites structured references such as paths, Obsidian links, plugin settings, frontmatter identity values, and `@context` tokens. It does not blindly rewrite normal prose.
- The one-line `sudo bash` installer also installs `/usr/local/bin/vault`, so `vault` works even before a new shell has loaded `~/.local/bin`.
- Run `_master/system/bootstrap/init_vault.sh --enable-git` later only if you want optional personal Git/LFS for your own vault.

Preview a context folder rename later with:

```bash
vault folder rename business studio --dry-run
```

Export includes plugin metadata/styles and non-sensitive settings, ships source bundles only for Context Nine and Relay, downloads active third-party plugin bundles during setup, and excludes known sensitive/local plugin config. When Obsidian first opens the vault, approve community plugins if Obsidian asks to trust the vault.

## How To Use The Vault

This vault is one command center with context folders as source-of-truth workspaces. System notes describe how the vault is structured, what each workspace is trying to become, and how tasks, calendar blocks, periodic notes, and agents keep work moving.

Start here after opening the vault:

- `_master/01-Context.md`: folder model, context folders, private/user-owned content, tasks, projects, epics, content, dashboards, and Relay collaboration.
- `_master/system/context/02-Identity.md`: identity answers for each active workspace.
- `_master/system/context/03-Momentum.md`: cadence, tasks, calendar, accountability, and social selling answers.
- `_master/system/context/OBSIDIAN-PROFILE.md`: Obsidian plugins, settings, templates, UI, and profile details.
- `_master/system/context/SCRIPTS.md`: `vault` commands and normal workflows.
- `_master/system/bootstrap/bootstrapdocs.md`: bootstrap/export internals.

For Relay collaboration, read `_master/01-Context.md`.

Default workspace map:

- `personal`: personal life, health, relationships, finances, default capture, and personal accountability.
- `personal-brand`: personal brand, writing, media, audience, authority, and social selling.
- `business`: product and business execution.

Daily flow:

1. Run `vault refresh`.
2. Open `_master/system/context/CONTEXT.md`.
3. Open today's agent daily rollup under `_master/system/context/`.
4. Check `_master/_obsidian/bases/tasks-today.base` and `_master/_obsidian/bases/tasks-home.base`.
5. Check `_master/_obsidian/bases/content-kanban.base` when content is part of the day.

Content-enabled workspaces use `_obsidian/content/publications`, `_obsidian/content/items`, `_obsidian/content/ideas`, and `_obsidian/content-schedules`. Tasks still live in `_obsidian/tasks`; a content note becomes work only when it has a real next action, status, date, blocker, or project.

## Upgrade Installed Vault

Preview future public updates:

```bash
vault upgrade --dry-run
```

Apply public setup updates:

```bash
vault upgrade --apply
```

You can also run `Vault Upgrade` from the Obsidian command palette. It applies the same public setup update as `vault upgrade --apply`.

Apply only Obsidian profile, theme, hotkey, and plugin updates:

```bash
vault profile upgrade --apply
```

Repair/inspect upgrade state:

```bash
vault upgrade status
vault upgrade doctor
vault upgrade repair-prompt
```
