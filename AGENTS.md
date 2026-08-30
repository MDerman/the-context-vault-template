# Agent Instructions

Root workspace is one Obsidian vault with context folders. `AGENTS.md` is direct-edit source of truth. `CLAUDE.md` is a symlink to it. Bootstrap/export copies root `AGENTS.md`; agent setup scripts only ensure symlinks.

## Always

- When making changes to workflows, scripts, and generally anything under the _system folder, ensure that relevant skills and docs are updated (if needed) and that if a future agent like you is ever lead to use that functionality, that this AGENTS.md will lead them to the correct documentation somehow and/or there is a relevant skill that would be discovered by the agent and read.
- Use `[[Obsidian links]]`, not Markdown links, inside vault notes.
- Follow README breadcrumbs before acting: nearest `README.md`, then relevant `README-<topic>.md`, then command/tool docs.
- If a workflow needs SOP or quick start docs, put it in the relevant folder as `README-<topic>.md`.
- When organizing a folder, keep its Python implementation files in a `scripts/` subfolder instead of loose beside its README/docs; purpose-specific `tests/` and `assets/` stay in their own folders.
- Use skills for reusable agent capabilities with trigger rules; use folder READMEs for vault SOPs and tool usage.
- Put plans in `.agents/plans/`.
- Put repo-scoped skills in `.agents/skills/`.
- Put implicit shared skills in `_system/agents/skills/auto/`, explicit-only skills in `_system/agents/skills/manual/`, repo-owned skills in the owning repo's `.agents/skills/`, and `gh skill --dir` installs in `_system/agents/skills/github/`; organize Vault sources recursively with `_lower-kebab` group folders, then run `ctx9-agents sync --dry-run` and `ctx9-agents sync`. Only explicitly configured repo skills are globally projected.
- `_system/agents/skills/catalog` is the generated Vault-local symlink-only catalog. Never install content there; `ctx9-agents sync` projects auto, manual, GitHub-managed, and selected repo-owned sources into it, then distributes point-in-time copies to enabled fleet machines.
- Treat incidental `.obsidian/` Git churn as ordinary Vault state: do not stop for it, and include it in the required final Vault-wide commit.
- Do not bulk-move, restructure, delete, or overwrite user content unless explicitly asked.
- Code Folder and Computer Topology auto skill is private source of truth for machine access and general `~/Code/` placement; use folder/repo docs before changing code.
- For machine-local credential locations, custody, enrollment, verification, and recovery, read `~/.agents/package/secrets/README.md` (Vault source: `_system/agents/_package/docs/secrets/README.md`), then use `$infra-onboard-machine`; never infer setup from file presence.
- Vault working files live in the full iCloud Obsidian Vault on registered Macs. A schema-v7 `remote-sshfs` Linux client may mount that complete worktree from its registered iCloud Mac host after `vault access status` proves the exact healthy source; code-only Linux hosts remain excluded. Only the registered primary Mac may have Vault Git metadata at `~/.local/share/vault-git/Vault.git`. Every iCloud worker and remote client remains Gitless and must never create a clone or sparse checkout.
- Normal Vault notes outside `.agents/` should not start with an H1 (`#`) because the note title already comes from its filename. Markdown files anywhere under `.agents/` may start with an H1 because they are agent artifacts such as plans and research. Use as little headings and text as possible when organizing or creating normal notes.
- A top-level context containing `_finance/` is a finance and tax-reporting workspace. Read that folder's `AGENTS.md` before handling its records, keep one `0_Yearly_Returns/YYYY.md` control note per relevant South African tax year, and treat the note as preparation evidence rather than proof of SARS submission. The legal issuer, account holder, or registered taxpayer determines which return owns a transaction; folder location alone never does.
- Never add hidden HTML comments "<!-- -->" to normal Vault notes. Do not put provenance, source paths, hashes, byte counts, move history, or agent-process metadata in note bodies; keep any necessary audit records under `_system/local/state/`.
- In context folders and `_library`, keep any folder home or directory note inside the folder it indexes and give it the same name as that folder.
- when writing links (internally, or url links) never format the link display text, and also make internal page links like "[[file name]]" not "[[path/to/file name]]" 
- For interactive remote scripts, stage a reviewed script first and invoke it with a separate standalone `ssh -t` command whose stdin is the real terminal. Never combine a password prompt with a pipe, heredoc, here-string, or encoded inline script. Read passwords through a TTY-aware API such as `getpass`; never pass them through `printf`, where a trailing newline can become part of the secret.
- Use `***` for Markdown thematic breaks in note bodies. Reserve standalone `---` lines for YAML frontmatter delimiters so body text cannot become a Setext heading.
- External skill-source repositories derive as `<registered Code root>/open_source/<repo-name>` and are declared in `_system/agents/_package/instance/skills/sources.json`. Resolve machine roots through `ctx9-agents config`; never hard-code a home path in a generic skill.


The managed Git workflow below applies only on the registered Vault Git-owner Mac. A Gitless iCloud worker or remote SSHFS client skips the entire Git block and follows **iCloud and Remote Worktrees** instead.

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

For this Vault repository only, the final staging scope supersedes the narrow task-scoped staging language in the managed Git block above on the primary Mac. After completing work there, run `git add -A`, update and stage the media manifest, verify the staged media state, commit every pending tracked and untracked non-ignored Vault change regardless of source or completeness, fetch and merge `origin/master`, and push. Repeat the complete-worktree commit if new changes appear before the final fetch. Completion requires a successful push unless an exact blocker is reported. A Gitless iCloud worker or remote client finishes its leased edits after host filesystem durability and never runs Vault Git. iCloud upload continues asynchronously and is not a task-completion gate. The primary commits and pushes the complete worktree currently visible to it without waiting for an upload receipt.

## Vault Host Boundary

- Run Vault tasks only from a registered full worktree: the primary iCloud Mac, a Gitless iCloud worker Mac, or a healthy full `remote-sshfs` client.
- On a remote client, run `vault access status` before reads and `vault access begin` before writes. A missing, read-only, degraded, wrong-source, or unregistered mount is a hard stop, not permission to create a clone or sparse checkout. Follow the $vault host gate and [[linux-remote-vault-access|Linux Remote Vault Access]].
- A task started on a code-only Linux or other non-participating host follows [[README-vault-host-boundary|Vault Host Boundary]] and stops before Vault-specific reads, writes, dispatch, handoff, waiting, polling, or SSH publication. Code-repository work remains valid and its executable plan stays self-contained in the owning repository.

## iCloud and Remote Worktrees

- The primary Mac and iCloud-participating worker Macs share one full set of Vault working files through iCloud. A registered remote client sees that same complete set through an exact-path SSHFS mount from its configured Mac host. Only the primary has the external Git directory referenced by the shared `.git` file. On every worker and remote client, that pointer must be dangling and `git -C "$(vault root)" rev-parse --git-dir` must fail.
- Treat the Vault as single-writer across Macs and remote clients. Before changing machines, stop edits and close unmanaged writers such as Obsidian and Vault-rooted tasks. Managed mutations require the shared host-side lease acquired with `vault access begin` and released only by a successful `vault access finish`.
- On an iCloud worker, mark the Vault folder **Keep Downloaded**, use **Download Now** when necessary for missing inbound files, and check for dataless files or iCloud conflict copies. Never wait for outbound iCloud upload before finishing a task. Do not run Vault Git, `vault git-preflight`, `vault refresh`, or Git-backed media maintenance there.
- On a remote client, keep the mount user-only and read-write, but never run Vault Git, refresh, release, agents sync, bootstrap publication, or Git-backed media maintenance. Git remains normal in ordinary Code repositories.
- `vault access finish` fsyncs changed files on the Mac host, records the session, releases the lease, and returns without waiting for iCloud. Receipts and upload state are diagnostic only. The primary does not wait for or verify a receipt before `vault git-preflight` and the complete-worktree commit.
- A stale lease is never stolen automatically. Recover an expired abandoned lease only after proving its writer stopped and recording an explicit reason through `vault access recover --reason "..."`.
- GitHub `origin` is the primary Mac's durable Git backup. iCloud transports Mac working files and local-only media bodies. Never copy or sync the primary's external Git directory.
- Scheduled and manual `vault refresh` are primary-only. Workers and remote clients may not register or execute the refresh schedule.

## First Read

1. Run `vault inventory` for live periods, contexts, task state, and source-note routing.
2. Use the routing index below, then follow folder READMEs until reaching the relevant SOP/tool/command doc.
3. Read relevant `<context-folder>/<context-folder>.md` before changing entity operating rules.
4. For public bootstrap/export work, read `_system/bootstrap/README.md` and `_system/docs/commands/Bootstrap Export.md`.

## Folder Map

- `_system/`: operating layer for shared Obsidian assets, agents, bootstrap, commands, docs, inboxes, local user data, migrations, sync, and tools. Read `_system/README.md`.
- `_system/agents/`: self-contained private agent package: approved dependencies, fleet desired state, workspaces, skills, configuration, portable workers, and verified aggregate state. Read `_system/agents/README.md`.
- `_system/deps/`: public Vault/bootstrap dependency manifest and installer; bootstrap only invokes it.
- `_system/tools/`: reusable tools outside `vault`. Read `_system/tools/README.md`.
- `_system/bootstrap/`: fresh install, public export, release, and upgrade framework.
- `_system/commands/`: `vault` dispatcher, commands, internals, and tests.
- `_system/docs/`: command, Obsidian, and workflow documentation.
- `_system/local/`: user-specific general configuration, per-skill configuration, env tooling, and runtime state. Read `_system/local/README.md`.
- `_system/local/state/`: ignored local reports, backups, and install/export state.
- `_library/`: learning, research dumps, swipe files, source material, thoughts. Read `_library/LIBRARY.md` before organizing it.
- `_wiki/`: synthesized reusable knowledge.
- `other/`: archive/holding area only when explicitly asked.
- Context folders: source-of-truth workspaces with local `<context-folder>.md` routing / home page and `_obsidian/` operating folders.

## Core Docs

- `_system/README.md`: vault architecture, folder model, data model, context folder rules.
- `_system/docs/commands/README.md`: `vault` command index and command docs routing.
- `_system/docs/commands/README-reference.md`: full command and bootstrap script inventory.
- `_system/docs/obsidian/README.md`: Obsidian profile/plugins/templates/UI.
- `_system/bootstrap/README.md`: bootstrap/export/upgrade mechanics.
- `_system/local/README.md`: local-data ownership and skill-config separation.
- `_system/local/env/README.md`: env workflow; placeholders only in tracked files.
- Machine registry, primary/worker coordination, connection routing, and code topology: [[_system/agents/skills/auto/_infrastructure/infra-code-folder-and-computer-topology/SKILL|Code Folder and Computer Topology skill]]


## When doing any of these things, read these first
e.g. if you need to save a task, read the `Tasks And Projects.md` first as specified below.

- Current state: `vault inventory`, source context notes, `Dashboard.md`.
- Tasks/projects/epics: `_system/docs/commands/Tasks And Projects.md`, then `<context-folder>/_obsidian/<tasks|projects|epics>/`.
- Calendar/time blocks: `_system/docs/commands/Google Calendar.md`, then `vault gcal`.
- Content: `_system/README.md#Content`, `_system/docs/commands/Content Schedules.md`, then the selected capability folders under `<context-folder>/_obsidian/content/`; schedules additionally require `content_schedules_enabled: true`.
- Scripts and `vault` commands: `_system/docs/commands/README.md`; open only the needed script doc.
- General tools and invoices: `_system/tools/README.md`, then relevant `README-<topic>.md` or tool README.
- Skills: `_system/agents/README.md`, `_system/agents/_package/docs/skills.md`, `_system/docs/commands/Agent Sync.md`.
- Agent skill-source repositories: `_system/docs/commands/Dependency Repos.md`, then `ctx9-agents update --skills`; public Vault dependencies remain under `_system/deps`.
- Fleet Code and personal agent configuration sync: `$infra-sync-code-workspaces`; topology supplies machine/repository facts and onboarding calls the same workflow.
- Complete approved fleet dependency, coding-tool, application, workspace-command, and skill-source updates: `$infra-update-fleet-dependencies`; routine convergence without seeking newer state remains `ctx9-agents sync`.
- Bootstrap/export/upgrade: `_system/bootstrap/README.md`, `_system/docs/commands/<Bootstrap Export|Public Vault Upgrade>.md`.
- Obsidian profile/UI/theme: `_system/docs/obsidian/README.md`, then `_system/docs/obsidian/editing_obsidian.md` if editing UI/CSS/plugin behavior.
- Keybindings: `_system/docs/keybindings/README.md`; fzf/tmux/cmux/btop shortcuts are consolidated in `terminal-keybindings.md`. Terminal commands and operating guidance: `_system/docs/terminal/README.md`; fleet terminal setup and repair additionally use `$infra-manage-fleet-terminal-workspaces`.
- Attachments: `_system/docs/commands/Attachments.md`. attachment's stored under owning top-level folder's `_obsidian/attachments/`
- Periodic notes: `<context-folder>/_obsidian/periodic/<daily|weekly|monthly|quarterly|yearly>/`=
- Private Git and pointer-only media: `_system/docs/commands/README-git.md`.
- Env/auth: `_system/local/env/README.md`.
- Brain Dump import: `_system/inbox/BRAIN_DUMP.md`
- Library changes: `_library/LIBRARY.md`.

## Operating SOPs

- Create TaskNotes tasks only for executable next actions, reminders, or decisions needing follow-up.
- Route unspecific capture to current default context from `vault inventory`.
- Use `scheduled` for work/surface date and `due` for deadline.
- Use native time fields: `timeEstimate`, `timeEntries`, `pomodoros`; do not use `duration`.
- Use `vault gcal create-event` for concrete appointments/travel/meetings/reservations; use `create-block` only for explicit time blocking.
- Use `_obsidian/content` for owned content items/ideas/publication definitions; use `_obsidian/tasks` for executable work about content.
- Keep proof-source notes explicit: commitment, data source, manual/automated status, missing-proof task/warning.
