---
type: agent-reference
status: enabled
---

## Code Workspace Catalog Schema

The private topology `repositories.json` retains its existing `repositories` map and may add a separate `code_workspaces` object:

```json
{
  "code_workspaces": {
    "schema_version": 1,
    "default_profile": "core",
    "defaults": {
      "clone_mode": "partial",
      "profiles": ["core"],
      "machines": ["*"],
      "codex_project_root": "."
    },
    "entries": {
      "example": {
        "path": "~/Code/example",
        "discovery": "repository",
        "remote": "git@github.com:owner/example.git"
      },
      "group": {
        "path": "~/Code/group",
        "discovery": "recursive"
      }
    }
  }
}
```

### Fields

- `schema_version`: must be `1`.
- `default_profile`: profile used when the command receives no `--profile` or `--entry`.
- `defaults`: values inherited by every entry.
- `entries.<id>.path`: source path under the executing user's Code root; target keeps the same Code-relative path.
- `discovery`: `repository` for one checkout, or `recursive` for every physical Git checkout below the path. Dynamic `--path` uses `auto`.
- `remote`: optional canonical remote for `repository`; required to bootstrap when the source checkout is absent. Recursive members discover their own remotes.
- `profiles`: catalog profiles that select the entry.
- `machines`: target machine IDs or `"*"`.
- `clone_mode`: `partial` or `full`; partial adds `git clone --filter=blob:none` and keeps full history.
- `codex_project_root`: `.` by default. A relative subdirectory may identify the folder to save as the Codex project.
- `required`: when true, missing source paths or empty recursive discovery are reported prominently.

Paths outside the configured source Code root, overlapping parent/child repositories, credential-bearing remotes, duplicate target-relative paths, and one canonical remote assigned to multiple desired paths are invalid. Recursive discovery skips known dependency, build, cache, `.workspace-sync`, symlinked, and already-discovered repository subtrees; pass an excluded directory itself with `--path` when it intentionally owns repositories. A recursive entry is intentionally source-observed; use exact entries with `remote` when bootstrap must work without that source collection being present.

When a thin workspace repository contains ignored child Git repositories and owns its own manifest/sync command, keep that hierarchy in one ownership layer. Do not select both the parent and its children in this catalog. If an installed local Codex marketplace lives in one child, select that exact child here so plugin reconciliation can guarantee its target-local path, and leave the remaining workspace membership to the owning workspace manifest.

For exact entries, `remote` is also the stable identity used to detect a uniquely moved source checkout. Applying with `--adopt-source-layout` updates that entry's `path` and a matching same-ID logical repository path; it never rewrites the remote or changes recursive entries.
