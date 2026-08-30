# Vault System And Bootstrap

This note is the internal source of truth for how the public vault bootstrap currently works, how it is intended to be used, and which moving parts matter when changing it.

## Public README Source

`_system/bootstrap/README-public-vault-template.md` is exported as the public root `README.md`.
`_system/bootstrap/install.sh` is exported as the public root `install.sh`.

The export mapping lives in `_system/bootstrap/bootstrap-export.json` under `root_files`:

```json
{
  "source": "_system/bootstrap/README-public-vault-template.md",
  "target": "README.md"
},
{
  "source": "_system/bootstrap/install.sh",
  "target": "install.sh"
}
```

Keep public setup instructions in `README-public-vault-template.md`, but keep install implementation in `install.sh`. Keep implementation notes, edge cases, and maintenance details in this file.

## Internal Docs Stay Split

- `_system/docs/commands/README.md`: normal command/operator workflows.
- `_system/docs/commands/README-reference.md`: full command and bootstrap script inventory.
- `_system/README.md`: concise vault architecture, ownership, and routing.
- `_system/agents/README.md`: private standalone agent-package architecture; excluded from the public Vault.
- `_system/tools/README.md`: reusable tool docs.
- `_system/docs/obsidian/README.md`: Obsidian profile, plugins, UI settings, templates, Sync Embeds.

`_system/docs/` holds durable command, Obsidian, and workflow documentation. Live agent routing comes from `vault inventory`; editable operating state stays in context-folder source notes.

## Public Export Flow

`vault bootstrap-export --force` exports to `~/Code/ctx9/vault-public` by default.

The exporter:

- copies selected root files, root `.obsidian` and `.obsidian-mobile` profile files with configured exclusions, Vault system files, selected `_library` paths, `_wiki/AGENTS.md`, and configured context folder scaffolds;
- excludes `_system/agents/**` as one product boundary and never sanitizes or re-adds agent-package files;
- writes `_system/local/state/export-manifest.json` so future exports can remove stale export-owned files;
- preserves repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs;
- exports portable local README/defaults but excludes `_system/local/snippets/private/**`, all `_system/local/env/**` contents, and `_system/local/state/**`;
- refuses to export inside the source vault.

## Current Exclusion Boundary

`_system/bootstrap/bootstrap-export.json` is the executable source of truth. At a high level, export excludes:

- personal context content; only configured public context folder notes, Bases, periodic templates, and selected physical packs are produced;
- generated root dashboards, vault periodic rollups, system attachments, inbox contents, local state, and sync remnants;
- the complete `_system/agents/**` package, including skills, private instance configuration and generated state;
- private local skill/snippet subfolders and all `_system/local/env` contents while keeping the empty env folder;
- private invoice/email tools;
- sensitive names such as `.env`, secrets, kubeconfig, plugin integration data, plugin logs, third-party plugin code, `.DS_Store`, `__pycache__`, `.pyc`, and `.bak` files.

The standalone agent product has its own allowlist exporter, release metadata and publication approval. Vault export never consumes that allowlist.

Public context entries declare `capabilities`, `content_schedules`, and an optional `folder_template` explicitly. The bootstrap does not infer context types. Physical packs live under `_system/bootstrap/templates/context-folders/`.

Use raw export for inspection and repair only. Normal public publishing goes through:

```bash
vault release publish --dry-run --bump patch
vault release publish --bump patch
```

`vault release publish` preflights the Vault and Skill Problem System, publishes only meaningful export changes, and keeps independent SemVer metadata for each product. Use `--product vault|skills|all` for scoped retries after partial external failures. Changed Vault releases update the dependency lock; changed skill-system releases regenerate their public skill inventory.

Release metadata lives in `_system/bootstrap/release.json`. It stores the SemVer, tag, release timestamp, dependency lock path, and dependency lock SHA-256. Any public release must update this file through `vault release publish`; do not commit a public export with stale release metadata.

Dependency lock metadata lives in `_system/local/dependencies.lock.json`. It records verified public Vault package state and Obsidian plugin release inputs. Agent skills and external agent sources are independently owned.

## Plugin Code

Most plugin code does not ship in public export. Plugin directories in `.obsidian` and `.obsidian-mobile` keep public metadata, styles, and non-sensitive settings:

- `manifest.json`
- `styles.css`
- `data.json` unless denylisted

Plugin code is intentionally excluded for third-party plugins:

- `main.js` excluded
- plugin backup/migration/helper files excluded

Local or patched plugins ship their bundles exactly because they are source-of-truth vault behavior:

- `context-nine/main.js`
- `simple-folder-note/main.js`
- `system3-relay/main.js`

Sensitive/local plugin config is still excluded:

- `system3-relay/data.json` excluded from both desktop and mobile profiles
- `context-nine/data.json` excluded
- other integration-ish plugin config excluded too

Exact-copy plugin files are scanned for high-confidence secrets before export. Export aborts if a copied plugin bundle appears to contain private keys, API keys, or token literals.

`_system/bootstrap/install_plugins.py` installs third-party active plugin bundles during setup and upgrade. It reads `.obsidian/community-plugins.json`, skips exact-copy plugins from `obsidian_plugin_exact_copy_plugins`, resolves each remaining plugin through Obsidian's community plugin registry, and downloads `main.js`, `manifest.json`, and optional `styles.css` from the GitHub release matching the exported plugin manifest version.

Correct wording: Export includes plugin metadata/styles and non-sensitive settings, ships complete bundles for Context Nine, Simple Folder Note, and Relay, downloads active third-party plugin bundles during setup/upgrade, and excludes known sensitive/local plugin config.

## First Install Flow

Public install script:

- installs Homebrew if it is missing, then invokes `_system/deps/install.py` against `_system/deps/packages.yaml`; private CTX2 and agent prerequisites are deliberately excluded;
- clones `MDerman/the-context-vault-template` into the default target `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`, or a first-argument target override;
- expands quoted `~`, `~/...`, and `~user/...` target overrides before creating the target directory;
- resolves relative target overrides from the directory where the installer was launched;
- creates the target directory if it is missing and refuses only when the target exists and is non-empty;
- refuses when the target path exists as a file;
- stores upstream bootstrap Git state outside iCloud under `~/Library/Application Support/context-nine-vault-bootstrap`;
- stores vault-local bootstrap metadata under `_system/local/state/install.json`;
- runs from README via `sudo bash`, resolves the original sudo user, and writes the vault/state as that user;
- removes the public-repo `.git` pointer from the vault;
- runs `_system/bootstrap/init_vault.sh --enable-git`, which asks for three exact context-folder slugs, preserves the starter examples through explicit capabilities/templates, and initializes personal Git/LFS directly under `~/.local/share/vault-git/<vault-name>.git`.
- downloads active third-party Obsidian plugin bundles, while complete bundles for Context Nine, Simple Folder Note, and Relay are already shipped in the vault export.
- defaults to Vault-only in non-interactive mode. `--install-skill-system` explicitly opts in; `--skill-system-source` selects a reviewed local export or repository URL for tests and recovery.
- asks `Install the optional CTX9 skill system and public skills? [y/N]`. Declining or EOF leaves `_system/agents` absent.
- copies the released public `_system/agents` tree without Git metadata, initializes `_package/instance` from blank defaults, runs the shared skill-system wizard, installs every public skill globally, and records source URL, release version, commit, and selected integrations under `_system/local/state/skill-system-install.json`.

Public README invokes root `install.sh` through the GitHub raw URL and shows only the default command plus a custom-target example.

User Git is separate from hidden public-upstream state. Public installs enable personal Git/LFS by default only when creating the installation's primary Vault. Never run the Git-enabled initializer on a Mac joining an existing Vault through iCloud; use the worker-Mac onboarding flow, which requires no Vault Git and a dangling shared `.git` pointer. Run `init_vault.sh --no-git` for an intentional standalone Gitless setup.

## Profile Upgrade Flow

`vault profile upgrade --dry-run` and `vault profile upgrade` use the same hidden upstream Git state as `vault upgrade`, but only apply root `.obsidian` profile files for plugins, theme, hotkeys, snippets, and safe profile settings. Workspace/open-tab layout files are skipped unless the user passes `--include-workspace`.

Profile upgrade does not advance the installed public commit. A later full `vault upgrade` still sees all non-profile public updates.

## Edge Cases

- Existing non-empty target vault folder: public install script refuses to continue.
- Existing target file: public install script refuses to continue.
- Missing target folder: public install script creates it before clone.
- Quoted custom target like `"~/Documents/Obsidian/vault"`: installer expands it to the invoking user's home, not a literal `~/` folder.
- Transient GitHub registry or release-asset download failures are retried before install fails.
- Export root already has a Git repo: exporter preserves repo metadata and mirrors only export-owned content.
- Upgrade reports are written under `_system/local/state/upgrade-reports`; generated install/export state remains local and excluded from public export.
- Plugin config: excluded plugin config means users must sign in/configure local integrations after install.
- Upgrade command: README currently documents planned `vault upgrade` commands; keep this only if the command exists or is intentionally being previewed before implementation.
- Upgrade reports include from/to version and commit, target release tag, dependency lock hash, result, error, and timestamps. Install state advances only after file changes, migrations, and dependency sync succeed; failed upgrades leave the previous installed version/commit in place and expose the failed attempt through `vault upgrade status`.

## System Folder Map

- `_system/bootstrap`: first-install, public-export, release, upgrade, and plugin orchestration. Public dependency intent and installation live under `_system/deps`; canonical agent sync lives under `_system/agents`.
- `_system/docs`: durable command, Obsidian profile, and workflow docs.
- `_system/commands`: implementations behind the `vault` dispatcher and supporting script utilities.
- `_system/local`: user-specific general configuration, per-skill configuration, env tooling, and runtime state.
- `_system/migrations`: empty framework for future public bootstrap migrations.
- `_system/inbox`: generated/import inbox files such as Brain Dump imports.
- `_system/local/state`: ignored local backups, install/export state, and upgrade reports.
- `_system/sync`: disabled, unused, and unsupported historical rclone backup/sync tooling; keep its automation off.
- `_system/tools`: reusable tools outside `vault` dispatcher.

New system-level tools should go in `_system/commands` only when they belong behind `vault`. Otherwise use `_system/tools` and declare public Vault dependencies in `_system/deps/packages.yaml`.

The public dependency installer never provides private CTX2 or fleet-agent prerequisites. `ctx9-agents sync` owns those approved dependencies after private fleet authentication.
