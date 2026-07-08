# Skill SOP

## Paths

- Active shared skills: `_master/agents/skills/<skill>/SKILL.md`
- Manual-only skills: `_master/agents/manual-skills/<skill>/SKILL.md`
- GitHub-managed skills: `_master/agents/gh-skills/<skill>/SKILL.md`
- Dormant skills: `_master/agents/skills-dump/<skill>/`
- Repo-local skills: `.agents/skills/`

## Active Skills

Put shared, implicitly discoverable skills in `_master/agents/skills/<skill>/`.

Use active skills only for reusable agent capability with clear trigger rules. Put ordinary vault procedures in folder READMEs instead.

## Manual-Only Skills

Manual-only skills live in `_master/agents/manual-skills/<skill>/` and are exposed as symlinks in `_master/agents/skills/<skill>`.

Each manual-only skill must include:

```yaml
policy:
  allow_implicit_invocation: false
```

at `_master/agents/manual-skills/<skill>/agents/openai.yaml`.

Do not create `_master/agents/skills/<skill>` symlinks by hand.

## GitHub-Managed Skills

Use `_master/agents/gh-skills/` for skills installed with GitHub CLI `gh skill`.

Install or update skills in that folder, then run the sync script so Codex and Claude discover them through `_master/agents/skills`.

```bash
GH_SKILLS_DIR="$(vault root)/_master/agents/gh-skills"

gh skill preview alpic-ai/skybridge skills/skybridge
gh skill install alpic-ai/skybridge skills/skybridge --dir "$GH_SKILLS_DIR"

gh skill install owner/repo packages/agent-skills/code-review --dir "$GH_SKILLS_DIR"

gh skill list --dir "$GH_SKILLS_DIR" --json skillName,sourceURL,version,path,pinned
gh skill update --dir "$GH_SKILLS_DIR" --dry-run
gh skill update --dir "$GH_SKILLS_DIR" --all
```

If a GitHub-managed skill name conflicts with an existing active or manual skill, the existing active surface wins and sync logs a skip.

## Sync

Preview, then apply:

```bash
_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --dry-run
_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --apply
```

The sync script:

- links global agent skill targets such as `~/.codex/skills` and `~/.claude/skills` to `_master/agents/skills`;
- exposes manual skills as individual symlinks under `_master/agents/skills`;
- exposes valid GitHub-managed skills from `_master/agents/gh-skills` as individual symlinks under `_master/agents/skills`;
- backs up replaced non-symlink target paths under `_master/agents/backups/skill-sync`.

Root agent file symlinks are separate:

```bash
python3 _master/system/bootstrap/agents/ensure-agent-file-symlinks.py --root . --dry-run
```

That script ensures `CLAUDE.md -> AGENTS.md`, `.agents/skills` is a real repo-local directory, and `.claude/skills -> ../.agents/skills`.

## Dependency Repos

External repos stay under `~/Code/open_source/<repo-name>` and are tracked in `_master/system/config/deps.json`.

If an external repo contains a skill, add a managed projection in `deps.json`; do not copy the repo into the vault. After projection changes:

```bash
vault deps sync --dry-run
vault deps sync --apply
```

`vault deps sync --apply` rebuilds projections and runs skill symlink sync when skill projections changed.
