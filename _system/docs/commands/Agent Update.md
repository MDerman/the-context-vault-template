---
type: agent-reference
status: enabled
---
## Agent Update

`ctx9-agents update` is the central approved fleet update operation. It resolves newer versions or source revisions within declared policy, preflights every selected machine, applies the immutable plan, runs normal agent sync once, verifies, and records factual state only after acceptance.

```bash
ctx9-agents update --dry-run
ctx9-agents update
ctx9-agents update --verify
```

The command applies by default. `--dry-run` may resolve upstream versions but writes nothing. `--verify` neither resolves newer state nor writes locks.

Selectors may be combined:

```bash
ctx9-agents update --dependencies
ctx9-agents update --coding-tools
ctx9-agents update --skills
ctx9-agents update --workspace-deps
ctx9-agents update --vault-dependencies
```

`--dependencies` selects approved agent packages, applications, access providers, system capabilities, and optional services. `--coding-tools` uses one exact T3 nightly version and preserves Codex, Claude Code, and OpenCode installation provenance. `--skills` updates only configured external and GitHub-managed sources, then projects and distributes point-in-time copies. `--workspace-deps` is transitional and reconciles only commands declared by logical workspace ID. `--vault-dependencies` independently updates the public Vault/bootstrap manifest on the full-Vault machine.

Restrict one skill-source operation with a repeatable source selector:

```bash
ctx9-agents update --skills --skill-source frontend-slides --dry-run
ctx9-agents update --skills --skill-source frontend-slides
ctx9-agents update --skills --skill-source gh:skybridge
```

Cloned sources use the repository ID from `skill-sources.json`. GitHub-managed sources use `gh:<skill-name>`. The updater requires a clean checkout on its configured branch, exact origin and upstream, and a current or fast-forward-only relationship. Dirty, ahead, divergent, detached, wrong-branch, wrong-upstream, and remote-mismatched sources block before mutation. It never resets, stashes, switches branches, or forces.

After source acceptance, the command rebuilds managed projections without fetching again, materializes repository-relative GitHub symlinks as portable content, validates relative references, distributes point-in-time copies, verifies every selected machine, and writes `_system/agents/_package/generated/state/skills.lock.json`. That lock records observed source revisions, checkout eligibility, projection digests, GitHub-managed versions, and fleet snapshot digests. It is factual evidence only and never controls desired state.

`_system/local/dependencies.lock.json` has a separate public-release purpose. Public bootstrap and upgrade may reproduce the skill-source revisions captured by a particular Vault release. Routine `ctx9-agents update --skills` never consumes those pins. This separation permits the private fleet package to move sources forward without changing a published bootstrap contract.

Use repeatable `--target MACHINE_ID` or `--local-only` to narrow the operation. An explicit target updates only the named target; the default includes the primary and every enabled eligible worker. Normal sync may still inspect the primary as its source. Disabled machines are rejected and never appear in the default target set.

Update differs from [[Agent Sync]]: sync converges current declared state and never seeks a newer upstream version. Update resolves approved newer state, applies typed adapters, calls sync, and verifies. Missing required direct packages remain sync-owned; update never installs software merely discovered on a machine. A second identical accepted update reports current state and makes no source, projection, or target changes.

Every report distinguishes updated, already current, absent, lifecycle-owned, manual, blocked, and failed items. A manual or failed item prevents an aligned-fleet result. Major OS upgrades, firmware, authentication, credential rotation, and production deployment are separate operations.
