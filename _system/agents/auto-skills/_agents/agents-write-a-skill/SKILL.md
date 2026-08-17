---
name: agents-write-a-skill
description: Creates or updates agent skills to match the Vault's authoring standards. Use when the user asks to create, write, rename, reorganize, thin, or improve a skill or its supporting references, scripts, assets, or discovery description.
---

# Agents · Write a Skill

Before editing, read `_system/agents/README.md`, `_system/agents/README-skills.md`, and `_system/local/README.md`.

## Workflow

1. Define the user-facing capability and the concrete ways a user would ask for it.
2. Read [[skill-authoring-method|Skill Authoring Method]] for description, structure, progressive-disclosure, and validation standards.
3. Choose auto, manual, or repository-local ownership from the canonical Skill SOP. Preserve established names unless the user requests a rename or the name is invalid.
4. Keep `SKILL.md` as a thin routing and execution contract. Split distinct platforms, approaches, or long procedures into directly linked references when that improves clarity.
5. Put deterministic utilities in `scripts/`, reusable files in `assets/`, and changing personal facts in `_system/local/skills/<skill-name>/`.
6. For repository-owned skills or global projections, read [[repo-skill-projections|Repository Skill Projections]].
7. Test applicable scripts, then run `vault skills sync --dry-run` and `vault skills sync --apply` for shared or projected skills.

Follow explicit user structure requests. Otherwise use judgment: prefer fewer, clearer files, but do not keep multiple substantial workflows in one `SKILL.md` merely to avoid a reference.
