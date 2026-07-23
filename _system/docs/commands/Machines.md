---
type: agent-reference
status: enabled
---
# Machines

Private registry: `_system/config/code-folder-and-computer-topology/private/machines.json`. It is tracked in private vault Git and excluded from public bootstrap export. Registry owns stable machine ID, display name, enabled state, shell transport, SSH alias, home, global-AGENTS eligibility, and optional VNC definition.

## Commands

```bash
vault machine list [--json]
vault machine init --id ID --display-name NAME --platform macos|linux --apply
vault machine register-worker --id ID --display-name NAME --platform macos|linux --ssh-alias ALIAS --home PATH --repo-path PATH --apply
vault machine identify ID --apply
vault machine status [NAME] [--json]
vault machine ssh NAME [-- COMMAND...]
vault machine vnc NAME [--no-open] [--local-port PORT]
vault machine vnc NAME --status
vault machine vnc NAME --stop
```

Registry schema v3 defines one primary, worker roles/platforms, and worker vault-sync settings. `vault.machine-id` is clone-local Git configuration.

Missing registry does not prompt during public bootstrap. Initialize it manually with `vault machine init`, then register workers.

Wootbook VNC creates or reuses SSH control tunnel to loopback noVNC, checks HTTP health, then opens auto-connecting client. Runtime control socket and metadata live under `~/.cache/vault-machine/`, never vault. Occupied default port gets free local port; explicitly requested occupied port fails.

Mac mini uses native `vnc://` URL through same interface.

## Register future machine

1. Complete [[_system/agents/auto-skills/_infrastructure/code-folder-and-computer-topology/references/new-mac-or-linux-machine-setup|New Mac or Linux Machine Setup]].
2. Add unique lower-kebab `id` and confirmed values to private registry.
3. Keep `enabled: false` until SSH identity, home, and route pass.
4. Add `vnc` only after local-only endpoint or native Screen Sharing works.
5. Set `global_agents_eligible: true` only for personal reviewed Codex machines.
6. Run `vault machine list`, `vault machine status ID`, global AGENTS deployment preview, then enable machine.
7. Update [[_system/agents/auto-skills/_infrastructure/code-folder-and-computer-topology/references/machine-requirements-and-topology|Machine Requirements and Topology]].
