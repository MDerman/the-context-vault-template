---
name: infra-code-folder-and-computer-topology
description: Discovers the current clone, registered primary and worker machines, connection routes, repository locations, and code-placement policy without provisioning machines. Use when identifying a machine, finding where code lives or belongs, inspecting fleet topology, resolving an SSH or Screen Sharing route, or supplying topology facts to another infrastructure workflow.
---

# Infra · Code Folder and Computer Topology

Read [[README-primary-worker-vault-sync|Primary and Worker Vault Coordination]] for fleet roles, registry routing, Vault host boundaries, and safe Git behavior. Vault work is Mac/iCloud-only; treat Linux machines as code-repository workers and follow [[README-vault-host-boundary|Vault Host Boundary]].

- Read `_system/local/skills/infra-code-folder-and-computer-topology/README.md`, then `private/machines.json` and `private/repositories.json` when present. If the registry is missing, keep fleet automation inactive and show `vault machine init` guidance.
- Resolve primary identity through local Git setting `vault.machine-id`. Resolve a Gitless iCloud worker through `~/.config/vault/machine-id`. Never infer identity from hostname when another workflow may mutate remote machines.
- Read a machine's linked `private_notes_path` only when machine-specific facts matter.
- Treat registry roles as generic: one `primary`, zero or more `worker` machines.
- Resolve repositories by logical ID from private repository config. Do not hardcode personal checkout locations into other skills.
- Treat each registry `ssh_alias` as the stable identity consumed by Codex, T3, terminal, sync, and update workflows. Route-specific `-lan`, `-wg`, hostnames, and addresses are diagnostic overrides and must not become durable application identities.
- Treat optional `skill_projections` as an explicit allowlist consumed by `vault skills sync`; never infer projections for every registered repository.
- Rediscover mutable facts before use and record confirmed private observations in the linked private machine note when the user asks for documentation changes.
- Read [[README-machine-runtime-state|Machine Runtime State]] before assigning machine-local logs, state, locks, caches, or runtime files.
- Read the owning repository `AGENTS.md` and `README.md` before repository changes; keep project-specific operations in that repository.
- For repeat or onboarding synchronization of Code repositories and personal Codex/Claude configuration from the primary, use `$infra-sync-code-workspaces`; topology supplies facts but performs no deployment.
- For onboarding, rebuilding, replacing, recovering, or accepting any machine role, use `$infra-onboard-machine`.
- For Warp, cmux, tmux, workmux, terminal profiles, or terminal notifications, use `$infra-manage-fleet-terminal-workspaces`.
- Keep this skill generic and exported. Keep registries, private notes, addresses, aliases, and personal operational references excluded.
