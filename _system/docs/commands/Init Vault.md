---
type: agent-reference
status: enabled
---
# Init Vault

Run first-time setup after placing a fresh/exported vault in iCloud:

```bash
_system/bootstrap/init_vault.sh
```

Dry-run the default/configured setup:

```bash
_system/bootstrap/init_vault.sh --dry-run --non-interactive
```

The init script installs/checks dependencies, prompts for context folders, runs bootstrap, ensures agent symlinks, installs the `vault` command, and optionally sets up Git/LFS with the Git directory outside iCloud. Fresh Git repositories are initialized directly under `~/.local/share/vault-git/<vault-name>.git`; existing in-vault Git directories are moved there before Git hooks or index updates run.
User Git/LFS is off by default; pass `--enable-git` when intentionally creating a personal vault repository.

Context-folder answers are stored in:

```text
_system/bootstrap/init-vault-config.json
```

The public starter vault begins with three template folders:

```text
personal
personal-brand
business
```

When setup renames any of them, it runs the same structured rename engine as:

```bash
vault folder rename business studio --dry-run
vault folder rename business studio
```

The rename command moves the folder and rewrites structured references such as paths, Obsidian links, plugin JSON paths, frontmatter identity values, and `@context` tokens. It leaves ordinary prose alone, so sentences like "grow your business" are not blindly rewritten.

Register a context folder that already exists, for example after Relay shares it into this vault:

```bash
cd "$(vault root)"
vault folder register business
```

`register` is an alias for the create/register path. It preserves the existing folder contents, reads status, context type, and content settings from the context folder note, regenerates context-aware Obsidian bases/templates, and refreshes agent symlinks.

Unregister a context folder while keeping its files:

```bash
vault folder unregister business --dry-run
vault folder unregister business
```

Unregister writes `context_registered: false` to folder note, then regenerates vault views so Dashboard and default script discovery ignore it. Re-register later with `vault folder register business`.

Remove a context folder from disk:

```bash
vault folder remove business --dry-run
vault folder remove business --apply
```

`remove` is dry-run by default and only deletes files with `--apply`.

Root `AGENTS.md` is direct-edit source of truth. Agent setup ensures symlinks with:

```bash
python3 _system/bootstrap/agents/ensure-agent-file-symlinks.py --root . --dry-run
```
