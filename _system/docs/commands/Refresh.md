---
type: agent-reference
status: enabled
---
# Refresh

Current manual refresh:

```bash
vault refresh
```

Refresh runs, in order:

1. Required Git fetch/prune and fast-forward-only preflight when remote exists.
2. Brain Dump ingestion only when `--sync-brain-dump` is passed.
3. Content schedule generation.
4. Source periodic-note creation, non-destructive daily task-section carry-forward, and vault Sync Embed rollups.
5. `Dashboard.md` generation.
6. Best-effort local Git maintenance.
7. Successful-refresh notification for Context Nine periodic-tab rollover.

Content, periodic, and Dashboard generation are required. Failure stops refresh so scheduled retries remain useful. Git maintenance failures warn and continue.

Register the local daily refresh LaunchAgent:

```bash
vault refresh-schedule register
vault refresh-schedule status
vault refresh-schedule unregister
```

Scheduled and manual refresh are restricted to the schema-v7 `vault_git.refresh_owner_machine_id`, which currently equals the Git owner. `vault refresh-schedule register` refuses every worker, a stale worker LaunchAgent exits without refresh, and Mac-worker bootstrap writes a persistent block before unregistering an existing schedule. Gitless iCloud workers and remote SSHFS clients must not run refresh; they finish their upload handoff and let the owner refresh and coordinate Git after [[Vault Git Sync|Worktree handoff]].

The schedule is configured in `_system/local/vault.json` under `refresh_schedule`. Use `timezone: local` to resolve each laptop's current system timezone at runtime. The LaunchAgent runs at load, at the configured time, and every `catchup_interval_seconds` seconds as an idempotent due check. A successful refresh writes the local date to `~/Library/Application Support/obsidian-context-vault/last-refresh-date.txt`; until that stamp matches today, failed refreshes retry according to `retry_attempts` and `retry_delay_seconds`.

Scheduled refreshes use best-effort Git preflight: fetch first, safely fast-forward `master` when incoming changes do not overlap local work, and preserve the working tree when Git blocks the update. Network, overlap, or divergence failures warn but cannot block local daily-note, periodic-rollup, or Dashboard generation. Manual `vault refresh` retains fatal preflight unless `--skip-git-preflight` or `--best-effort-git-preflight` is passed explicitly. Daily carry-forward uses the most recent earlier daily note, even when one or more calendar days have no note. Under the daily task section, unchecked checklist items plus ordinary text and nested headings are appended without duplicating existing content; checked checklist lines are not carried. An existing daily note is never regenerated from its template, so refresh preserves content added ahead of time or by Obsidian's calendar UI.

After a successful refresh for the machine's current local date, refresh atomically writes `_system/local/state/refresh-complete.json`. Context Nine watches that ignored marker and replaces actual open Markdown tabs for past periodic notes with the current note in the same context or `_system` rollup scope. Current and future-dated periodic notes remain open. Sidebar Outline state, recent-file history, and `.obsidian/workspace.json` are not edited.

When Obsidian is already running and its command line interface is registered, refresh also calls the Context Nine CLI handler immediately. It never intentionally launches Obsidian for this notification; unavailable or failed CLI delivery warns at most and the marker remains the durable fallback. Enable the optional direct path under Obsidian **Settings → General → Command line interface**.

Implementation script:

```bash
python3 _system/commands/refresh.py
```

Brain Dump ingestion is configured in:

```text
_system/local/vault.json
```

The default Apple Note is `Brain Dump`. New imports are inserted at the top of its single synced import file:

```text
_system/inbox/BRAIN_DUMP.md
```

Attachments are copied to:

```text
_system/inbox/BRAIN_DUMP_ATTACHMENTS/
```

After a successful write, the Apple Note body is cleared back to a blank placeholder. To import Brain Dump during refresh:

```bash
vault refresh --sync-brain-dump
```

To ingest without clearing Brain Dump:

```bash
vault refresh --sync-brain-dump --no-clear-brain-dump
```

To refresh all context folders:

```bash
vault refresh --all
```

Brain Dump ingestion is skipped by default. Use standalone `vault sync` or explicit `vault refresh --sync-brain-dump` when ingestion is wanted.

To skip local Git maintenance:

```bash
vault refresh --skip-git-maintenance
```

To skip required Git preflight explicitly:

```bash
vault refresh --skip-git-preflight
```

To attempt fetch and safe fast-forward but continue local generation if coordination is unavailable:

```bash
vault refresh --best-effort-git-preflight
```

Git maintenance keeps local history shallow at 100 commits by default and prunes unreachable local objects:

```bash
vault git-maintenance
vault git-maintenance --depth 100
```

Use `--git-depth N` on `vault refresh` to change the refresh-time depth.

Use `vault content` or `vault periodic` for targeted generation. There is no separate context or Dashboard command.
