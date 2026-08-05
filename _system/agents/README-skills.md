# Skill SOP

## Source And Catalog Contract

- Implicit source: `_system/agents/auto-skills/<_group>/<skill>/SKILL.md`
- Explicit-only source: `_system/agents/manual-skills/<_group>/<skill>/SKILL.md`
- GitHub-managed source: `_system/agents/gh-skills/<skill>/SKILL.md`
- Generated catalog: `_system/agents/skills/<skill>`
- Dormant storage: `_system/agents/skills-dump/<skill>/`
- Repo-local skills: `.agents/skills/`

`skills/` contains symlinks only. Put new or moved skills under auto, manual, or GH source, then sync. Never install content into generated catalog.

Organizer folders must use `_lower-kebab`, may nest recursively, and never contain `SKILL.md`. Skill folder must contain `SKILL.md`; folder basename must equal frontmatter `name`. Names must be globally unique.

## Big-Endian Naming

- Auto/manual skill: `<category>-<capability>`.
- Large third-party packs may use an approved root pack group and distinctive pack token, such as `_claude-seo/claude-seo-<capability>` or `_corey-marketing-skills/corey-<capability>`.
- Repository-local skill: `l-<capability>`.
- Never encode auto/manual invocation in the name.
- Use lowercase kebab-case and preserve the established descriptive capability slug. Do not shorten, reword, or reorder it merely to make names more compact. Keep the complete name under 64 characters.
- Keep `SKILL.md` as the filename. For shared skills, make the first H1 mirror the hierarchy, such as `# Infra · Update Fleet Coding Tools`. For repository-local skills, use the exact lowercase slug, such as `# l-hotfix-build-push`.
- Omit `interface.display_name` from `agents/openai.yaml`; Codex derives the user-facing label from the canonical frontmatter `name`, avoiding a second name to maintain.
- Prefix the existing descriptive capability slug with literal lowercase `l-`; do not add repository or category tokens.

| Folder | Token |
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

Shared skill sync validates the category prefix and big-endian H1 for auto/manual sources. GitHub-managed skills retain publisher names and titles.

Use a dedicated pack token when a large installed collection would otherwise flood autocomplete under a broad functional token. Choose a short, distinctive publisher or repository phrase; prefix every projected skill consistently; and preserve the upstream capability slug after that prefix. Register the pack group and title in `sync_skills.py` rather than weakening category validation.

A pack may expose one orchestrating root skill whose name exactly equals its pack token, such as `_claude-seo/claude-seo`. Register that exception explicitly; ordinary category skills still require `<token>-<capability>`.

## Skill And Config Separation

- Read [[_system/agents/README|Agents]], this file, and [[_system/local/README|Local Vault Data]] before adding or restructuring skill.
- Generic instructions, validation, scripts, code snippets, and reusable assets stay in skill folder.
- Changing domains, personal paths, machine facts, account/project IDs, repository locations, and deployment access details go in `_system/local/skills/<skill-name>/`.
- Use same basename as skill. Add config-folder `README.md`; use `private/` for private instance data.
- Config format may be Markdown, JSON, TOML, YAML, or another consumer-appropriate format.
- Skill must name required config, validate it before mutation, and explain setup when missing. Public-exported skill must remain understandable without private config.
- Before adding secrets or variables, read [[_system/local/env/README|Env Tooling]]. Add vault-owned keys to `_system/local/env/.env.base` first; values go in ignored `.env`. External-repository variables remain in owning repository env workflow.

## Invocation Policy

Sync preserves other `agents/openai.yaml` fields and enforces:

```yaml
policy:
  allow_implicit_invocation: true
```

for auto skills, and:

```yaml
policy:
  allow_implicit_invocation: false
```

for manual skills. Missing metadata gets created. GH metadata stays publisher-controlled.

## Sync

```bash
vault skills sync --dry-run
vault skills sync --apply
```

Sync performs full preflight before writes. Malformed sources, duplicate names, real content under generated catalog, or unmanaged global name collisions fail with repair instructions.

Apply:

- repairs dependency target/type metadata after manually moving a managed skill wrapper;
- removes stale catalog links and rebuilds changed links;
- maintains per-skill links under `~/.agents/skills`, `~/.claude/skills`, `~/.kilo/skills`, and `~/.kilocode/skills` when Kilocode exists;
- preserves unrelated global skills;
- removes vault-owned legacy `~/.codex/skills` whole-directory link;
- never copies discovery-target content into vault.

Existing tasks cache skill catalog. Start new task or restart Codex after sync.

## Dependency Skills

External repos stay under `~/Code/open_source/<repo-name>` and are configured in `_system/local/deps.json`.

Use `manual-skill` for explicit-only wrapper or `auto-skill` for implicit wrapper. Wrapper materializes upstream `SKILL.md` for Codex loader compatibility, projects supporting assets, and keeps invocation policy metadata vault-owned. The projection target basename overrides upstream frontmatter `name`; optional `title_override` replaces or inserts its first H1. `vault deps sync` reapplies these deterministic local overrides without changing upstream repositories.

```bash
vault deps sync --dry-run
vault deps sync --apply
vault skills sync --dry-run
```

Moving managed wrapper between source roots or `_group` folders then running skill sync updates `deps.json`, projection marker, target, type, and policy.

## GitHub-Managed Skills

```bash
GH_SKILLS_DIR="$(vault root)/_system/agents/gh-skills"
gh skill install owner/repo packages/agent-skills/code-review --dir "$GH_SKILLS_DIR"
gh skill update --dir "$GH_SKILLS_DIR" --all
vault skills sync --apply
```

GH publisher files remain untouched. Name conflict fails preflight.

## Repo-Local Skills

Repo-local `.agents/skills` stays real and outside global sync. Repo `.claude/skills` may link to `../.agents/skills`.
