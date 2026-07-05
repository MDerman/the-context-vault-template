---
type: agent-reference
status: enabled
---
# Agent Skills Sync

Preview or apply local coding-agent skill symlinks:

```bash
_master/system/bootstrap/sync-agent-skills.sh --dry-run
_master/system/bootstrap/sync-agent-skills.sh --apply
```

The script links global coding-agent skill targets such as `~/.codex/skills` and `~/.claude/skills` to this vault's `_master/agents/skills`. It also links convenience `skill-packs` targets to `_master/agents/skill-packs` and mirrors direct skill-pack children into `_master/agents/skills/manual` as symlinks. Existing symlinks at those targets are reset on every apply run so stale or broken links are replaced. Non-symlink directories are backed up after target-only skills are copied into the vault source.

Repo-local `.agents/skills` folders are real local directories for repo-scoped skills and are not managed by this global sync script. Repo-local `.claude/skills` should symlink to `../.agents/skills` so Claude and Codex can read the same repo-scoped skills.

Manual-only skill packs must include `agents/openai.yaml` with `policy.allow_implicit_invocation: false` so `$skill` works without implicit triggering.

External dependency repos are managed separately by `vault deps`; see [[Dependency Repos]]. If a dependency repo contains a skill, `vault deps` creates a managed wrapper in `_master/agents/skill-packs` or `_master/agents/skills`, then this sync script exposes it to agents. Do not copy external repos directly into `_master/agents`.
