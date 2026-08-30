---
type: agent-reference
status: enabled
---
# Machines

Private registry: `_system/agents/_package/instance/fleet/machines.json`. It is tracked in private Vault Git and excluded from public exports. Registry schema v7 owns stable machine identity, registered home, Code and Vault roots, explicit Vault capability, one Git/refresh owner, iCloud host/remote-client relationships, role, canonical SSH alias, non-secret routes, agent eligibility, and optional VNC. `~` expands against the selected machine's registered home. Credentials, account identity, device keys, mount state, and leases remain machine-local.

## Commands

```bash
vault machine list [--json]
vault machine setup
vault machine init --id ID --display-name NAME --platform macos|linux
vault machine register-worker --id ID --display-name NAME --platform macos|linux --ssh-alias ID --home PATH --ssh-user USER --provider wireguard|tailscale [--vault-root PATH] [--vault-source MAC_HOST_ID]
vault machine access configure ID wireguard|tailscale --host HOST [--lan-host HOST] [--client-variant VARIANT]
vault machine access inspect ID [--provider wireguard|tailscale] [--attempts N]
vault machine access render [--target SOURCE_ID]... [--dry-run]
vault machine access switch ID wireguard|tailscale [--dry-run]
vault machine identify ID
vault machine status [NAME] [--json]
vault machine ssh NAME [-- COMMAND...]
vault machine vnc NAME [--no-open] [--local-port PORT]
vault machine vnc NAME --status
vault machine vnc NAME --stop
```

`vault machine setup` is the normal entrypoint. It initializes the primary registry when missing, requires an explicit provider with no default, previews a disabled worker and private note, prints an exact `$infra-onboard-machine` request, and can copy that editable request before opening `codex app` at the Vault. It never submits a Codex message.

Supported Vault modes are `primary-external-git`, `icloud-gitless`, `remote-sshfs`, and `none`. The primary uses clone-local `vault.machine-id`; Gitless Mac workers and remote Linux clients use mode-`0600` `~/.config/vault/machine-id`. A remote client mounts a full registered Mac worktree and never receives Git metadata.

`register-worker` is the lower-level deterministic route. A macOS worker with `--vault-root` gets the full Gitless iCloud Vault and no `git_dir`. A Linux worker with both `--vault-root` and `--vault-source` gets `remote-sshfs` desired state; either option alone is rejected. Without them it remains `none`. New selected-provider records may remain `pending` only while the machine is disabled. Remote deployment follows [[Vault Access|Vault Access]] and [[linux-remote-vault-access|Linux Remote Vault Access]].

`access configure` stores a provider route without changing the canonical provider. `access switch` verifies the new route from every other enabled source, atomically changes the registry, renders all enabled source machines, verifies fresh canonical connections, and rolls back on failure. `access render` runs from the registered primary and owns `~/.ssh/config.d/vault-machine-access.conf` on each enabled source. It produces canonical `ID`, diagnostic `ID-lan`, and diagnostic `ID-mesh` aliases with that source's fleet-shell identity and each target's selected provider while preserving unrelated SSH configuration. The default covers every enabled source; repeat `--target SOURCE_ID` to narrow a repair. Full provider rules live in [[machine-access-selection|Machine Access Selection]].

`access inspect` forces the requested configured provider for fresh SSH probes without switching the canonical alias. Its JSON output contains only sanitized provider, route, latency, and Tailscale direct/peer-relay/DERP evidence so WireGuard and Tailscale can be compared before a switch.

Wootbook VNC creates or reuses SSH control tunnel to loopback noVNC, checks HTTP health, then opens auto-connecting client. Runtime control socket and metadata live under `~/.cache/vault-machine/`, never vault. Occupied default port gets free local port; explicitly requested occupied port fails.

Mac mini uses native `vnc://` URL through same interface.

## Register future machine

1. Complete [[shared-onboarding-and-acceptance|Shared Onboarding and Acceptance]] and the selected `$infra-onboard-machine` role procedure.
2. Use `vault machine setup`; choose WireGuard or Tailscale explicitly. WireGuard requires an existing network, such as a deployed Kubernetes Helm chart.
3. Keep `enabled: false` until SSH identity, home, selected `-mesh` route, source-aware aliases, passwordless canonical reverse forwarding to the primary, reboot, and unattended acceptance pass.
4. Add `vnc` only after local-only endpoint or native Screen Sharing works.
5. Set `global_agents_eligible: true` only for reviewed personal Codex/Claude machines; explicit disabled-machine onboarding may provision configuration before enablement.
6. Run `vault machine list`, `vault machine status ID`, then `$infra-sync-code-workspaces` preview/doctor before enabling the machine.
7. Update [[_system/agents/skills/auto/_infrastructure/infra-code-folder-and-computer-topology/references/machine-requirements-and-topology|Machine Requirements and Topology]].
