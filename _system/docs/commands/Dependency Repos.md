---
type: agent-reference
status: enabled
---
# Dependency Repositories

External agent skill sources are desired agent-package configuration, not Vault dependencies. Their private source is:

```text
_system/agents/_package/instance/skills/sources.json
```

The registry stores public repository identity, accepted ref, enabled state, selected source, group, name and invocation mode. It does not store home paths, clone roots, Git transport, instruction fragments or generated targets. Profile configuration owns Git transport. Each machine checkout derives beneath `<resolved Code root>/open_source`.

Validate and inspect through the standalone resolver:

```bash
ctx9-agents config validate
ctx9-agents config get skills.sources
```

In the private source Vault, use the central update workflow:

```bash
ctx9-agents update --skills --dry-run
ctx9-agents update --skills
ctx9-agents sync --skills --dry-run
ctx9-agents sync --skills
```

Update accepts only clean, correctly configured, fast-forwardable sources, materializes portable repository-relative symlinks, rebuilds allowlisted projections, distributes point-in-time copies and records factual state under `_system/agents/_package/generated/state`. Disabled sources remain desired configuration but are not fetched or rebuilt.

Public Vault install, upgrade and release never read this registry or clone these repositories. Public agent export includes only skills explicitly reviewed in its independent allowlist. Neither product infers public eligibility from a source folder.

Executable packages belong in `_system/agents/_package/defaults/dependencies.json`; personal selections and workspace-built commands belong in `instance/dependencies/selections.json`. External skill sources never install arbitrary executable hooks.
