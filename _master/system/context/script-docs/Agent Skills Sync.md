---
type: agent-reference
status: enabled
---
# Agent Skills Sync

For skill storage rules, read [[_master/agents/README-skills|README-skills]].

Preview or apply local coding-agent skill symlinks:

```bash
_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --dry-run
_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --apply
```

The script links global coding-agent skill targets such as `~/.codex/skills` and `~/.claude/skills` to this vault's `_master/agents/skills`. It also exposes each child of `_master/agents/manual-skills` and `_master/agents/gh-skills` as an individual symlink in `_master/agents/skills`, for example `_master/agents/skills/gws-gmail -> ../manual-skills/gws-gmail` and `_master/agents/skills/skybridge -> ../gh-skills/skybridge`. Existing symlinks at agent skill targets are reset on every apply run so stale or broken links are replaced. Non-symlink active skill directories are backed up after target-only skills are copied into the vault source.

Repo-local `.agents/skills` folders are real local directories for repo-scoped skills and are not managed by this global sync script. Repo-local `.claude/skills` should symlink to `../.agents/skills` so Claude and Codex can read the same repo-scoped skills.

Manual-only skills must include `agents/openai.yaml` with `policy.allow_implicit_invocation: false`. They are discoverable because their individual dirs are symlinked into `_master/agents/skills`, but that policy blocks implicit invocation. The sync script removes legacy manual-skill wrapper dirs and replaces them with direct symlinks.

When adding a new manual-only skill, do not create the `_master/agents/skills/<skill>` symlink by hand. Create `_master/agents/manual-skills/<skill>/SKILL.md`, add `_master/agents/manual-skills/<skill>/agents/openai.yaml`, then run:

```bash
_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --dry-run
_master/system/bootstrap/agents/ensure-agent-skill-symlinks.sh --apply
```

After apply, verify the generated link:

```bash
ls -l _master/agents/skills/<skill>
```

There is no `_master/agents/skills/agents/openai.yaml` config to edit; implicit invocation policy belongs in each manual skill's own `agents/openai.yaml`.

GitHub-managed skills live under `_master/agents/gh-skills` and should be installed with `gh skill --dir`:

```bash
GH_SKILLS_DIR="$(vault root)/_master/agents/gh-skills"

gh skill preview alpic-ai/skybridge skills/skybridge
gh skill install alpic-ai/skybridge skills/skybridge --dir "$GH_SKILLS_DIR"
gh skill install owner/repo packages/agent-skills/code-review --dir "$GH_SKILLS_DIR"

gh skill list --dir "$GH_SKILLS_DIR" --json skillName,sourceURL,version,path,pinned
gh skill update --dir "$GH_SKILLS_DIR" --dry-run
gh skill update --dir "$GH_SKILLS_DIR" --all
```

After installing or updating GitHub-managed skills, run this sync script. If a GitHub-managed skill name conflicts with an existing active or manual skill, the existing active skill wins and the GitHub-managed skill stays stored but undiscoverable until the conflict is resolved.

External dependency repos are managed separately by `vault deps`; see [[Dependency Repos]]. If a dependency repo contains a skill, `vault deps` creates a managed projection in `_master/agents/manual-skills` or `_master/agents/skills`, then this sync script links manual projections into the active skill surface. Do not copy external repos directly into `_master/agents`.
