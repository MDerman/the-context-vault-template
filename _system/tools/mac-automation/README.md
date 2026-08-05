# macOS Automation

Reusable macOS automation lives here. The managed login workflow is exposed through `vault mac-startup`; do not install the source script directly as a LaunchAgent.

## Quick Start

Inspect configuration and runtime state:

```bash
vault mac-startup status
vault mac-startup status --json
```

Preview or install the configured actions for this machine:

```bash
vault mac-startup install --dry-run
vault mac-startup install
vault mac-startup install --provision-disabled
```

Run the enabled actions immediately without changing the LaunchAgent:

```bash
vault mac-startup run --dry-run
vault mac-startup run
```

Unload the managed job and remove its installed plist/runtime:

```bash
vault mac-startup uninstall --dry-run
vault mac-startup uninstall
```

Uninstall deliberately leaves the current in-memory HID mapping unchanged. Restarting the Mac clears that mapping unless another tool reapplies it.

## Runtime

Installation creates the per-user `com.obsidian-context-vault.mac-startup` LaunchAgent with `RunAtLoad`. It copies `startup.sh` and a resolved action snapshot under `~/Library/Application Support/obsidian-context-vault/mac-startup/`, so login does not depend on the iCloud vault being ready.

Logs are written to:

```text
~/Library/Logs/obsidian-context-vault-mac-startup.out.log
~/Library/Logs/obsidian-context-vault-mac-startup.err.log
```

Configured legacy LaunchAgents are unloaded and moved into the runtime folder's `legacy-launchagents/` directory. They are archived rather than deleted and are not restored automatically by uninstall.

## Actions And Bootstrap Safety

Configuration ownership and the opt-in schema live in [[_system/local/skills/infra-code-folder-and-computer-topology/Mac Startup/README|macOS Startup Configuration]]. Public defaults keep the workflow disabled, private per-machine configuration is excluded from bootstrap export, and the bootstrap installer never invokes `vault mac-startup install`.

To add another optional login action:

1. Add its disabled flag to `_system/local/skills/infra-code-folder-and-computer-topology/Mac Startup/defaults.json`.
2. Add its implementation and dispatch case to `startup.sh`.
3. Add the action ID to the command's supported-action validation.
4. Add focused configuration, runner, plist, and status tests.

The `remap-tilde-key` action applies HID usage `0x35` to `0x64` for the logged-in user. The `open-applications` action expands validated private-config bundle identifiers into `open -b` calls. Do not use it for an application such as WireGuard when that application has its own login helper and service lifecycle.

Normal install and run operations require an enabled registered Mac. The explicit `--provision-disabled` option exists for the current clone during reviewed onboarding and refuses an already enabled machine.
