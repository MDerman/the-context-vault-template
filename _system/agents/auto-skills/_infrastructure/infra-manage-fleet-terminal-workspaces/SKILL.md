---
name: infra-manage-fleet-terminal-workspaces
description: Configures, audits, repairs, or explains fleet terminal environments across Warp, cmux, tmux, workmux, btop, Starship, terminal profiles, saved workspaces, reconnect behavior, and retired agent notifications. Use for terminal workspace setup, Warp or cmux layout changes, persistent remote shells, T3 SSH terminal integration, workmux recovery, or terminal-profile deployment on registered machines.
---

# Infra · Manage Fleet Terminal Workspaces

Read [[cmux-tmux-terminal-workspaces|Warp, cmux, and tmux Terminal Workspaces]] for architecture, deployment, verification, persistence, and rollback.

- Use `$infra-code-folder-and-computer-topology` to load the canonical machine registry and private execution-chain observations. Do not duplicate machine facts in this skill.
- Read [[README-warp-cmux-execution-chain|Warp and cmux Execution Chain]] when explaining machine boundaries or frontend routing.
- Run `scripts/sync_terminal_profiles.py` for tmux, btop, Starship, workmux, and managed profile deployment.
- Run `scripts/configure_warp_machine_workspaces.py` and `scripts/configure_cmux_machine_workspaces.py` for primary-host layouts.
- Keep every controller dry-run by default; use `--apply` only after reviewing exact targets and use `--verify` afterward.
- Read [[README-workmux-notifications|Workmux Agent Notifications]] before touching notification hooks. Notifications remain retired and disabled unless the user explicitly asks to re-enable them.
- During new-machine work, return gate status to `$infra-onboard-machine`; this skill does not own machine registration, WireGuard, SSH enrollment, or registry enablement.
