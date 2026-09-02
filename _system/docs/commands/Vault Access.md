---
type: agent-reference
status: enabled
---

## Vault access

`vault access` reports and enforces full-worktree safety and shared writer leases. It also exposes iCloud, receipt, observation, and Git-push state for diagnostics, but upload state does not gate task completion. It uses schema-v7 machine identity and fails closed on unknown topology or safety output.

### Commands

```bash
vault access mount
vault access unmount
vault access status [--json]
vault access doctor [--json]
vault access wait --download|--upload|--receipt SESSION_ID [--timeout SECONDS]
vault access begin [--task-id TASK_OR_THREAD_ID]
vault access finish [--timeout SECONDS]
vault access recover --reason "EXPLICIT REASON"
vault access ack-git --receipt SESSION_ID --commit COMMIT_SHA
```

`mount` and `unmount` operate SSHFS only on a registered `remote-sshfs` client. A Mac reports its local iCloud worktree instead. Unmount is graceful and refuses an active session or lease.

`status` reports four independent states:

1. `filesystem_saved`
2. `icloud_uploaded`
3. `peer_observed`
4. `git_pushed`

It also reports SSH and exact mount health, read-write mode, File Provider and iCloud container state, last activity, dataless/conflict/pause/pending paths, the lease owner/session/heartbeat/expiry, active session, and the latest receipt.

`begin` requires a fully materialized, current downloaded worktree with no conflicts, pause, exclusions, or dataless files, then atomically acquires the one host-side lease. Pending outbound uploads and a container that is not caught up do not block access. Managed commands that write Vault files fail without a matching lease. Close Obsidian and unmanaged Vault writers first because filesystem permissions cannot prevent them from bypassing the command boundary.

`finish` snapshots changes, hashes changed file bodies, records symlinks and deletions, fsyncs on the Mac host, writes an ignored diagnostic receipt, releases the lease, and returns immediately. It never waits for named uploads, receipt upload, or container caught-up state.

`wait --upload`, `wait --receipt`, and `ack-git` remain explicit diagnostic commands. They are never required before Git preflight, commit, push, or task completion. The registered Git owner commits and pushes the complete worktree currently visible to it.

Setup, systemd, SSHFS options, first acceptance, reboot acceptance, and recovery belong to [[linux-remote-vault-access|Linux Remote Vault Access]] under `$infra-onboard-machine`. Host and Git coordination are summarized in [[Vault Git Sync]] and [[README-primary-worker-vault-sync|Primary and Worker Vault Coordination]].
