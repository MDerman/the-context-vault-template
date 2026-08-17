## Primary and Worker Vault Coordination

### Model

- `primary`: the only Mac with Vault Git. It uses the full iCloud working Vault and machine-local external Git metadata at `~/.local/share/vault-git/Vault.git`. It alone commits, pushes, runs Git preflight and media maintenance, and schedules or manually runs `vault refresh` on macOS.
- macOS `worker`: the same fully downloaded iCloud working files with no Vault Git metadata. The shared `.git` file remains because iCloud carries it from the primary, but its target must not exist on the worker. The worker edits files only.
- Linux `worker`: a code-repository worker only. It does not clone, read, edit, commit, or publish the Vault.
- `origin`: the primary Mac's durable Vault Git backup. It does not coordinate iCloud worker Macs directly.

No Mac may create or retain `~/Code/vault`. Among iCloud-participating Macs, exactly one Git owner exists: the registered primary. Never copy or sync `~/.local/share/vault-git/Vault.git` between Macs.

Registry lives at `_system/local/skills/infra-code-folder-and-computer-topology/private/machines.json`, schema v4. Primary identity lives in local Git config as `vault.machine-id`. A Gitless iCloud worker stores the same machine-local identity at `~/.config/vault/machine-id` with mode `0600`; it is never stored in iCloud.

Missing registry keeps fleet tooling inactive. Initialize manually:

```sh
vault machine init --id primary-id --display-name "Primary" --platform macos --apply
vault machine identify primary-id --apply
```

### Git rules

- Only the primary Mac runs Vault Git commands.
- Completed primary work stages and commits the complete tracked and untracked non-ignored Vault worktree, fetches, integrates newer `origin/master` safely, and pushes.
- Background automation never commits, pushes, stashes, resets, rebases, creates merge commits, or fans changes between machines.
- Vault work started on a Linux host follows [[README-vault-host-boundary|Vault Host Boundary]] and stops without cross-task coordination. Linux code work uses self-contained repository-local plans and never uses SSH to the primary as a Vault publication hop.

### Worker bootstrap

Run from the registered primary after the worker is registered and reachable:

```sh
vault worker-sync bootstrap WORKER_ID --apply
vault worker-sync bootstrap WORKER_ID --provision-disabled --apply
```

Normal bootstrap requires an enabled worker. Reviewed onboarding may provision exactly one disabled worker with `--provision-disabled`; keep it disabled until reboot acceptance passes.

For `checkout: icloud`, bootstrap requires a fully materialized iCloud Vault, rejects dataless files, reads the shared `.git` pointer, and guarantees that its target does not exist. If the expected legacy worker target `~/.local/share/vault-git/Vault.git` exists, apply moves it recoverably to `~/.Trash/Vault.git-disabled-<timestamp>-<pid>`. It refuses any unexpected Git target and any legacy `~/Code/vault`. It writes `~/.config/vault/machine-id`, refreshes skill links, creates the persistent worker refresh block, and unregisters the refresh LaunchAgent. It never initializes, fetches, indexes, checks out, or configures Vault Git.

Verify a worker Mac:

```sh
test "$(cat "$HOME/.config/vault/machine-id")" = WORKER_ID
test -f "$(vault root)/.git"
pointer_target="$(sed -n 's/^gitdir: //p' "$(vault root)/.git")"
test -n "$pointer_target" && test ! -e "$pointer_target"
! git -C "$(vault root)" rev-parse --git-dir
test ! -e "$HOME/Code/vault"
vault refresh-schedule status
vault skills sync --dry-run
```

Refresh scheduling must report ineligible and unloaded.

### Mac handoff

The shared iCloud Vault is single-writer across Macs.

Before leaving any Mac, stop Vault edits, close Obsidian and Vault-rooted Codex tasks, and wait for iCloud upload to finish. Before opening the Vault elsewhere, wait for iCloud to settle, ensure the folder is fully downloaded, and check for dataless files or conflict copies.

After work on an iCloud worker, switch to the primary only after upload completes. The primary then runs `vault git-preflight`, inspects all iCloud-delivered changes, performs the required complete-worktree commit, and pushes. A worker must never run `git`, `vault git-preflight`, `vault refresh`, or Git-backed media commands against the iCloud Vault.
