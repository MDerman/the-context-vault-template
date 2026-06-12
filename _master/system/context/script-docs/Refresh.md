---
type: agent-reference
status: enabled
---
# Refresh

Current manual refresh:

```bash
vault refresh
```

The refresh wrapper ingests the configured Brain Dump Apple Note, runs the Google Calendar TaskNotes date mirror, regenerates agent context, then runs best-effort local Git maintenance.

Register the local daily refresh LaunchAgent:

```bash
vault refresh-schedule register
vault refresh-schedule status
vault refresh-schedule unregister
```

The schedule is configured in `_master/system/config.json` under `refresh_schedule`. Use `timezone: local` to resolve each laptop's current system timezone at runtime. The LaunchAgent runs at load, at the configured time, and every `catchup_interval_seconds` seconds as an idempotent due check. A successful refresh writes the local date to `~/Library/Application Support/obsidian-context-vault/last-refresh-date.txt`; until that stamp matches today, failed refreshes retry according to `retry_attempts` and `retry_delay_seconds`.

Implementation script:

```bash
python3 _master/system/scripts/refresh.py
```

Brain Dump ingestion is configured in:

```text
_master/system/config.json
```

The default Apple Note is `Brain Dump`. New imports are inserted at the top of its single synced import file:

```text
_master/system/inbox/BRAIN_DUMP.md
```

Attachments are copied to:

```text
_master/system/inbox/BRAIN_DUMP_ATTACHMENTS/
```

After a successful write, the Apple Note body is cleared back to a blank placeholder. To ingest without clearing Brain Dump:

```bash
vault refresh --no-clear-brain-dump
```

To refresh all context folders:

```bash
vault refresh --all
```

To skip Brain Dump ingestion:

```bash
vault refresh --skip-brain-dump
```

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
