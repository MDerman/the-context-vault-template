---
type: agent-reference
status: enabled
---
# Bootstrap Export

Export the public bootstrap vault from the current vault:

```bash
vault bootstrap-export --dry-run
vault bootstrap-export --force
```

Use `vault bootstrap-export --force` for local inspection and repair only. For a public version that installed vaults can upgrade to and report against, use:

```bash
vault release publish --dry-run --bump patch
vault release publish --bump patch
```

`vault release publish` updates `_master/system/bootstrap/state/release.json`, writes `_master/system/config/dependencies.lock.json`, exports, commits the public repo, creates tag `vX.Y.Z`, pushes, and creates the GitHub Release. Any public export commit must include a fresh `release.json` bump.

The export writes a root `README.md` from `_master/system/bootstrap/README-public-vault-template.md`. Internal bootstrap/export mechanics live in `_master/system/README.md`. With `--force`, the exporter mirrors export-owned files into the configured export root while preserving repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs.

Managed dependency projection targets are derived from `_master/system/config/deps.json` and excluded with all descendants. Install recreates them from local dependency checkouts, so public output never contains machine-specific absolute projection symlinks.

Default export root and context folder output mapping live in:

```text
_master/system/bootstrap/bootstrap-export.json
```

Implementation script: `_master/system/scripts/bootstrap_export.py`.
