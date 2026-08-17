---
type: agent-reference
status: enabled
---
# Machines

Private registry: `_system/local/skills/infra-code-folder-and-computer-topology/private/machines.json`. It is tracked in private vault Git and excluded from public bootstrap export. Registry owns stable machine ID, display name, enabled state, shell transport, SSH alias, home, optional IPv4 `wireguard_address`, personal agent-configuration eligibility, and optional VNC definition.

## Commands

```bash
vault machine list [--json]
vault machine init --id ID --display-name NAME --platform macos|linux --apply
vault machine register-worker --id ID --display-name NAME --platform macos|linux --ssh-alias ALIAS --home PATH [--repo-path PATH] --apply
vault machine identify ID --apply
vault machine status [NAME] [--json]
vault machine ssh NAME [-- COMMAND...]
vault machine vnc NAME [--no-open] [--local-port PORT]
vault machine vnc NAME --status
vault machine vnc NAME --stop
```

Registry schema v4 is the current writer/validator format and defines one primary plus worker roles and platforms. Consumers must validate the fields they use rather than reject a later additive schema version. Supported Vault operation uses `full` for the primary Mac and `icloud` for Gitless Mac workers. The primary uses clone-local `vault.machine-id`; a Gitless Mac worker uses mode-`0600` `~/.config/vault/machine-id`. Linux machines are code-repository workers only and do not receive a Vault checkout.

Missing registry does not prompt during public bootstrap. Initialize it manually with `vault machine init`, then register workers.

`register-worker` creates a disabled worker and a conventional private machine-note path. A macOS worker requires `--repo-path` and gets `checkout: icloud`, the full iCloud Vault working files, and no `git_dir`. A Linux worker records `vault_sync.enabled: false` and accepts no Vault path. Do not run Vault worker bootstrap for Linux machines; provision their ordinary code repositories through the code-workspace workflow instead. Keep every worker disabled until onboarding and reboot acceptance pass.

Wootbook VNC creates or reuses SSH control tunnel to loopback noVNC, checks HTTP health, then opens auto-connecting client. Runtime control socket and metadata live under `~/.cache/vault-machine/`, never vault. Occupied default port gets free local port; explicitly requested occupied port fails.

Mac mini uses native `vnc://` URL through same interface.

## Register future machine

1. Complete [[shared-onboarding-and-acceptance|Shared Onboarding and Acceptance]] and the selected `$infra-onboard-machine` role procedure.
2. Add unique lower-kebab `id`, confirmed values, and the machine's WireGuard IPv4 address when enrolled to the private registry.
3. Keep `enabled: false` until SSH identity, home, and route pass.
4. Add `vnc` only after local-only endpoint or native Screen Sharing works.
5. Set `global_agents_eligible: true` only for reviewed personal Codex/Claude machines; explicit disabled-machine onboarding may provision configuration before enablement.
6. Run `vault machine list`, `vault machine status ID`, then `$infra-sync-code-workspaces` preview/doctor before enabling the machine.
7. Update [[_system/agents/auto-skills/_infrastructure/infra-code-folder-and-computer-topology/references/machine-requirements-and-topology|Machine Requirements and Topology]].
