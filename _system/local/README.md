## Local Vault Data

User-specific configuration and runtime state live here. Generic workflows stay in skills and tools.

### Skill configuration contract

For skill `<skill-name>`, use:

```text
_system/local/skills/<skill-name>/
  README.md                 # ownership, schema, setup, and consumers
  defaults.*                # optional portable tracked defaults
  private/                  # private instance values; never public-exported
```

- Folder basename must match skill folder/frontmatter name.
- Keep generic behavior, validation, and reusable snippets in skill folder.
- Keep changing domains, account/project IDs, machine facts, personal paths, repository locations, and deployment access details in matching config folder.
- Markdown, JSON, TOML, YAML, and shell-readable formats are valid. Choose format consumer can validate.
- Secrets and environment variables belong in [[_system/local/env/README|shared vault env]] or owning external repository env workflow. Do not duplicate external-repo secrets here.
- Config may reference external repositories by logical ID; topology config resolves IDs to local paths.
- Every config folder needs `README.md` describing public/private status and authoritative owner.

General vault configuration stays directly under `_system/local`; ignored reports, backups, and install/export state live under `state/`.

Public export excludes every `_system/local/skills/**/private/**` path, `_system/local/snippets/private/**`, all `_system/local/env/**` contents, and `_system/local/state/**`. Public skills must handle missing private config with setup guidance.
