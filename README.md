# Context9 Obsidian Vault Setup

The goal of this vault is to have one Obsidian vault where everything related to your personal life, businesses, and other fields of life can live together while staying isolated. It is set up so agents, skills, and workflows have enough context to help schedule, evolve, update, code, and act as personal assistants for you and your business.

This is made possible by a custom plugin called Context Nine and by the Relay plugin and many others. Relay lets team members collaborate on selected folders into their vault. This assumes everyone on your team will be using this vault setup.

## Where To Learn The Vault

After setup, start here:

- `master/00-StartHere.md`: first read and daily operating flow.
- `master/01-Context.md`: folder model, context folders, private/user-owned content, tasks, projects, epics, content, dashboards, and Relay collaboration.
- `master/system/context/OBSIDIAN-PROFILE.md`: Obsidian plugins, settings, templates, UI, and profile details.
- `master/system/context/SCRIPTS.md`: `vault` commands and normal workflows.
- `master/system/bootstrap/bootstrapdocs.md`: bootstrap/export internals.

For Relay collaboration, read `master/01-Context.md` after setup.

## Install On New Mac

Paste this from any terminal directory:

```bash
curl -fsSL https://raw.githubusercontent.com/MDerman/the-context-vault-template/main/install.sh | bash
```

To install somewhere else, pass a target path:

```bash
curl -fsSL https://raw.githubusercontent.com/MDerman/the-context-vault-template/main/install.sh | bash -s -- "/custom/Vault/path"
```

Result:

- Vault lives at `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault` unless you pass a custom target path as the first script argument.
- Public upstream Git state lives outside iCloud under `~/Library/Application Support/context-nine-vault-bootstrap/`.
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
