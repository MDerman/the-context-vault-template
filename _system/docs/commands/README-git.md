---
type: agent-reference
status: enabled
---
# Git Repository

This private vault uses normal Git for notes, code, and configuration. Binary files use Git LFS pointer format, but their bodies are intentionally local-only and are never uploaded to GitHub LFS.

## Layout

- Working files: the full iCloud Vault root shared by the primary and iCloud-participating worker Macs.
- Git owner: only the registered primary Mac has `~/.local/share/vault-git/Vault.git`, referenced by the shared `.git` file. Never sync that directory through iCloud.
- Worker rule: the shared `.git` pointer is deliberately dangling on every iCloud worker Mac. Workers never run Vault Git or keep Vault LFS objects.
- Host rule: never create or retain a separate Vault repository on a Mac worker, Linux machine, or other non-iCloud host.
- Local media objects: `~/.local/share/vault-git/Vault.git/lfs/objects`.
- Remote: private `https://github.com/MDerman/vault.git`.
- Primary branch: `master`.
- Media manifest: `_system/local/git-media-manifest.json`.

Every LFS pointer committed to Git contains original media SHA-256 and byte size:

```text
version https://git-lfs.github.com/spec/v1
oid sha256:<media-sha256>
size <media-bytes>
```

GitHub stores pointer text and path. It does not store media body. GitHub is therefore a notes, code, configuration, path, and checksum backup—not media recovery storage.

## Commit And Push

Stage the complete Vault worktree first. Git LFS clean filters convert configured binary files to pointers in index while leaving normal media bodies in worktree.

```bash
git add -A
vault git-media write-manifest
git add -A
vault git-media verify --index
git commit -m "Description"
git push
```

Every completed Vault task on the primary includes all tracked and untracked non-ignored changes, even when generated, incidental, incomplete, or created by another task. Before commit, regenerate and stage the manifest and verify the index. A Gitless Mac worker never uses this commit procedure; it waits for iCloud upload and hands the complete worktree to the primary. `vault git-media status` verifies committed state, local media availability, and custom hook installation where Vault Git exists.

Versioned `.githooks/pre-push` validates pointer and manifest state when `vault.media-mode=pointer-only`. It intentionally never runs `git lfs pre-push`, so normal `git push` cannot upload media bodies. Install versioned hooks with:

```bash
vault worker-sync install-hooks --apply
```

The primary requires local LFS bodies before push. An iCloud worker Mac receives media working files through iCloud and has no Vault LFS cache. Do not copy the primary cache, run `git lfs pull` against the worker Vault, or place any Git state in iCloud. Worker Mac media changes are reviewed, manifested, committed, and pushed only after they reach the primary. Public installs retain ordinary Git LFS behavior unless pointer-only mode is configured.

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

Do not run `git lfs prune` unless every required media body has another verified local backup. Keep the primary LFS object directory. Gitless Mac workers have no Vault Git cache; GitHub cannot restore the media bodies they receive through iCloud.

Public bootstrap remains separate: fresh public installs use ordinary Git LFS upload behavior unless pointer-only mode is explicitly configured. This private source-vault remote uses pointer metadata only.

See [[_system/docs/commands/Vault Git Sync|Vault Git Sync]], [[_system/docs/commands/Refresh|Refresh]], [[_system/docs/commands/Attachments|Attachments]], and [[_system/docs/obsidian/README|Obsidian]].
