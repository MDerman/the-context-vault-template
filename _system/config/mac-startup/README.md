# macOS Startup Configuration

This folder configures the opt-in per-machine workflow implemented by `vault mac-startup` and [[_system/tools/mac-automation/README|macOS Automation]].

## Ownership

- `defaults.json` is portable and public-exported. It must keep startup automation and every action disabled so a fresh bootstrap never installs or runs machine automation.
- `private/machines.json` contains machine-specific opt-ins keyed by the clone-local `vault.machine-id`. Public bootstrap export excludes it.
- The registered machine and platform remain authoritative in `_system/config/infra-code-folder-and-computer-topology/private/machines.json`; this config only chooses startup actions.

## Schema

Both files use `schema_version: 1`. Portable defaults define the LaunchAgent label, known action flags, and an empty legacy-agent list. A private machine entry can override:

```json
{
  "enabled": true,
  "actions": {
    "remap-tilde-key": true
  },
  "legacy_launch_agents": [
    "com.example.old-login-job"
  ]
}
```

An install is allowed only when the current clone has a registered, enabled macOS machine identity, its private startup entry is enabled, and at least one known action is enabled.
