---
type: agent-reference
status: enabled
---
## Vault Git coordination

The registered `vault_git.owner_machine_id` Mac is the sole Git owner for the shared iCloud Vault. It keeps machine-local Git metadata at `~/.local/share/vault-git/Vault.git`; iCloud carries only working files and the shared `.git` pointer. Every iCloud worker Mac is file-only. A registered `remote-sshfs` Linux client may read and edit the host's complete worktree through its exact mount, but the same pointer remains unresolved there and Vault Git fails by design. Code-only Linux hosts do not run Vault tasks.

This removes the split-brain condition created when working files and separate Git indexes advanced independently. No worker or remote client may create Vault Git metadata, a Vault LFS cache, `~/Code/vault`, a sparse checkout, or a Git proxy.

### Commands

Run Git commands only on the primary Mac:

```sh
vault git-preflight
vault worker-sync install-hooks
```

Run worker bootstrap from the primary:

```sh
vault worker-sync bootstrap WORKER_ID
vault worker-sync bootstrap WORKER_ID --provision-disabled
```

For a Mac worker registered with `checkout: icloud`, bootstrap requires a complete iCloud Vault with no dataless items. It validates the shared `.git` pointer and guarantees it is dangling. If the pointer resolves to the exact legacy worker location `~/.local/share/vault-git/Vault.git`, apply moves that directory recoverably to `~/.Trash/Vault.git-disabled-<timestamp>-<pid>`. Any unexpected live target is refused. Bootstrap then writes `~/.config/vault/machine-id`, refreshes skills, writes the persistent worker refresh block, and unregisters the LaunchAgent. It never initializes or contacts a Vault Git remote.

If a Vault task begins on Linux, inspect its schema-v7 mode. A healthy registered `remote-sshfs` client follows [[Vault Access]] and may use the full mount; a `none` machine follows [[README-vault-host-boundary|Vault Host Boundary]] and stops without cross-task coordination. Neither mode may use SSH to the primary as a Git publication step.

### Primary Git workflow

Repository `AGENTS.md` defines the required workflow. On the primary, fetch and compare before editing. At completion, stage the entire tracked and untracked non-ignored Vault, update and verify the media manifest, commit, fetch and integrate concurrent `origin/master`, and push. Background automation never commits, pushes, stashes, resets, rebases, or creates merge commits.

Versioned hooks apply only where Vault Git exists:

- `post-commit`: run the required Git LFS post-commit hook.
- `post-checkout`, `post-merge`, `post-rewrite`: refresh dependency-backed auto-skill projections and global skill links.
- `pre-push`: enforce pointer-only media policy where configured.

### Worktree coordination

The Vault is single-writer across iCloud Macs and remote clients. Managed mutations use the authoritative host-side writer lease; unmanaged editors must be closed before a remote session.

Before leaving the active Mac:

1. Stop Vault edits and close Obsidian plus Vault-rooted Codex tasks.
2. Finish the leased edit session. Do not wait for outbound iCloud upload.
3. If the active Mac is the primary, complete and push the required Vault-wide commit before leaving it. If it is a worker, do not run Git; iCloud continues transporting its changes asynchronously.

Before starting on another Mac:

1. Ensure the Vault folder is marked **Keep Downloaded** and choose **Download Now** when necessary for missing inbound files.
2. Require no dataless files and no iCloud conflict copies.
3. On a worker, confirm the shared `.git` pointer is dangling and continue with file work only. On the primary, run `vault git-preflight`, inspect the complete worktree, and account for every iCloud-delivered change.

Never edit through two worktrees at once. Never run `git`, `vault git-preflight`, `vault refresh`, `vault git-maintenance`, release, agents sync, or Git-backed media commands from a worker or remote client. If iCloud produces a conflict copy, stop and compare both versions; do not reset, stash, delete, or choose a winner automatically.

### Remote session diagnostics

A remote client starts with `vault access status` and acquires the lease through `vault access begin`. `vault access finish` records changed files, hashes, symlinks, and deletions, performs host fsync, writes an ignored diagnostic receipt, releases the lease, and returns without waiting for iCloud upload or caught-up state.

Optional diagnostics on the Git-owner Mac:

```sh
vault access wait --receipt SESSION_ID
vault git-preflight
```

The receipt command can materialize a named session, verify hashes and deletions, check File Provider health, and record `peer-observed`. The primary does not run it as a prerequisite. It follows the full Vault-wide Git procedure against the complete worktree currently visible to it. `vault access ack-git` is optional diagnostic bookkeeping after a pushed commit is visible on the configured remote branch.
