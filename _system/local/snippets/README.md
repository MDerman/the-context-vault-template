# Managed Snippets Config

Canonical text snippets and their physical target locations for `vault snippets`.

## Layout

```text
_system/local/snippets/
  defaults.json            # portable snippet definitions and vault-local targets
  sources/<snippet>.md     # canonical literal text
  private/targets.json     # private external-repository targets by logical repo ID
```

External repository IDs resolve through
`_system/agents/_package/instance/fleet/workspaces.json`.
Repository ID `vault` always means the current vault root. Public bootstrap export
keeps defaults and sources but excludes `private/` targets.

## Target Markers

Put one exact, non-nested marker pair at the intended location in a physical UTF-8
text file:

```markdown
<!-- snippet:example:start -->
The complete materialized text remains physically present here.
<!-- snippet:example:end -->
```

Markers are invisible in rendered Markdown. Add and position new marker pairs
deliberately; the CLI never guesses an insertion point. Edit canonical source,
not a materialized block.

## Commands

```bash
vault snippets list
vault snippets check
vault snippets check git-task-workflow --repo vault
vault snippets sync --dry-run
vault snippets sync
```

`vault snippets sync` applies by default; pass `--dry-run` to preview. The
standalone Python implementation still accepts its internal compatibility
`--apply` flag. It validates every selected source, repository, target, and marker
before writing; changes only managed block bodies; preserves surrounding local
edits; and never stages, commits, or pushes.
If a target changes while apply is running, the write stops rather than replacing
the newer content.

After a cross-repository apply, inspect and commit each repository independently,
staging only its snippet target files.
