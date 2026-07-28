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
- `_system/agents/README.md`: agent skill docs.
- `_system/tools/README.md`: reusable tool docs.
- `_system/docs/obsidian/README.md`: Obsidian profile, plugins, UI settings, templates, Sync Embeds.

`_system/docs/` holds durable command, Obsidian, and workflow documentation. Live agent routing comes from `vault inventory`; editable operating state stays in context-folder source notes.

## Public Export Flow

`vault bootstrap-export --force` exports to `~/Code/vault-public` by default.

The exporter:

- copies root agent wiring, selected root files, root `.obsidian` and `.obsidian-mobile` profile files with configured exclusions, `_system` minus generated/private outputs, empty `_library`, `_wiki/AGENTS.md`, and configured context folder scaffolds;
- derives managed dependency projection targets from `_system/config/deps.json` and omits them; fresh installs recreate local projections without exporting machine-specific absolute symlinks;
- writes `_system/state/export-manifest.json` so future exports can remove stale export-owned files;
- preserves repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs;
- exports config-folder README/defaults but excludes `_system/config/*/private/**` and all `_system/config/env/**` contents;
- refuses to export inside the source vault.

Use raw export for inspection and repair only. Normal public publishing goes through:

```bash
vault release publish --dry-run --bump patch
vault release publish --bump patch
```

`vault release publish` bumps the public SemVer release metadata, writes `_system/config/dependencies.lock.json`, exports the public vault, commits `~/Code/vault-public`, creates annotated tag `vX.Y.Z`, pushes the commit/tag, and creates the GitHub Release. Use `--bump minor`, `--bump major`, or `--version X.Y.Z` when the release should not be a patch bump.

Release metadata lives in `_system/bootstrap/release.json`. It stores the SemVer, tag, release timestamp, dependency lock path, and dependency lock SHA-256. Any public release must update this file through `vault release publish`; do not commit a public export with stale release metadata.

Dependency lock metadata lives in `_system/config/dependencies.lock.json`. It records tested Homebrew dependency versions, exact external repo commits from `deps.json`, Obsidian plugin manifest versions, and GitHub CLI/`gh skill` availability for the release.

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
- stores vault-local bootstrap metadata under `_system/state/install.json`;
- runs from README via `sudo bash`, resolves the original sudo user, and writes the vault/state as that user;
- removes the public-repo `.git` pointer from the vault;
- runs `_system/bootstrap/init_vault.sh --enable-git`, which asks for three exact context-folder slugs and initializes personal Git/LFS directly under `~/.local/share/vault-git/<vault-name>.git`, outside iCloud.
- downloads active third-party Obsidian plugin bundles, while Context Nine and Relay are already shipped in the vault export.
- clones every repo from `_system/config/deps.json` at release-locked commits, creates projections, and runs vault-owned setup hooks. Agent Canvas setup builds editable checkout, links Bun package, and installs `~/.local/bin/agent-canvas`.

Public README invokes root `install.sh` through the GitHub raw URL and shows only the default command plus a custom-target example.

User Git is separate from hidden public-upstream state. Public installs enable personal Git/LFS by default outside iCloud. Run `init_vault.sh --no-git` only for manual setup that intentionally omits personal Git.

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
- Upgrade reports are written under `_system/state/upgrade-reports`; generated install/export state remains local and excluded from public export.
- Plugin config: excluded plugin config means users must sign in/configure local integrations after install.
- Upgrade command: README currently documents planned `vault upgrade` commands; keep this only if the command exists or is intentionally being previewed before implementation.
- Upgrade reports include from/to version and commit, target release tag, dependency lock hash, result, error, and timestamps. Install state advances only after file changes, migrations, and dependency sync succeed; failed upgrades leave the previous installed version/commit in place and expose the failed attempt through `vault upgrade status`.

## System Folder Map

- `_system/bootstrap`: first install, public export config, release metadata, upgrade policy, agent symlink helpers, dependency install, and plugin install. Canonical skill sync lives under `_system/agents`.
- `_system/docs`: durable command, Obsidian profile, and workflow docs.
- `_system/commands`: implementations behind the `vault` dispatcher and supporting script utilities.
- `_system/config`: vault, dependency, calendar, and Dashboard configuration.
- `_system/migrations`: empty framework for future public bootstrap migrations.
- `_system/inbox`: generated/import inbox files such as Brain Dump imports.
- `_system/state`: ignored local backups, install/export state, and upgrade reports.
- `_system/sync`: rclone backup/sync tooling.
- `_system/tools`: reusable tools outside `vault` dispatcher.

New system-level tools should go in `_system/commands` only when they belong behind `vault`. Otherwise use `_system/tools` and document dependency needs in `_system/bootstrap/Brewfile`.
