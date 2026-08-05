## macOS Startup Configuration

This folder configures the opt-in per-machine workflow implemented by `vault mac-startup` and [[_system/tools/mac-automation/README|macOS Automation]].

It is owned by [[_system/local/skills/infra-code-folder-and-computer-topology/README|Code Folder And Computer Topology Config]].

### Ownership

- `defaults.json` is portable and public-exported. It must keep startup automation and every action disabled so a fresh bootstrap never installs or runs machine automation.
- `private/machines.json` contains machine-specific opt-ins keyed by the clone-local `vault.machine-id`. Public bootstrap export excludes it.
- The registered machine and platform remain authoritative in `_system/local/skills/infra-code-folder-and-computer-topology/private/machines.json`; this config only chooses startup actions.

### Schema

Both files use `schema_version: 1`. Portable defaults define the LaunchAgent label, known action flags, an empty application list, and an empty legacy-agent list. A private machine entry can override:

```json
{
  "enabled": true,
  "actions": {
    "open-applications": true,
    "remap-tilde-key": true
  },
  "applications": [
    "com.bitwarden.desktop"
  ],
  "legacy_launch_agents": [
    "com.example.old-login-job"
  ]
}
```

`applications` contains validated bundle identifiers. They are opened through macOS `open -b` only when `open-applications` is enabled. Prefer an application's native login helper when it owns more than launching the UI, such as WireGuard On-Demand Activation; do not add the same application to both systems.

An ordinary install is allowed only when the current clone has a registered, enabled macOS machine identity, its private startup entry is enabled, and at least one known action is enabled. During new-machine onboarding, `vault mac-startup install --provision-disabled` may configure exactly the current disabled Mac before fleet enablement; the flag refuses an already enabled machine.
