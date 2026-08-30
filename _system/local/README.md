## Local Vault Data

Vault-owned user-specific configuration and observed runtime state live here. This folder never owns desired machine, workspace, skill-projection, or agent dependency registries; those form the self-contained `_system/agents` package.

### Skill configuration contract

For skill `<skill-name>`, use:

```text
_system/agents/_package/instance/skills/config/<skill-name>/
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

General vault configuration stays directly under `_system/local`; ignored reports, backups, and install/export state live under `state/`. Machine-wide Code workspace runtime data belongs under `~/Code/.workspace-sync/`, not here; follow [[_system/agents/skills/auto/_infrastructure/infra-code-folder-and-computer-topology/README-machine-runtime-state|Machine Runtime State]].

`_system/local/state` is general Vault runtime evidence, not the credential inventory and not a secret-distribution mechanism. The canonical machine-credential vocabulary is the non-secret `_system/agents/_package/instance/fleet/machine-secrets.json`; sanitized fleet verification lives in `_system/agents/_package/generated/state/machine-secrets.lock.json`. Actual values may still exist in ignored `_system/local/env/.env`, an owning repository's env workflow, `_system/agents/_package/instance/skills/config/*/private` when explicitly appropriate, or an OS/provider-native store. Files named `machine-secrets.yaml` and `machine-secrets.lock.json` contain no secret values.

Public export excludes every `_system/agents/_package/instance/skills/config/**/private/**` path, `_system/local/snippets/private/**`, all `_system/local/env/**` contents, and `_system/local/state/**`. Public skills must handle missing private config with setup guidance.
