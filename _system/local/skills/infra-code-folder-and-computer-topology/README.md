## Code Folder And Computer Topology Config

Private fleet config owned by `infra-code-folder-and-computer-topology` and consumed by vault machine commands, `infra-onboard-machine`, `infra-sync-code-workspaces`, and `infra-manage-fleet-terminal-workspaces`.

- `private/machines.json`: machine registry, sync roles, access routing, optional `wireguard_address`, terminal workspace profiles, and eligibility for primary-owned personal agent configuration. Deployment belongs to `$infra-sync-code-workspaces`, not topology.
- `private/My Machines/`: mutable per-machine observations.
- `private/Machine Conventions/`: role-based machine convention folders and same-named notes.
- `private/repositories.json`: logical repository IDs, local paths, access method, and optional env loader. Its backward-compatible `code_workspaces` section owns reviewed Code sync roots, profiles, machine selection, clone policy, and Codex project roots for `infra-sync-code-workspaces`.
- A repository's optional `skill_projections` list selects individual `.agents/skills/l-*` sources for tracked global projection. Each entry has a repo-relative `source` and `auto` or `manual` mode; registration alone never projects a repo.
- `private/fleet-observations.md`: mutable current fleet observations and operational history.
- `private/remote-access-prerequisites.md`: current private network and operator-machine access details.
- `private/README-warp-cmux-execution-chain.md`: current terminal execution chain and verification observations.
- `private/retired-syncthing-code-folder.md`: retired replication recovery paths and history.
- Machine-local Code workspace reconciliation history lives under `~/Code/.workspace-sync/`; the private registry here remains authoritative desired fleet configuration. See [[_system/agents/auto-skills/_infrastructure/infra-code-folder-and-computer-topology/README-machine-runtime-state|Machine Runtime State]].
- [[_system/local/skills/infra-code-folder-and-computer-topology/Mac Startup/README|Mac Startup]]: portable defaults and private per-machine startup opt-ins.

All files under `private/` stay in private vault Git and are excluded from public bootstrap export. Generic setup and recovery procedures stay in skill folder.

Terminal controllers copy machine registry to `~/.config/workmux/machines.json` with mode `0600`; deployed cmux/Warp helpers read that runtime copy instead of embedding aliases or home paths.
