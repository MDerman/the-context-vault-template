# Vault System And Bootstrap

This note is the internal source of truth for how the public vault bootstrap currently works, how it is intended to be used, and which moving parts matter when changing it.

## Public README Source

`_master/system/bootstrap/bootstrap-public-README.md` is exported as the public root `README.md`.
`_master/system/bootstrap/install.sh` is exported as the public root `install.sh`.

The export mapping lives in `_master/system/bootstrap/bootstrap-export.json` under `root_files`:

```json
{
  "source": "_master/system/bootstrap/bootstrap-public-README.md",
  "target": "README.md"
},
{
  "source": "_master/system/bootstrap/install.sh",
  "target": "install.sh"
}
```

Keep public setup instructions in `bootstrap-public-README.md`, but keep install implementation in `install.sh`. Keep implementation notes, edge cases, and maintenance details in this file.

## Internal Docs Stay Split

- `_master/system/context/SCRIPTS.md`: normal command/operator workflows.
- `_master/system/context/SCRIPT-REFERENCE.md`: full script inventory and one-time script cautions.
- `_master/01-Context.md`: vault architecture, folder model, data model, and bootstrap export workflow.
- `_master/README.md`: `_master` folder map and tooling/skill SOPs.
- `_master/system/context/OBSIDIAN-PROFILE.md`: Obsidian profile, plugins, UI settings, templates, Sync Embeds.

Generated copies under `_master/system/context/*.md` are agent-readable outputs from source docs. Edit the source files, not generated copies.

## Public Export Flow

`vault bootstrap-export --force` exports to `~/Code/vault-public` by default.

The exporter:

- copies root agent wiring, selected root files, root `.obsidian` and `.obsidian-mobile` profile files with configured exclusions, `_master` minus generated/private outputs, empty `_library`, `_wiki/AGENTS.md`, and configured context folder scaffolds;
- writes `_master/system/bootstrap/state/export-manifest.json` so future exports can remove stale export-owned files;
- preserves repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs;
- refuses to export inside the source vault.

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

`_master/system/bootstrap/install_plugins.py` installs third-party active plugin bundles during setup and upgrade. It reads `.obsidian/community-plugins.json`, skips exact-copy plugins from `obsidian_plugin_exact_copy_plugins`, resolves each remaining plugin through Obsidian's community plugin registry, and downloads `main.js`, `manifest.json`, and optional `styles.css` from the GitHub release matching the exported plugin manifest version.

Correct wording: Export includes plugin metadata/styles and non-sensitive settings, ships source bundles only for Context Nine, Simple Folder Note, and Relay, downloads active third-party plugin bundles during setup/upgrade, and excludes known sensitive/local plugin config.

## First Install Flow

Public install script:

- installs Homebrew if it is missing, then checks Homebrew-managed dependencies;
- clones `MDerman/the-context-vault-template` into the default target `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`, or a first-argument target override;
- expands quoted `~`, `~/...`, and `~user/...` target overrides before creating the target directory;
- resolves relative target overrides from the directory where the installer was launched;
- creates the target directory if it is missing and refuses only when the target exists and is non-empty;
- refuses when the target path exists as a file;
- stores upstream bootstrap Git state outside iCloud under `~/Library/Application Support/context-nine-vault-bootstrap`;
- stores vault-local bootstrap metadata under `_master/system/bootstrap/state`;
- runs from README via `sudo bash`, resolves the original sudo user, and writes the vault/state as that user;
- removes the public-repo `.git` pointer from the vault;
- runs `_master/system/bootstrap/init_vault.sh`, which asks for three exact context-folder slugs; user Git is off by default.
- downloads active third-party Obsidian plugin bundles, while Context Nine and Relay are already shipped in the vault export.

Public README invokes root `install.sh` through the GitHub raw URL and shows only the default command plus a custom-target example.

User Git is optional and separate. Users can run `_master/system/bootstrap/init_vault.sh --enable-git` later if they want personal Git/LFS for their own vault.

## Profile Upgrade Flow

`vault profile upgrade --dry-run` and `vault profile upgrade --apply` use the same hidden upstream Git state as `vault upgrade`, but only apply root `.obsidian` profile files for plugins, theme, hotkeys, snippets, and safe profile settings. Workspace/open-tab layout files are skipped unless the user passes `--include-workspace`.

Profile upgrade does not advance the installed public commit. A later full `vault upgrade --apply` still sees all non-profile public updates.

## Edge Cases

- Existing non-empty target vault folder: public install script refuses to continue.
- Existing target file: public install script refuses to continue.
- Missing target folder: public install script creates it before clone.
- Quoted custom target like `"~/Documents/Obsidian/vault"`: installer expands it to the invoking user's home, not a literal `~/` folder.
- Transient GitHub registry or release-asset download failures are retried before install fails.
- Export root already has a Git repo: exporter preserves repo metadata and mirrors only export-owned content.
- Legacy root state paths (`.vault-bootstrap`, `.vault-upgrade`, `.bootstrap-export-manifest.json`) are not part of new installs. Upgrade keeps legacy fallbacks and migrates old install/report state into `_master/system/bootstrap/state`.
- Plugin config: excluded plugin config means users must sign in/configure local integrations after install.
- Upgrade command: README currently documents planned `vault upgrade` commands; keep this only if the command exists or is intentionally being previewed before implementation.

## System Folder Map

- `_master/system/bootstrap`: first install, public export config, generated agent instructions, dependency install, plugin install, and skill sync scripts.
- `_master/system/context`: agent-readable generated context, durable command docs, Obsidian profile docs, and current rollups.
- `_master/system/scripts`: implementations behind the `vault` dispatcher and supporting script utilities.
- `_master/system/migrations`: versioned migrations for public bootstrap upgrades.
- `_master/system/obsidian_notes`: notes and guides for editing Obsidian-specific UI, CSS, and plugin behavior.
- `_master/system/inbox`: generated/import inbox files such as Brain Dump imports.
- `_master/system/backup`: local generated backups. This folder is not intended as public source material.

New system-level tools should go in `_master/system/scripts` only when they belong behind `vault`. Otherwise use `_master/general-tools` and document dependency needs in `_master/system/bootstrap/Brewfile`.
