# Managed Snippets

`vault snippets` keeps one canonical text source physically materialized between
minimal markers in files across registered Git repositories.

Configuration, marker format, and target-adoption rules live in
[[_system/local/snippets/README|Managed Snippets Config]].

```bash
vault snippets list
vault snippets list --json
vault snippets check
vault snippets check git-task-workflow --repo vault
vault snippets check --json
vault snippets sync --dry-run
vault snippets sync git-task-workflow --repo business --apply
```

`check` exits successfully only when every selected target matches its canonical
source. `sync` defaults to a unified-diff dry run. `--apply` changes only managed
block bodies, including when unrelated files or surrounding text are being edited;
it never stages, commits, pushes, or rewrites any other content.

Add marker pairs manually at deliberate document positions. Missing, partial,
malformed, duplicated, or nested markers stop the whole selected apply before any
file changes. A target changed concurrently during apply is also preserved and
reported instead of overwritten.
