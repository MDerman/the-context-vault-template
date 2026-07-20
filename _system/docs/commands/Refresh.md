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

1. Brain Dump ingestion only when `--sync-brain-dump` is passed.
2. Best-effort Google Calendar TaskNotes mirror with orphan mirror-event pruning.
3. Content schedule generation.
4. Source periodic-note creation, daily checklist carry-forward, and vault Sync Embed rollups.
5. `Dashboard.md` generation.
6. Best-effort local Git maintenance.

Content, periodic, and Dashboard generation are required. Failure stops refresh so scheduled retries remain useful. Calendar and Git maintenance failures warn and continue.

Register the local daily refresh LaunchAgent:

```bash
vault refresh-schedule register
vault refresh-schedule status
vault refresh-schedule unregister
```

The schedule is configured in `_system/config/vault.json` under `refresh_schedule`. Use `timezone: local` to resolve each laptop's current system timezone at runtime. The LaunchAgent runs at load, at the configured time, and every `catchup_interval_seconds` seconds as an idempotent due check. A successful refresh writes the local date to `~/Library/Application Support/obsidian-context-vault/last-refresh-date.txt`; until that stamp matches today, failed refreshes retry according to `retry_attempts` and `retry_delay_seconds`.

Implementation script:

```bash
python3 _system/commands/refresh.py
```

Brain Dump ingestion is configured in:

```text
_system/config/vault.json
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

To skip Google Calendar sync:

```bash
vault refresh --skip-gcal
```

To skip local Git maintenance:

```bash
vault refresh --skip-git-maintenance
```

Git maintenance keeps local history shallow at 5 commits by default and prunes unreachable local objects:

```bash
vault git-maintenance
vault git-maintenance --depth 5
```

Use `--git-depth N` on `vault refresh` to change the refresh-time depth.

Use `vault content` or `vault periodic` for targeted generation. There is no separate context or Dashboard command.
