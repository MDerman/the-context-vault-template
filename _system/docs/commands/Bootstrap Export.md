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

`vault release publish` preflights both public products, reports which exports changed, and publishes only those products. Each product keeps independent SemVer metadata, tags, commits, and GitHub Releases. Use `--product vault`, `--product skills`, or `--product all` to retry one side after a partial external failure.

The export writes a root `README.md` from `_system/bootstrap/README-public-vault-template.md`. Internal bootstrap/export mechanics live in `_system/bootstrap/README.md`. With `--force`, the exporter mirrors export-owned files into the configured export root while preserving repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs.

The Vault exporter excludes `_system/agents/**` completely. The Skill Problem System exporter separately publishes a sanitized `_system/agents` tree with public defaults, schemas, runtime, docs, and every active skill that passes its portability, privacy, configuration, provenance, and license checks. Its generated inventory records every exclusion.

Default export root and context folder output mapping live in:

```text
_system/bootstrap/bootstrap-export.json
```

Implementation script: `_system/commands/bootstrap_export.py`.

Interactive installs ask once whether to install the optional CTX9 skill system and public skills. Declining leaves `_system/agents` absent. Accepting copies the released public tree into the Vault, initializes its instance from blank defaults, runs the same setup wizard, and records release identity and selected integrations in ignored install state. Vault upgrades never overwrite that tree.
