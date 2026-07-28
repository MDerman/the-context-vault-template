---
type: agent-reference
status: enabled
---
# Git Repository

This private vault uses normal Git for notes, code, and configuration. Binary files use Git LFS pointer format, but their bodies are intentionally local-only and are never uploaded to GitHub LFS.

## Layout

- Worktree: vault root.
- External Git directory: `~/.local/share/vault-git/Vault.git`.
- Local media objects: `~/.local/share/vault-git/Vault.git/lfs/objects`.
- Remote: private `https://github.com/MDerman/vault.git`.
- Primary branch: `master`.
- Media manifest: `_system/config/git-media-manifest.json`.

Every LFS pointer committed to Git contains original media SHA-256 and byte size:

```text
version https://git-lfs.github.com/spec/v1
oid sha256:<media-sha256>
size <media-bytes>
```

GitHub stores pointer text and path. It does not store media body. GitHub is therefore a notes, code, configuration, path, and checksum backup—not media recovery storage.

## Commit And Push

Stage changed files first. Git LFS clean filters convert configured binary files to pointers in index while leaving normal media bodies in worktree.

```bash
git add <paths>
vault git-media write-manifest
git add _system/config/git-media-manifest.json
vault git-media verify --index
git commit -m "Description"
git push
```

Before commit, verify index when needed by running `vault git-media write-manifest`, staging manifest, then committing. `vault git-media status` verifies committed state, local media availability, and custom hook installation.

Versioned `.githooks/pre-push` validates pointer and manifest state when `vault.media-mode=pointer-only`. It intentionally never runs `git lfs pre-push`, so normal `git push` cannot upload media bodies. Install versioned hooks with:

```bash
vault worker-sync install-hooks --apply
```

Primary requires local LFS bodies before push. Pointer-only workers inherit primary-verified manifest state for non-media commits, avoiding hydration of every pointer blob in a partial clone. Worker media changes are rejected unless local bodies exist and `vault.media-write-authorized=true` is explicitly set; authorized media changes receive full pointer/manifest/body verification. Public installs retain ordinary Git LFS behavior unless pointer-only mode is configured.

Do not run `git lfs push`. Do not replace hook with `git lfs install --force`.

## Clone Pointer Metadata

Clone without requesting absent media bodies:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/MDerman/vault.git
```

Clone contains full normal Git files plus tiny media pointers. `git lfs pull` cannot restore media because GitHub does not hold media objects.

To restore full vault elsewhere, copy media bodies or local LFS object store from separate local backup, then verify:

```bash
vault git-media verify --ref HEAD --full-local-hash
```

## Media Changes

Adding or changing configured binary file creates new local LFS object and pointer. Regenerate manifest before commit. Removing media removes pointer from next manifest but does not automatically delete local LFS object.

Manifest is deterministic JSON sorted by path. Each entry records path, actual media SHA-256, logical byte size, and normal-Git pointer blob ID. Filenames containing spaces or newlines remain escaped safely.

## Maintenance And Recovery

`vault git-maintenance` compacts normal Git history. Local archive refs keep referenced commit history alive. Git bundle does not contain LFS media bodies.

Do not run `git lfs prune` unless every required media body has another verified local backup. Keep local LFS object directory with worktree media.

Public bootstrap remains separate: fresh public installs use ordinary Git LFS upload behavior unless pointer-only mode is explicitly configured. This private source-vault remote uses pointer metadata only.

See [[_system/docs/commands/Vault Git Sync|Vault Git Sync]], [[_system/docs/commands/Refresh|Refresh]], [[_system/docs/commands/Attachments|Attachments]], and [[_system/docs/obsidian/README|Obsidian]].
