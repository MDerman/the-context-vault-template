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

External repos stay under `~/Code/open_source/<repo-name>` and are configured in `_system/config/deps.json`.

Use `manual-skill` for explicit-only wrapper or `auto-skill` for implicit wrapper. Wrapper materializes upstream `SKILL.md` for Codex loader compatibility, projects supporting assets, and keeps invocation policy metadata vault-owned. `vault deps sync` refreshes materialized file.

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
