# Bootstrap Docs

This note is the internal source of truth for how the public vault bootstrap currently works, how it is intended to be used, and which moving parts matter when changing it.

## Public README Source

`master/system/bootstrap/README-bootstrap.md` is exported as the public root `README.md`.

The export mapping lives in `master/system/bootstrap/bootstrap-export.json` under `root_files`:

```json
{
  "source": "master/system/bootstrap/README-bootstrap.md",
  "target": "README.md"
}
```

Keep public setup instructions in `README-bootstrap.md`. Keep implementation notes, edge cases, and maintenance details in this file.

## Internal Docs Stay Split

- `master/system/context/SCRIPTS.md`: normal command/operator workflows.
- `master/system/context/SCRIPT-REFERENCE.md`: full script inventory and one-time script cautions.
- `master/01-Context.md`: vault architecture, folder model, data model, and bootstrap export workflow.
- `master/system/context/OBSIDIAN-PROFILE.md`: Obsidian profile, plugins, UI settings, templates, Sync Embeds.

Generated copies under `master/system/context/*.md` are agent-readable outputs from source docs. Edit the source files, not generated copies.

## Public Export Flow

`vault bootstrap-export --force` exports to `~/Code/vault-public` by default.

The exporter:

- copies root agent wiring, selected root files, root `.obsidian` profile files with configured exclusions, `master` minus generated/private outputs, empty `library`, `wiki/AGENTS.md`, and configured context folder scaffolds;
- writes `.bootstrap-export-manifest.json` so future exports can remove stale export-owned files;
- preserves repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs;
- refuses to export inside the source vault.

## Plugin Code

Plugin code does not ship in public export. Plugin directories keep only public metadata and styles:

- `manifest.json`
- `styles.css`

Code and config are intentionally excluded for safety:

- `main.js` excluded
- `data.json` excluded
- plugin backup/migration/helper files excluded
- `system3-relay/data.json` excluded
- `context-nine/data.json` excluded
- other integration-ish plugin config excluded too

Correct wording: Export includes plugin metadata/styles, but excludes plugin bundles and local plugin data/config. Users install or configure plugins locally after setup.

## First Install Flow

Public README install script:

- expects Homebrew installed first;
- clones `MDerman/the-context-vault-template` into `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`;
- stores upstream bootstrap Git state outside iCloud under `~/Library/Application Support/matt-vault-bootstrap`;
- removes the public-repo `.git` pointer from the vault;
- runs `master/system/bootstrap/init_vault.sh --no-git`.

User Git is optional and separate. Users can run `master/system/bootstrap/init_vault.sh --enable-git` later if they want personal Git/LFS for their own vault.

## Edge Cases

- Existing non-empty target vault folder: public install script refuses to continue.
- Missing iCloud Obsidian Documents folder: public install script tells user to install/open Obsidian with iCloud enabled first.
- Export root already has a Git repo: exporter preserves repo metadata and mirrors only export-owned content.
- Plugin config: excluded plugin config means users must sign in/configure local integrations after install.
- Upgrade command: README currently documents planned `vault upgrade` commands; keep this only if the command exists or is intentionally being previewed before implementation.
