# Primary and Worker Vault Coordination

## Model

- `primary`: full authoritative working vault that may retain media bodies locally.
- `worker`: partial sparse checkout for `.agents` work, `_system`, and versioned `.githooks`; it may push reviewed non-media commits.
- `origin`: canonical durable state and the only repository coordination point.

Registry lives at `_system/config/infra-code-folder-and-computer-topology/private/machines.json`, schema v3. Clone identity lives in local Git config as `vault.machine-id`; it is never committed.

Missing registry keeps fleet tooling inactive. Initialize manually:

```sh
vault machine init --id primary-id --display-name "Primary" --platform macos --apply
vault machine register-worker --id worker-id --display-name "Worker" --platform linux --ssh-alias worker-id --home /home/user --repo-path /home/user/Code/vault --apply
vault machine identify primary-id --apply
```

## Explicit Git Rules

- Agents fetch and compare local `master` with `origin/master` before task edits.
- A clean checkout that is behind fast-forwards explicitly. Unrelated dirty files may remain only when local and remote heads already match and task paths do not overlap.
- Completed units are staged narrowly, committed, fetched again, merged with newer `origin/master` when necessary, and pushed explicitly.
- Automation never commits, pushes, stashes, resets, rebases, creates merge commits, or fans out changes between machines. The primary's daily refresh may fetch and attempt a strict fast-forward of `master`; overlap, network, or divergence failures preserve local work and do not block local generation.
- Pointer-only workers verify manifest/pointers without downloading media bodies.
- Worker media pointer or manifest changes require local bodies plus explicit `vault.media-write-authorized=true`.

## Commands

```sh
vault git-preflight
vault worker-sync install-hooks --apply
vault worker-sync bootstrap WORKER_ID --apply
```

`vault git-preflight` fetches and attempts a strict fast-forward, including with a dirty working tree; Git aborts safely when incoming changes overlap local work. Scheduled refresh treats that result as best-effort so Git coordination cannot block local generation. Normal agent work follows the root `AGENTS.md` fetch-and-compare policy.

## Explicit Worker Bootstrap

Run worker bootstrap from the primary after the worker is registered and reachable:

```sh
vault worker-sync bootstrap WORKER_ID --apply
```

The command creates or repairs the sparse clone, clone identity, pointer-only media mode, versioned hooks, `vault` command link, dependency-backed auto-skill projections, and global skill links. It does not fetch an existing checkout, push commits, contact other workers, or install a background service or timer. Bring an existing checkout to the desired committed `origin/master` first.

Verify on the worker:

```sh
git status --short --branch
git sparse-checkout list
git config --get vault.machine-id
git config --get core.hooksPath
vault skills sync --dry-run
```
