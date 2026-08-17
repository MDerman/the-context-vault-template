---
type: agent-reference
status: enabled
---
## Vault Git coordination

The registered primary Mac is the sole Git owner for the shared iCloud Vault. It keeps machine-local Git metadata at `~/.local/share/vault-git/Vault.git`; iCloud carries only the working files and the shared `.git` pointer. Every iCloud worker Mac is file-only: the pointer target must not exist there, so Vault Git commands fail by design. Linux and other non-iCloud hosts do not run Vault tasks or keep Vault checkouts.

This removes the split-brain condition created when iCloud delivered working files while separate Mac Git indexes advanced at different times. No Mac worker may create Vault Git metadata, a Vault LFS cache, or `~/Code/vault`.

### Commands

Run Git commands only on the primary Mac:

```sh
vault git-preflight
vault worker-sync install-hooks --apply
```

Run worker bootstrap from the primary:

```sh
vault worker-sync bootstrap WORKER_ID --apply
vault worker-sync bootstrap WORKER_ID --provision-disabled --apply
```

For a Mac worker registered with `checkout: icloud`, bootstrap requires a complete iCloud Vault with no dataless items. It validates the shared `.git` pointer and guarantees it is dangling. If the pointer resolves to the exact legacy worker location `~/.local/share/vault-git/Vault.git`, apply moves that directory recoverably to `~/.Trash/Vault.git-disabled-<timestamp>-<pid>`. Any unexpected live target is refused. Bootstrap then writes `~/.config/vault/machine-id`, refreshes skills, writes the persistent worker refresh block, and unregisters the LaunchAgent. It never initializes or contacts a Vault Git remote.

If a Vault task begins on Linux, follow [[README-vault-host-boundary|Vault Host Boundary]] and stop without messaging, creating, handing off to, waiting for, or polling another task. Code execution uses a self-contained plan in the owning repository; do not SSH to the primary as a Vault publication step.

### Primary Git workflow

Repository `AGENTS.md` defines the required workflow. On the primary, fetch and compare before editing. At completion, stage the entire tracked and untracked non-ignored Vault, update and verify the media manifest, commit, fetch and integrate concurrent `origin/master`, and push. Background automation never commits, pushes, stashes, resets, rebases, or creates merge commits.

Versioned hooks apply only where Vault Git exists:

- `post-commit`: run the required Git LFS post-commit hook.
- `post-checkout`, `post-merge`, `post-rewrite`: refresh dependency-backed auto-skill projections and global skill links.
- `pre-push`: enforce pointer-only media policy where configured.

### Mac-to-Mac handoff

The iCloud Vault is single-writer across Macs.

Before leaving the active Mac:

1. Stop Vault edits and close Obsidian plus Vault-rooted Codex tasks.
2. Wait for iCloud upload to finish.
3. If the active Mac is the primary, complete and push the required Vault-wide commit before leaving it. If it is a worker, do not run Git; its changes will be committed on the primary after handoff.

Before starting on another Mac:

1. Ensure the Vault folder is marked **Keep Downloaded**, choose **Download Now** when necessary, and wait for iCloud activity to settle.
2. Require no dataless files and no iCloud conflict copies.
3. On a worker, confirm the shared `.git` pointer is dangling and continue with file work only. On the primary, run `vault git-preflight`, inspect the complete worktree, and account for every iCloud-delivered change.

Never edit the Vault on two Macs at once. Never run `git`, `vault git-preflight`, `vault refresh`, `vault git-maintenance`, or Git-backed media commands against the iCloud Vault from a worker Mac. If iCloud produces a conflict copy, stop and compare both versions; do not reset, stash, delete, or choose a winner automatically.
