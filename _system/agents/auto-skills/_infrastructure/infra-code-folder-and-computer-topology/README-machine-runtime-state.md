## Machine Runtime State

Use these ownership boundaries when an infrastructure workflow needs local state, logs, locks, caches, or generated runtime files.

### Code workspace state

Machine-local state for Code workspace reconciliation belongs under:

```text
~/Code/.workspace-sync/
```

- Keep the directory hidden from ordinary Code browsing and exclude `.workspace-sync` from recursive repository discovery.
- Prefer `state.json` for the latest snapshot, bounded `history.jsonl` for summaries, and `runs/` for recent detailed records.
- Use atomic writes, mode `0700` for private directories, and `0600` for files containing local paths or operational metadata.
- Store sanitized facts only. Keep credentials and environment values in their owning env or credential system.
- Treat this state as local, rebuildable, and unsynchronized. Do not make `~/Code/.workspace-sync` a Git repository or copy it between machines.
- Use native OS locations when the operating system owns the artifact, such as LaunchAgents, systemd user units, or supervisor stdout logs. A workspace-sync record may reference those paths without duplicating them.

### Vault-owned state

Use `_system/local/` when the vault itself owns the configuration or state and it should travel with, configure, or report on this vault:

- `_system/local/skills/<skill-name>/` for per-skill configuration and private instance facts.
- `_system/local/state/` for ignored vault reports, backups, migrations, and install/export runtime state.
- Other `_system/local/` files for general vault configuration.

Do not put machine-wide Code workspace history in `_system/local`; do not put authoritative fleet configuration in `~/Code/.workspace-sync`. Desired cross-machine repository layout remains in the topology registry, while each machine's reconciliation observations remain under its own Code root.
