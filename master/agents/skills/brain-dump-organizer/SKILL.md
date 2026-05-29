---
name: brain-dump-organizer
description: Organize the synced Brain Dump Apple Notes import into reviewable Obsidian proposal notes and apply approved proposals. Use when the user says organize Apple Notes, triage Apple Notes, process Brain Dump, apply Brain Dump proposals, or clean the Brain Dump inbox.
---

# Brain Dump Organizer

## Quick Start

Use this skill in two separate flows.

### Organize Brain Dump

1. Run:

```bash
vault triage prepare
```

2. Read the JSON output. It includes the `run_id`, backup note, Base path, and proposal item notes.
3. Read `master/agents/skills/brain-dump-organizer/references/triage-prompt.md`.
4. Inspect the active routing docs before classifying:
   - `master/system/context/CONTEXT.md`
   - `01-personal/HOME.md`
   - `02-personal-brand/HOME.md`
   - `03-business/HOME.md`
   - relevant existing `_obsidian/tasks`
5. Edit each proposal note for the run:
   - set `route`, `target_context`, `target_kind`, `apply_action`, `priority`, `task_status`, `target_path`, and `confidence`;
   - keep `proposal_status: needs-review` unless the user explicitly wants auto-approval;
   - add a short `## Proposed Reason`.
6. Run:

```bash
vault triage clear-import
```

The root import file should now be empty. The backup and proposal notes are the review copy.

### Apply Approved Proposals

1. The user reviews `master/_obsidian/bases/BRAIN_DUMP_TRIAGE.base` and changes proposals to `proposal_status: approved`.
2. Run:

```bash
vault triage apply
```

3. Report created/appended notes and any blocked proposals.

## Safety Rules

- Never apply `needs-review` proposals.
- Never delete backup folders.
- Do not call an external LLM API; the current agent performs classification by editing proposal notes.
- Keep generated links in Obsidian `[[ ]]` syntax.
- If `route: append-to-existing-task`, require `target_path` before approval/application.
- If applying fails for a proposal, leave it editable and report the blocker.

## Useful Commands

```bash
vault triage ensure-base
vault triage apply --dry-run
vault triage self-test
```
