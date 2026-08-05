---
name: infra-code-folder-and-computer-topology
description: Discovers the current clone, registered primary and worker machines, connection routes, repository locations, and code-placement policy without provisioning machines. Use when identifying a machine, finding where code lives or belongs, inspecting fleet topology, resolving an SSH or Screen Sharing route, or supplying topology facts to another infrastructure workflow.
---

# Infra · Code Folder and Computer Topology

Read [[README-primary-worker-vault-sync|Primary and Worker Vault Coordination]] for fleet roles, registry routing, checkout rules, and safe Git behavior.

- Read `_system/local/skills/infra-code-folder-and-computer-topology/README.md`, then `private/machines.json` and `private/repositories.json` when present. If the registry is missing, keep fleet automation inactive and show `vault machine init` guidance.
- Resolve the current clone through local Git setting `vault.machine-id`. Never infer identity from hostname when another workflow may mutate remote machines.
- Read a machine's linked `private_notes_path` only when machine-specific facts matter.
- Treat registry roles as generic: one `primary`, zero or more `worker` machines.
- Resolve repositories by logical ID from private repository config. Do not hardcode personal checkout locations into other skills.
- Rediscover mutable facts before use and record confirmed private observations in the linked private machine note when the user asks for documentation changes.
- Read the owning repository `AGENTS.md` and `README.md` before repository changes; keep project-specific operations in that repository.
- For adding, rebuilding, enrolling, or replacing a machine, use `$infra-onboard-machine`.
- For a worker Mac, use `$infra-onboard-worker-mac` in addition to generic onboarding.
- For Warp, cmux, tmux, workmux, terminal profiles, or terminal notifications, use `$infra-manage-fleet-terminal-workspaces`.
- Keep this skill generic and exported. Keep registries, private notes, addresses, aliases, and personal operational references excluded.
