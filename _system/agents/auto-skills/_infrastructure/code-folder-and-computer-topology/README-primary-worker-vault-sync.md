# Primary and Worker Vault Sync

## Model

- `primary`: full authoritative working vault. May retain media bodies locally and fan out committed `master` after successful origin push.
- `worker`: partial sparse checkout for `_system` work plus versioned `.githooks`. May push clean non-media commits. Never fans out to other machines.
- `origin`: canonical durable desired state and reconnect queue.

Registry lives at `_system/config/code-folder-and-computer-topology/private/machines.json`, schema v3. Clone identity lives in local Git config as `vault.machine-id`; it is never committed.

Missing registry keeps fleet automation inactive. Initialize manually:

```sh
vault machine init --id primary-id --display-name "Primary" --platform macos --apply
vault machine register-worker --id worker-id --display-name "Worker" --platform linux --ssh-alias worker-id --home /home/user --repo-path /home/user/Code/vault --apply
vault machine identify primary-id --apply
```

## Safe Sync Rules

- Branch: `master`.
- Fetch with prune, then fast-forward only.
- Dirty or divergent checkout stops. Never stash, reset, force, or auto-rebase.
- Post-commit hook queues background work and returns.
- Primary pushes origin before SSH fan-out.
- Worker pushes only clean committed `master`; rejected push remains local.
- Startup service plus five-minute timer catches workers up after downtime.
- Pointer-only workers verify manifest/pointers without downloading media bodies.
- Worker media pointer or manifest changes require local bodies plus explicit `vault.media-write-authorized=true`.

## Commands

```sh
vault git-preflight
vault worker-sync status
vault worker-sync install-hooks --apply
vault worker-sync bootstrap WORKER_ID --apply
```

Linux workers use systemd user service/timer. macOS workers use LaunchAgent with `RunAtLoad` and 300-second interval.
