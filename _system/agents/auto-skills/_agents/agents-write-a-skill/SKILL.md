---
name: agents-write-a-skill
description: Create or update agent skills with the vault's required structure, big-endian names, progressive disclosure, and bundled resources. Use when a user wants to create, write, rename, or restructure a skill.
---

# Agents · Write a Skill

Before editing, read `_system/agents/README.md`, `_system/agents/README-skills.md`, and `_system/local/README.md`.

## Naming Contract

- Auto/manual source: `<category>-<capability>`.
- Large installed skill packs may use a dedicated root organizer and discovery token when the user wants deliberate autocomplete. Use `_distinctive-pack-name/<pack-token>-<upstream-capability>`; keep the upstream capability slug intact after the prefix.
- Repository-local `.agents/skills`: `l-<capability>`.
- Do not encode auto/manual invocation in the name; storage and `agents/openai.yaml` control it.
- Folder basename and frontmatter `name` must match exactly. The file remains `SKILL.md`.
- Use lowercase kebab-case. Capability slugs may be fully descriptive; preserve an established skill name instead of shortening, rewording, or reordering it merely for consistency.
- Keep the complete name under 64 characters. Shorten only when required by that limit or when the user explicitly requests a rename.
- Shared-skill H1 mirrors the hierarchy with title case and middle dots, such as `# Infra · Update Fleet Coding Tools`.
- Repo-local H1 is the exact lowercase slug, such as `# l-hotfix-build-push`; never render it as `L · ...`.
- Omit `interface.display_name` from `agents/openai.yaml`; Codex derives the label from frontmatter `name`.

| Source folder | Token |
|---|---|
| `_agents` | `agents` |
| `_claude-seo` | `claude-seo` |
| `_code` | `code` |
| `_corey-marketing-skills` | `corey` |
| `_creative` | `creative` |
| `_documents` | `documents` |
| `_finance` | `finance` |
| `_gws` | `gws` |
| `_infrastructure` | `infra` |
| `_marketing` | `marketing` |
| `_matt-p-skills` | `mp` |
| `_spreadsheets` | `spreadsheets` |
| `_swan-gtm-skills` | `swan-gtm` |
| `_vibe-marketer-skills-pack` | `vibe-marketer` |
| `_vault` | `vault` |
| `_video` | `video` |

For a repo-local skill, prefix the existing descriptive capability slug with literal lowercase `l-`. Do not add repository or category tokens. Example: `l-hotfix-build-push`.

For a large third-party pack, prefer a short publisher or repository phrase that users must intentionally type, rather than placing dozens of skills behind a broad token such as `marketing`. Apply the pack token to every skill consistently, mirror the pack title in each H1, and register the root organizer/token/title in `_system/agents/sync_skills.py`. Examples: `_claude-seo/claude-seo-audit` with `# Claude SEO · Audit`, and `_corey-marketing-skills/corey-analytics` with `# Corey Marketing Skills · Analytics`.

If the pack includes one orchestrating root skill, its name may exactly equal the pack token, such as `_claude-seo/claude-seo`. Register that root exception explicitly; do not loosen ordinary category naming.

## Authoring Process

1. Confirm the capability, trigger phrases, source location, category, and whether scripts or references are needed.
2. Create `SKILL.md`; add deterministic utilities under `scripts/` and optional detailed guidance one reference level deep.
3. Keep reusable behavior in the skill. Put personal paths, domains, IDs, machine facts, and changing instance values in `_system/local/skills/<skill-name>/`, with a `README.md` and private values under `private/`.
4. Before adding environment variables, follow `_system/local/env/README.md`.
5. Review examples and edge cases, then run `vault skills sync --dry-run` and `vault skills sync --apply` for shared skills.

## Minimal Template

```md
---
name: category-capability
description: What it does. Use when the user mentions concrete triggers or inputs.
---

# Category · Capability

## Quick Start

[Minimal working procedure]
```

Descriptions are the discovery surface: state the capability, then explicit trigger conditions. Keep them under 1024 characters and in third person.

Add scripts for repeatable validation, transformation, or operations with meaningful failure handling. Move optional detail out when `SKILL.md` would exceed 100 lines; references should be linked directly from it and remain one level deep.

## Validation Checklist

- [ ] Source folder maps to the category token.
- [ ] Large installed packs use one distinctive pack token consistently and do not crowd a broad functional prefix.
- [ ] Existing descriptive capability wording is preserved unless the user explicitly requested different wording.
- [ ] Repo-local folder, name, and H1 use the same literal `l-<capability>` slug.
- [ ] Folder basename equals frontmatter `name`.
- [ ] Shared H1 mirrors its hierarchy; repo-local H1 exactly matches its lowercase slug.
- [ ] `agents/openai.yaml` omits `interface.display_name`.
- [ ] Description states capability and triggers.
- [ ] `SKILL.md` is under 100 lines and contains no time-sensitive instance facts.
- [ ] Config, private data, and environment variables follow their owning SOPs.
- [ ] Scripts are executable/tested where applicable; examples are concrete.
- [ ] Shared skill sync dry-run is clean after apply.
