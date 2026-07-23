# Vault Git Sync

GitHub `origin/master` is durable desired state. Primary uses full checkout; workers use partial sparse clones containing root files, `_system`, and versioned `.githooks`.

```sh
vault git-preflight
vault worker-sync status
vault worker-sync install-hooks --apply
vault worker-sync bootstrap WORKER_ID --apply
```

Versioned hooks live in `.githooks`:

- `post-commit`: enqueue background push/delivery.
- `post-checkout`, `post-merge`, `post-rewrite`: apply skill projections.
- `pre-push`: pointer-only media guard when configured; ordinary Git LFS otherwise.

Worker refresh uses fetch/prune and fast-forward only. Dirty, divergent, unreachable, disabled, or rejected states stop and log. Automation never stashes, rebases, resets, forces, or resolves conflicts.

Linux worker installation creates `vault-worker-sync.service` and `vault-worker-sync.timer` under `~/.config/systemd/user`. macOS creates `~/Library/LaunchAgents/com.vault.worker-sync.plist`. Both run at startup and every five minutes.
