# Context9 Obsidian Vault Setup

The goal of this vault is to have one Obsidian vault where everything related to your personal life, businesses, and other fields of life can live together while staying isolated. It is set up so agents, skills, and workflows have enough context to help schedule, evolve, update, code, and act as personal assistants for you and your business.

This is made possible by a custom plugin called Context Nine and by the Relay plugin and many others. Relay lets team members collaborate on selected folders into their vault. This assumes everyone on your team will be using this vault setup.

## How To Use The Vault

This vault is one command center with numbered context folders as source-of-truth workspaces. System notes describe how the vault is structured, what each workspace is trying to become, and how tasks, calendar blocks, periodic notes, and agents keep work moving.

Start here after opening the vault:

- `master/01-Context.md`: folder model, context folders, private/user-owned content, tasks, projects, epics, content, dashboards, and Relay collaboration.
- `master/system/context/02-Identity.md`: identity answers for each active workspace.
- `master/system/context/03-Momentum.md`: cadence, tasks, calendar, accountability, and social selling answers.
- `master/system/context/OBSIDIAN-PROFILE.md`: Obsidian plugins, settings, templates, UI, and profile details.
- `master/system/context/SCRIPTS.md`: `vault` commands and normal workflows.
- `master/system/bootstrap/bootstrapdocs.md`: bootstrap/export internals.

For Relay collaboration, read `master/01-Context.md`.

Default workspace map:

- `01-personal`: personal life, health, relationships, finances, default capture, and personal accountability.
- `02-personal-brand`: personal brand, writing, media, audience, authority, and social selling.
- `03-business`: product and business execution.

Daily flow:

1. Run `vault refresh`.
2. Open `master/system/context/CONTEXT.md`.
3. Open today's agent daily rollup under `master/system/context/`.
4. Check `master/_obsidian/bases/tasks-today.base` and `master/_obsidian/bases/tasks-home.base`.
5. Check `master/_obsidian/bases/content-kanban.base` when content is part of the day.

Content-enabled workspaces use `_obsidian/content/publications`, `_obsidian/content/items`, `_obsidian/content/ideas`, and `_obsidian/content-schedules`. Tasks still live in `_obsidian/tasks`; a content note becomes work only when it has a real next action, status, date, blocker, or project.

## Install On New Mac

First run the install script from any terminal directory:

```bash
tmp="$(mktemp)" && curl -fsSL https://raw.githubusercontent.com/MDerman/the-context-vault-template/main/install.sh -o "$tmp" && sudo bash "$tmp" && rm -f "$tmp"
```

To install somewhere else, pass a target path:

```bash
tmp="$(mktemp)" && curl -fsSL https://raw.githubusercontent.com/MDerman/the-context-vault-template/main/install.sh -o "$tmp" && sudo bash "$tmp" "/custom/Vault/path" && rm -f "$tmp"
```

Then open it in Obsidian:

1. Open Obsidian.
2. Choose "Open folder as vault".
3. Select the vault folder, usually `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`.

Result:

- Vault lives at `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault` unless you pass a custom target path as the first script argument.
- Public upstream Git state lives outside iCloud under `~/Library/Application Support/context-nine-vault-bootstrap/`.
- Vault-local bootstrap metadata lives under `master/system/bootstrap/state/`.
- The installer runs with `sudo`, but writes the vault and bootstrap state as the user who invoked sudo.
- Vault folder has no public-repo `.git` pointer after install.
- `init_vault.sh` installs/checks command dependencies, asks context-folder questions, generates agent files, and installs `vault`.
- Run `master/system/bootstrap/init_vault.sh --enable-git` later only if you want optional personal Git/LFS for your own vault.

Export includes plugin metadata/styles and non-sensitive settings, ships source bundles only for Context Nine and Relay, and excludes known sensitive/local plugin config. Install third-party plugin code locally after setup.

## Upgrade Installed Vault

Preview future public updates:

```bash
vault upgrade --dry-run
```

Apply public setup updates:

```bash
vault upgrade --apply
```

Repair/inspect upgrade state:

```bash
vault upgrade status
vault upgrade doctor
vault upgrade repair-prompt
```
