# Bootstrap Docs

This note is the internal source of truth for how the public vault bootstrap currently works, how it is intended to be used, and which moving parts matter when changing it.

## Public README Source

`_master/system/bootstrap/README-bootstrap.md` is exported as the public root `README.md`.
`_master/system/bootstrap/install.sh` is exported as the public root `install.sh`.

The export mapping lives in `_master/system/bootstrap/bootstrap-export.json` under `root_files`:

```json
{
  "source": "_master/system/bootstrap/README-bootstrap.md",
  "target": "README.md"
},
{
  "source": "_master/system/bootstrap/install.sh",
  "target": "install.sh"
}
```

Keep public setup instructions in `README-bootstrap.md`, but keep install implementation in `install.sh`. Keep implementation notes, edge cases, and maintenance details in this file.

The public root `_master/00-StartHere.md` is intentionally not exported. Its first-read and daily-flow guidance is folded into the public README instead.

## Internal Docs Stay Split

- `_master/system/context/SCRIPTS.md`: normal command/operator workflows.
- `_master/system/context/SCRIPT-REFERENCE.md`: full script inventory and one-time script cautions.
- `_master/01-Context.md`: vault architecture, folder model, data model, and bootstrap export workflow.
- `_master/system/context/OBSIDIAN-PROFILE.md`: Obsidian profile, plugins, UI settings, templates, Sync Embeds.

Generated copies under `_master/system/context/*.md` are agent-readable outputs from source docs. Edit the source files, not generated copies.

## Public Export Flow

`vault bootstrap-export --force` exports to `~/Code/vault-public` by default.

The exporter:

- copies root agent wiring, selected root files, root `.obsidian` profile files with configured exclusions, `_master` minus generated/private outputs, empty `_library`, `_wiki/AGENTS.md`, and configured context folder scaffolds;
- writes `_master/system/bootstrap/state/export-manifest.json` so future exports can remove stale export-owned files;
- preserves repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs;
- refuses to export inside the source vault.

## Plugin Code

Most plugin code does not ship in public export. Plugin directories keep public metadata, styles, and non-sensitive settings:

- `manifest.json`
- `styles.css`
- `data.json` unless denylisted

Plugin code is intentionally excluded for third-party plugins:

- `main.js` excluded
- plugin backup/migration/helper files excluded

Two local plugins ship their bundles because they are source-of-truth vault behavior:

- `context-nine/main.js`
- `system3-relay/main.js`

Sensitive/local plugin config is still excluded:

- `system3-relay/data.json` excluded
- `context-nine/data.json` excluded
- other integration-ish plugin config excluded too

Correct wording: Export includes plugin metadata/styles and non-sensitive settings, ships source bundles only for Context Nine and Relay, and excludes known sensitive/local plugin config. Users install third-party plugin code locally after setup.

## First Install Flow

Public install script:

- installs Homebrew if it is missing, then checks Homebrew-managed dependencies;
- clones `MDerman/the-context-vault-template` into the default target `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`, or a first-argument target override;
- creates the target directory if it is missing and refuses only when the target exists and is non-empty;
- refuses when the target path exists as a file;
- stores upstream bootstrap Git state outside iCloud under `~/Library/Application Support/context-nine-vault-bootstrap`;
- stores vault-local bootstrap metadata under `_master/system/bootstrap/state`;
- runs from README via `sudo bash`, resolves the original sudo user, and writes the vault/state as that user;
- removes the public-repo `.git` pointer from the vault;
- runs `_master/system/bootstrap/init_vault.sh`, which asks for three exact context-folder slugs; user Git is off by default.

Public README invokes root `install.sh` through the GitHub raw URL and shows only the default command plus a custom-target example.

User Git is optional and separate. Users can run `_master/system/bootstrap/init_vault.sh --enable-git` later if they want personal Git/LFS for their own vault.

## Edge Cases

- Existing non-empty target vault folder: public install script refuses to continue.
- Existing target file: public install script refuses to continue.
- Missing target folder: public install script creates it before clone.
- Export root already has a Git repo: exporter preserves repo metadata and mirrors only export-owned content.
- Legacy root state paths (`.vault-bootstrap`, `.vault-upgrade`, `.bootstrap-export-manifest.json`) are not part of new installs. Upgrade keeps legacy fallbacks and migrates old install/report state into `_master/system/bootstrap/state`.
- Plugin config: excluded plugin config means users must sign in/configure local integrations after install.
- Upgrade command: README currently documents planned `vault upgrade` commands; keep this only if the command exists or is intentionally being previewed before implementation.
