# Agent Instructions

Root workspace is one Obsidian vault with context folders. `AGENTS.md` is direct-edit source of truth. `CLAUDE.md` is a symlink to it. Bootstrap/export copies root `AGENTS.md`; agent setup scripts only ensure symlinks.

## Always

- When making changes to workflows, scripts, and generally anything under the _system folder, ensure that relevant skills and docs are updated (if needed) and that if a future agent like you is ever lead to use that functionality, that this AGENTS.md will lead them to the correct documentation somehow and/or there is a relevant skill that would be discovered by the agent and read.
- Use `[[Obsidian links]]`, not Markdown links, inside vault notes.
- Follow README breadcrumbs before acting: nearest `README.md`, then relevant `README-<topic>.md`, then command/tool docs.
- If a workflow needs SOP or quick start docs, put it in the relevant folder as `README-<topic>.md`.
- Use skills for reusable agent capabilities with trigger rules; use folder READMEs for vault SOPs and tool usage.
- Put plans in `.agents/plans/`.
- Put repo-scoped skills in `.agents/skills/`.
- Put implicit shared skills in `_system/agents/auto-skills/`, explicit-only skills in `_system/agents/manual-skills/`, repo-owned skills in the owning repo's `.agents/skills/`, and `gh skill --dir` installs in `_system/agents/gh-skills/`; organize Vault sources recursively with `_lower-kebab` group folders, then run `vault skills sync --dry-run` and `--apply`. Only explicitly configured repo skills are globally projected.
- Treat incidental `.obsidian/` Git churn as ordinary Vault state: do not stop for it, and include it in the required final Vault-wide commit.
- Do not bulk-move, restructure, delete, or overwrite user content unless explicitly asked.
- Code Folder and Computer Topology auto skill is private source of truth for machine access and general `~/Code/` placement; use folder/repo docs before changing code.
- Vault working files live only in the full iCloud Obsidian Vault on Macs. Only the registered primary Mac may have Vault Git metadata at `~/.local/share/vault-git/Vault.git`; iCloud worker Macs remain Gitless. Linux and other non-iCloud hosts are code-repository workers only and must not clone, read, or edit the Vault.
- Never make H1s (#) directly at top of md file. it is redundant. Use as little headings and text as possible when organizing or creating notes.
- when writing links (internally, or url links) never format the link display text, and also make internal page links like "[[file name]]" not "[[path/to/file name]]" 
- Use `***` for Markdown thematic breaks in note bodies. Reserve standalone `---` lines for YAML frontmatter delimiters so body text cannot become a Setext heading.
- External dependency repos live under `~/Code/open_source/<repo-name>` and are tracked in `_system/local/deps.json`.
- `_system/agents/skills` is generated symlink-only catalog. Never install content there; `vault skills sync --apply` projects auto, manual, GitHub-managed, and selected repo-owned sources into it.

The managed Git workflow below applies only on the primary Mac. A Gitless iCloud worker Mac skips the entire Git block and follows **iCloud Mac Worktree** instead.

## Git Coordination

Before making task-related file changes:

1. Run `git fetch origin --prune`.
2. Confirm the current branch is the repository's expected working branch, then compare `HEAD` with its configured upstream.
3. If the checkout is clean and behind, fast-forward to the upstream branch.
4. Unrelated dirty or newly appearing files are expected in a shared checkout. Continue when they do not overlap the task's files, and never stage, overwrite, or revert them.
5. If the current branch is ahead, divergent, or cannot be updated safely, identify and reconcile the Git state without discarding other work before editing.

After completing a user-requested unit of work:

1. Stage only that unit's files and commit them, even when unrelated changes remain or appear concurrently. A dirty tree elsewhere is not a reason to skip the commit.
2. If unrelated paths are already staged, keep them staged but exclude them from the unit's commit by committing only the task's paths.
3. Run `git fetch origin --prune` again.
4. If the upstream branch advanced, integrate it into the current branch; resolve conflicts only when they are task-scoped and the intended result is clear.
5. If unrelated dirty work blocks integration, or conflict intent is unclear, preserve all work and report the blocker without overwriting, stashing, resetting, or including unrelated changes.
6. Push the current branch to its configured upstream. If the push is rejected because the upstream advanced again, fetch, integrate, and retry without forcing.

### Vault-wide completion override

For this Vault repository only, the final staging scope supersedes the narrow task-scoped staging language in the managed Git block above on the primary Mac. After completing work there, run `git add -A`, update and stage the media manifest, verify the staged media state, commit every pending tracked and untracked non-ignored Vault change regardless of source or completeness, fetch and merge `origin/master`, and push. Repeat the complete-worktree commit if new changes appear before the final fetch. Completion requires a successful push unless an exact blocker is reported. A Gitless iCloud worker Mac must never run these Git steps: finish the file edits, close Vault writers, wait for iCloud upload, and hand off the complete-worktree commit and push to the primary Mac.

## Vault Host Boundary

- Run Vault tasks only from the full iCloud Vault on the registered primary Mac or a Gitless iCloud worker Mac.
- A task started on Linux or another non-iCloud host must follow [[README-vault-host-boundary|Vault Host Boundary]] before any Vault-specific read or write. It must stop immediately: do not dispatch, message, create, hand off to, wait for, or poll another task; do not use a Vault clone or SSH publication step.
- Linux machines remain valid code-repository workers. Executable plans for them must be self-contained in the owning code repository; the Vault note must name that entrypoint.

## iCloud Mac Worktree

- The primary Mac and iCloud-participating worker Macs share one full set of Vault working files through iCloud. Only the primary has the external Git directory referenced by the shared `.git` file. On every worker, that pointer must be dangling and `git -C "$(vault root)" rev-parse --git-dir` must fail.
- Treat the iCloud Vault as single-writer across Macs. Before changing machines, stop edits, close Obsidian and Vault-rooted Codex tasks, and wait for iCloud to finish uploading. Never edit the Vault concurrently on two Macs.
- On an iCloud worker, mark the Vault folder **Keep Downloaded**, use **Download Now** when necessary, wait for iCloud to settle, and check for dataless files or iCloud conflict copies. Do not run Vault Git, `vault git-preflight`, `vault refresh`, or Git-backed media maintenance there.
- After worker edits, return to the primary only after iCloud upload completes. On the primary, wait for materialization, run `vault git-preflight`, inspect the complete worktree, then commit and push all Vault changes.
- GitHub `origin` is the primary Mac's durable Git backup. iCloud transports Mac working files and local-only media bodies. Never copy or sync the primary's external Git directory.
- Scheduled and manual `vault refresh` are primary-only on Macs. Worker Macs may not register or execute the refresh LaunchAgent.

## First Read

1. Run `vault inventory` for live periods, contexts, task state, and source-note routing.
2. Use the routing index below, then follow folder READMEs until reaching the relevant SOP/tool/command doc.
3. Read relevant `<context-folder>/<context-folder>.md` before changing entity operating rules.
4. For public bootstrap/export work, read `_system/bootstrap/README.md` and `_system/docs/commands/Bootstrap Export.md`.

## Folder Map

- `_system/`: operating layer for shared Obsidian assets, agents, bootstrap, commands, docs, inboxes, local user data, migrations, sync, and tools. Read `_system/README.md`.
- `_system/agents/`: shared skills, skill storage, and versioned global agent configuration. Read `_system/agents/README.md`.
- `_system/tools/`: reusable tools outside `vault`. Read `_system/tools/README.md`.
- `_system/bootstrap/`: fresh install, public export, release, and upgrade framework.
- `_system/commands/`: `vault` dispatcher, commands, internals, and tests.
- `_system/docs/`: command, Obsidian, and workflow documentation.
- `_system/local/`: user-specific general configuration, per-skill configuration, env tooling, and runtime state. Read `_system/local/README.md`.
- `_system/local/state/`: ignored local reports, backups, and install/export state.
- `_library/`: learning, research dumps, swipe files, source material, thoughts. Read `_library/LIBRARY.md` before organizing it.
- `_wiki/`: synthesized reusable knowledge.
- `other/`: archive/holding area only when explicitly asked.
- Context folders: source-of-truth workspaces with local `<context-folder>.md` routing notes and `_obsidian/` operating folders.

## Core Docs

- `_system/README.md`: vault architecture, folder model, data model, context folder rules.
- `_system/docs/commands/README.md`: `vault` command index and command docs routing.
- `_system/docs/commands/README-reference.md`: full command and bootstrap script inventory.
- `_system/docs/obsidian/README.md`: Obsidian profile/plugins/templates/UI.
- `_system/bootstrap/README.md`: bootstrap/export/upgrade mechanics.
- `_system/local/README.md`: local-data ownership and skill-config separation.
- `_system/local/env/README.md`: env workflow; placeholders only in tracked files.
- Machine registry, primary/worker coordination, connection routing, and code topology: [[_system/agents/auto-skills/_infrastructure/infra-code-folder-and-computer-topology/SKILL|Code Folder and Computer Topology skill]].

## Agent Routing Index

- Current state: `vault inventory`, source context notes, `Dashboard.md`.
- Tasks/projects/epics: `_system/docs/commands/Tasks And Projects.md`, then `<context-folder>/_obsidian/<tasks|projects|epics>/`.
- Calendar/time blocks: `_system/docs/commands/Google Calendar.md`, then `vault gcal`.
- Content: `_system/README.md#Content`, `_system/docs/commands/Content Schedules.md`, then the selected capability folders under `<context-folder>/_obsidian/content/`; schedules additionally require `content_schedules_enabled: true`.
- Scripts and `vault` commands: `_system/docs/commands/README.md`; open only the needed script doc.
- General tools and invoices: `_system/tools/README.md`, then relevant `README-<topic>.md` or tool README.
- Skills: `_system/agents/README.md`, `_system/agents/README-skills.md`, `_system/docs/commands/Agent Skills Sync.md`.
- Dependency repos: `_system/docs/commands/Dependency Repos.md`, then `vault deps`.
- Fleet Code and personal agent configuration sync: `$infra-sync-code-workspaces`; topology supplies machine/repository facts and onboarding calls the same workflow.
- Bootstrap/export/upgrade: `_system/bootstrap/README.md`, `_system/docs/commands/<Bootstrap Export|Public Vault Upgrade>.md`.
- Obsidian profile/UI/theme: `_system/docs/obsidian/README.md`, then `_system/docs/obsidian/editing_obsidian.md` if editing UI/CSS/plugin behavior.
- Attachments: `_system/docs/commands/Attachments.md`.
- Private Git and pointer-only media: `_system/docs/commands/README-git.md`.
- Env/auth: `_system/local/env/README.md`.
- Library changes: `_library/LIBRARY.md`.

## Core Paths

- Tasks: `<context-folder>/_obsidian/tasks/`
- Projects: `<context-folder>/_obsidian/projects/`
- Epics: `<context-folder>/_obsidian/epics/`
- Periodic notes: `<context-folder>/_obsidian/periodic/<daily|weekly|monthly|quarterly|yearly>/`
- Entity operating notes: `<context-folder>/<context-folder>.md`
- Content: `<context-folder>/_obsidian/content/`
- Content schedules: `<context-folder>/_obsidian/content-schedules/`
- Attachments: owning top-level folder's `_obsidian/attachments/`
- Brain Dump import: `_system/inbox/BRAIN_DUMP.md`

## Operating SOPs

- Create TaskNotes tasks only for executable next actions, reminders, or decisions needing follow-up.
- Route unspecific capture to current default context from `vault inventory`.
- Use `scheduled` for work/surface date and `due` for deadline.
- Use native time fields: `timeEstimate`, `timeEntries`, `pomodoros`; do not use `duration`.
- Use `vault gcal create-event` for concrete appointments/travel/meetings/reservations; use `create-block` only for explicit time blocking.
- Use `_obsidian/content` for owned content items/ideas/publication definitions; use `_obsidian/tasks` for executable work about content.
- Keep proof-source notes explicit: commitment, data source, manual/automated status, missing-proof task/warning.
