---
name: infra-sync-code-workspaces
description: Synchronizes registered Code workspaces and primary-owned Codex and Claude configuration across fleet machines. Use when the user asks to sync or refresh Code folders, prepare a new machine's workspaces, reconcile moved repositories, update agent settings on another machine, inspect workspace sync history, or verify remote workspace readiness.
---

# Infra · Sync Code Workspaces

Read `$infra-code-folder-and-computer-topology` and every prerequisite it requires before operating.

1. Load machines and `code_workspaces` from the topology skill's private registries. Keep missing or invalid configuration inactive.
2. Read [[workspace-sync-commands|Workspace Sync Commands]] for modes, command syntax, safety gates, and post-sync checks.
3. Read [[catalog-schema|Catalog Schema]] before changing catalog entries, profiles, machine filters, or clone policy.
4. Read [[state-and-reconciliation|State and Reconciliation]] before adopting source moves, relocating target checkouts, or inspecting run history.
5. Read [[agent-configuration-sync|Fleet Agent Configuration Sync]] before changing managed Codex or Claude files, eligibility, role overlays, or onboarding integration.
6. Read [[plugin-reconciliation|Fleet Codex Plugin Reconciliation]] before changing plugin inventory, marketplace handling, ownership state, or readiness reporting.
7. Preview first. Apply only after every selected target passes noninteractive SSH, Git, repository, agent-configuration, and plugin preflight.

Versioned global instructions live under `_system/agents/config`; `vault skills sync` renders them locally, while this workflow distributes the same per-machine render to eligible fleet targets.

Use `reconcile` for normal repeat synchronization and during onboarding. `bootstrap` remains available for first-run clone behavior; `refresh` updates existing clean workspaces; `doctor` verifies without mutation.

Never copy working trees, `.git`, credentials, sessions, plugin caches, marketplace snapshots, or the whole Code directory between machines. Never reset, stash, clean, force-update, switch an existing branch, change a remote, or use GUI access as an authentication fallback.
