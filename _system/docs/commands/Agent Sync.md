---
type: agent-reference
status: enabled
---
## Agent Sync

Sync converges the versions and sources currently declared by the primary; it never searches for newer upstream state. Use [[Agent Update]] or `$infra-update-fleet-dependencies` when the intent is to update versions, applications, or skill sources.

Read [[_system/agents/_package/docs/skills|Skill SOP]] for source, grouping, policy, dependency, and collision rules. The canonical command applies all selected changes by default:

```bash
ctx9-agents sync
ctx9-agents sync --dry-run
ctx9-agents sync --verify
```

With no component flags, sync applies approved direct dependencies, managed workspaces, workspace-built commands, skills, settings, and rendered instructions in that order. Select any subset by combining:

```bash
ctx9-agents sync --dependencies
ctx9-agents sync --workspaces
ctx9-agents sync --workspace-deps
ctx9-agents sync --skills
ctx9-agents sync --config
ctx9-agents sync --instructions
ctx9-agents sync --skills --instructions
```

`--skills` validates source policy and repository projections, rebuilds the Vault's generated symlink catalog, creates a portable point-in-time snapshot, and installs real skill directories under `~/.agents/skills` on the primary and every enabled target. Claude, Kilo, and Kilocode use per-skill aliases to those local copies. Unmanaged skills are preserved. Distribution remains independent of Vault access: code-only workers need no Vault, and remote clients never follow skill links into their mount.

`--dependencies` validates the complete typed registry at `_system/agents/_package/defaults/dependencies.json`, then installs and verifies required direct packages that match each machine's eligibility. The `sshfs` package uses `remote-vault-clients` eligibility and is not installed on code-only Linux workers. Sync also installs the value-free dependency, workspace-dependency, skill-source, secret-registry, and lifecycle-reference bundle under `~/.agents/package`. Coding tools, applications, providers, system capabilities, workspace commands, and optional services remain explicit registry entries routed to their lifecycle adapters. `--workspaces` reconciles exact checkouts from `_system/agents/_package/instance/fleet/workspaces.json`. `--workspace-deps` runs tracked repository-owned installers declared in `_system/agents/_package/instance/dependencies/selections.json` only after checkout safety checks. Verified target state lives under `~/.agents/state`; the primary collects sanitized evidence in `_system/agents/_package/generated/state/dependencies.lock.json`.

Component-only dependency runs update only their selected aggregate-lock section. For example, `--workspace-deps` refreshes workspace evidence while preserving previously confirmed direct-dependency evidence; an unselected section is never replaced with `null`.

Remote macOS workspace installers run as disposable `launchctl` jobs in the logged-in user's GUI bootstrap domain so native Keychain-backed prerequisites remain available. The worker uses owner-only temporary output files, records only sanitized installer evidence, removes the job afterward, and never moves a credential into SSH, argv, or Vault state. Linux installers continue in the authenticated SSH user context with Secret Service supplied by that machine.

`--config` distributes the authoritative value-free private instance registry into `~/.config/ctx9/agents`, plus Mattbook's `~/.codex/config.toml`, `~/.claude/settings.json`, and non-secret coding-agent service metadata such as the Langfuse instance descriptor. Machine-specific paths and safety overlays are rendered per target. Credentials remain machine-local and independently enrolled. Target-local Codex plugin and marketplace tables are preserved.

`--instructions` composes base, platform, role, machine, then explicitly registered Vault-authored skill fragments into `~/.codex/AGENTS.md` and keeps `~/.claude/CLAUDE.md` linked to it. The schema-v7 machine footer tells code-only Linux workers to stop, remote clients to use status/begin/finish without waiting for upload and avoid Vault Git, Gitless Mac hosts to remain Gitless, and the owner to commit the complete worktree currently visible without waiting for receipts. Workspace and third-party skills cannot register global instruction fragments.

Every run preflights all selected enabled targets before applying. Use repeatable `--target MACHINE_ID`, `--local-only`, or `--require-repo-sources` when narrowing scope or performing machine acceptance. Mac mini is disabled and is never selected. The Vault intentionally provides no agent-package aliases; one package has one CLI.

Source roots:

- `_system/agents/skills/auto`: implicit invocation allowed.
- `_system/agents/skills/manual`: explicit invocation only.
- `_system/agents/skills/github`: publisher metadata unchanged; optional `github_skills` modes in the skill-source registry apply only to distributed snapshots.
- `_system/agents/skills/projected`: generated tracked copies of explicitly configured repository skills.
- `_system/agents/skills/catalog`: generated Vault-local flat symlink catalog.

Use recursive `_lower-kebab` organizer folders. Sync validates every source and global collision before changing files, materializes selected `skill_projections` from the private repository topology, enforces auto/manual metadata, validates derived external projections against compact source choices, and rebuilds the catalog. It never projects every registered repository automatically or rewrites desired source configuration from generated paths.

After a skill apply, restart Codex or open a new task because the current task's skill catalog is cached.
