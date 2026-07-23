---
name: code-folder-and-computer-topology
description: Routes work involving multiple computers, primary/worker vault sync, remote access, Mac or Linux setup, code locations, repository placement, and fleet-wide agent deployment. Use before connecting to, configuring, enrolling, recovering, or locating code on any machine.
---

# Code Folder and Computer Topology

Read [[_system/agents/auto-skills/_infrastructure/code-folder-and-computer-topology/README-primary-worker-vault-sync|Primary and Worker Vault Sync]] before acting. It defines generic fleet roles, registry routing, checkout rules, and safe Git behavior.

- Read `_system/config/code-folder-and-computer-topology/README.md`, then `private/machines.json` and `private/repositories.json` when present. Missing registry means fleet automation stays inactive; show `vault machine init` guidance.
- Resolve current clone through local Git setting `vault.machine-id`. Never infer identity from hostname when automation changes remote machines.
- Read linked `private_notes_path` only when machine-specific facts matter.
- Treat registry roles as generic: one `primary`, zero or more `worker` machines.
- Resolve repositories by logical ID from private repository config. Do not hardcode personal checkout locations into other skills.
- Rediscover mutable facts before use; record confirmed private observations in linked private machine notes.
- Read owning repository `AGENTS.md` and `README.md` before repository changes.
- Keep project-specific operations in owning repository docs.
- Keep generic skill exported. Keep registry, private notes, addresses, aliases, and personal operational references excluded.
