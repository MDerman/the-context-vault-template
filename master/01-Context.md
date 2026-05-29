# 01-Context

This note is the source of truth for how this Obsidian workspace is organized.

For day-to-day Obsidian usage, keep these companion references nearby:

- [[obsidian-plugins-reference]]: installed/core plugins, what each one is for, and the configured workflows.
- [[obsidian-keyboard-shortcuts]]: current hotkeys and high-value keyboard workflows.
- [[obsidian-core-features]]: non-plugin Obsidian fundamentals for new users.
- [[obsidian-settings-and-examples]]: recommended settings, Markdown examples, and callout examples.

The root folder is the master vault. The numbered context folders are the source-of-truth workspaces. The old dash-prefixed folders are legacy source material and should be left alone until I intentionally migrate them.

## Mental Model

```text
root workspace = master control panel
numbered context folders = source-of-truth workspaces
master = operating manual, bootstrap, scripts, generated dashboards, agent context
library = raw and semi-processed learning material
wiki = LLM-constructed synthesis layer guided by wiki/AGENTS.md and wiki/karpathy-initial-proompt.md
master/agents = agent skills and agent-development process notes
master/general-tools = reusable scripts, Mac automation, and utility tools
other = archive or holding area for excess context folders and random file dumps
master/_obsidian/bases = master/global TaskNotes views
master/_obsidian/templates/shared = root-level shared non-periodic templates
master/_obsidian/excalidraw = master Excalidraw folder and shared Excalidraw scripts
<root-folder>/_obsidian/attachments = note attachments owned by that top-level root folder
<context-folder>/_obsidian/projects = project notes for that context folder
<context-folder>/_obsidian/epics = epic notes for that context folder
```

The master vault is the only Obsidian workspace. Context folders are source-of-truth folders inside it, not standalone vaults.

## Context Folder Map

Configured context folders:

- `01-personal`: personal life, goals, health, values, finances, relationships, home, reflection, default capture. Active by default.
- `02-personal-brand`: personal brand, public writing, content, media, audience, offers, reputation. Active by default.
- `03-business`: Impression business workspace. Active by default.
- `04-dev`: development, contracting, software projects, job applications, technical work. Archived by default.
- `05-claudeche`: Claudeche workspace. Archived by default.

Each context folder has a `HOME.md` file. Its `status` property controls whether that context folder appears in default generated agent periodic rollups:

- `status: active`: included when the generator is run with no context folder arguments.
- `status: archived`: still available, but excluded from default rollups.
- blank, null, or missing status: treated as not active.

Its `content_enabled` property controls whether that context folder gets content infrastructure:

- `content_enabled: true`: content storage, content schedules, publication definitions, cadence config, and content views are scaffolded.
- `content_enabled: false`: no content scaffold by default.

Its `default_capture` property controls the default place for unspecific tasks and periodic capture:

- `default_capture: true`: preferred capture context folder.
- if no folder is marked, scripts fall back to the first active context folder.

The default active working set is `01-personal`, `02-personal-brand`, and `03-business`.

The content-enabled working set is `02-personal-brand` and `03-business`.

`HOME.md` is the context folder's local routing map. Its frontmatter is the control panel:

```yaml
---
status: active
content_enabled: false
default_capture: true
---
```

Use `status: archived` for inactive-but-kept context folders, or leave the status blank for not active.

## Folder Rules

Each context folder uses this internal `_obsidian` operating structure:

```text
<context-folder>/
  HOME.md
  DECLARATION.md
  _obsidian/
    attachments/
    bases/
    excalidraw/
    content-schedules/ # content-enabled folders only
    epics/
    periodic/
      daily/
      weekly/
      quarterly/
      yearly/
    projects/
    tasks/
    templates/
      periodic/
  <context-specific folders, such as docs/>
```

Content-enabled context folders also use:

```text
<context-folder>/DECLARATION/content-cadence.json
<context-folder>/_obsidian/content-schedules/
<context-folder>/_obsidian/content/
  publications/
    blogs/
    newsletters/
    youtube/
  items/
    blog-posts/
    newsletter-issues/
    youtube-videos/
    social-posts/
  ideas/
  archive/
```

`DECLARATION/content-cadence.json` is the source of truth for recurring publication cadence. `content.py` creates the current fixed 4-week planning note under `_obsidian/content-schedules` from enabled cadence JSON and maintains the `Current content schedule:` line in the context folder `DECLARATION.md`. Normal refresh is create-only and does not overwrite existing content schedule notes.

Content schedule config supports `schedule_format` values:

- `weekly`: week headings with all slots in chronological order.
- `weeklyThenByPublication`: week headings, then publication headings inside each week.
- `publicationThenByWeek`: publication headings, then week headings inside each publication. This is the default.

Use `publication_order` to choose the publication heading order. Explicitly regenerate an existing managed schedule with:

```bash
vault content --context-folders 02-personal-brand --date 2026-05-13 --force
```

Context folder-owned operating folders live under `_obsidian` so ordinary work folders can sit directly under the context folder root and remain visually distinct. There is no default `notes` folder.

Note attachments should live under the owning top-level root folder's `_obsidian/attachments` directory. For example, attachments used by `library/...` notes belong under `library/_obsidian/attachments`, and attachments used by `03-business/...` notes belong under `03-business/_obsidian/attachments`. Obsidian's built-in paste destination is the temporary inbox `master/_obsidian/attachments/_inbox`; run `attachments.py` to route inbox and imported attachments into the correct root folder.

`_obsidian/tasks`, `_obsidian/projects`, `_obsidian/epics`, and root `DECLARATION.md` are the standard operating surfaces:

- `_obsidian/tasks`: TaskNotes task notes.
- `_obsidian/projects`: ordinary project notes.
- `_obsidian/epics`: ordinary epic notes.
- `DECLARATION.md`: entity-specific answers for Identity and Momentum. Social Selling lives inside Momentum when relevant.
- `_obsidian/content`: owned content assets, publication definitions, and content views for content-enabled entities only.

Context folders are for actual operating information: current source-of-truth notes, docs, assets, tasks, periodic notes, SOPs, internal training, decisions, and material actively used by that context folder. They are not for samples, downloaded templates, general learning notes, course notes, research dumps, or notes about learning. Learning material belongs in `library`; durable synthesis belongs in `wiki`. Non-entity random thoughts belong in `library/thoughts`.

If something learned in `library` or `wiki` should become part of a context folder, promote it deliberately into that context folder as an operating artifact, such as an SOP, keep-in-mind note, employee training note, checklist, policy, decision record, declaration update, or active reference.

## Relay Collaboration

Relay is for sharing selected folders between vaults while keeping each person's private context in their own vault. Shared folders should be explicit operating spaces, such as `library` or a context folder. Do not assume another person's whole vault is shared.

Fastest setup for joining the same Relay workspace:

1. Run the public Context9 vault setup from the root `README.md`.
2. Open Obsidian at `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`.
3. Enable community plugins when prompted.
4. Open Relay settings.
5. Ask the host for the Relay host name and workspace invite/details.
6. Sign in or join the same Relay workspace.
7. Share or download the folders you need, commonly `library` and the relevant context folder.
8. Reload Obsidian.
9. Check the Relay sync status panel.

Bootstrap export includes plugin metadata/styles, but excludes plugin bundles and local plugin data/config. Users install or configure plugins locally after setup.

Entity operating-system answers live in `DECLARATION.md` rather than `HOME.md`. `HOME.md` explains what each local folder is for and where to store or find information. Master system notes under `master/02-Identity.md` and `master/03-Momentum.md` use Sync Embeds to show enabled declaration sections. Declarations keep one file-title H1 and use H2 for embeddable sections such as `Identity` and `Momentum`, because Sync Embeds section isolation is more reliable below H1. Social Selling uses an H3 under Momentum for personal-brand entities.

Reusable cross-context assets, agent skills, Mac automation, scripts, generated outputs, and utility files live under `master`.

`other` is the archive/dump zone. Use it for excess context folders, uncertain imports, miscellaneous old projects, and files that should not yet be promoted into an active context folder, `library`, or `wiki`.

## Master Folder

`master` is the operating layer.

Important paths:

- `master/00-StartHere.md`: walkthrough for the operating systems layer.
- `master/01-Context.md`: this note.
- `master/02-Identity.md`: identity system rollup.
- `master/03-Momentum.md`: momentum/accountability/social selling system rollup.
- `master/system/context/OBSIDIAN-PROFILE.md`: Obsidian profile, plugin, template, color, icon, Bases, calendar, and Sync Embeds reference.
- `master/system/context/SCRIPTS.md`: main scripts and normal refresh workflows.
- `master/system/context/SCRIPT-REFERENCE.md`: fuller script reference, including secondary and one-time scripts.
- `master/_obsidian/notes/operating-methods`: durable source notes for elimination, dreamlining, automation, and mini-retirement principles.
- `master/system/bootstrap/init_vault.sh`: first-run fresh/exported vault setup entrypoint.
- `master/system/bootstrap/bootstrap_vault.py`: generic bootstrap CLI.
- `master/system/bootstrap/bootstrap-export.json`: public export config, including context folder output mapping and export root.
- `master/system/bootstrap/AGENTS.template.md`: editable source for generated root agent instructions.
- `master/system/bootstrap/generate_agents.py`: generates root `AGENTS.md` and agent symlinks from discovered context folders.
- `master/system/bootstrap/install_dependencies.sh`: local dependency installer/checker for vault bootstrap commands.
- `master/system/bootstrap/install_vault_command.py`: installs the `vault` dispatcher into `~/.local/bin`.
- `master/system/bootstrap/sync-agent-skills.sh`: links local coding-agent skill folders to `master/agents/skills`.
- `master/system/scripts/bootstrap_export.py`: exports the public bootstrap vault from the current vault.
- `master/system/scripts/upgrade.py`: upgrades public bootstrap installs from hidden upstream Git state outside iCloud.
- `master/system/scripts/vault.py`: terminal dispatcher installed as `vault` in `~/.local/bin`.
- `master/system/scripts/content.py`: creates current fixed 4-week content schedule notes from enabled cadence JSON.
- `master/system/scripts/periodic.py`: creates agent-readable periodic rollups for the current active or selected context folder set.
- `master/system/scripts/delete_master_periodic_notes_for_now.py`: deletes current generated master periodic rollups, and can also clean selected context folder source notes.
- `master/system/scripts/attachments.py`: dry-run, apply, and verify note attachment routing across root folders. Reports and quarantine output go to `~/Downloads/vault-generated/`.
- `master/system/scripts/context.py`: creates compact agent-readable context.
- `master/system/scripts/folder.py`: creates/registers a new context folder from the scaffold template.
- `master/Dashboard.md`: generated refresh dashboard with current periodic, content schedule, context home, and key Base links.
- `master/_obsidian/bases`: master dashboards.
- `master/system/context/*.md`: generated agent-readable system packets and periodic rollups.
- `master/_obsidian/bases`: master TaskNotes command views.
- `master/system/context`: generated agent context, realized system notes, agent periodic rollups, and durable agent operating notes.
- `master/_obsidian/templates/shared`: shared non-periodic templates, system templates, and shared task template.
- `master/_obsidian/templates/shared/content`: shared content and publication templates.
- `master/_obsidian/excalidraw`: master Excalidraw folder and source for shared Excalidraw scripts copied into each context folder.

Generated files contain a managed marker. The bootstrap updates generated files, but skips existing non-managed files.

Root agent files:

- `AGENTS.md`: generated instructions for Codex, Claude, and other coding agents. Edit `master/system/bootstrap/AGENTS.template.md`, then rerun `python3 master/system/bootstrap/generate_agents.py`.
- `CLAUDE.md`: symlink to `AGENTS.md`.
- `.agents/skills`: agent skills folder.
- `.claude/skills`: symlink to `.agents/skills`.

Context folders do not have their own Obsidian profiles or agent symlinks. Open the root workspace for Obsidian and agent work.

## Periodic Notes

Context folder periodic notes are the source of truth:

```text
<context-folder>/_obsidian/periodic/daily/YYYY-MM-DD.md
<context-folder>/_obsidian/periodic/weekly/YYYY-Www.md
<context-folder>/_obsidian/periodic/quarterly/YYYY-Qn.md
<context-folder>/_obsidian/periodic/yearly/YYYY.md
```

From the master vault, Periodic Notes defaults to `01-personal`. Opening today's daily note in the root workspace creates or opens:

```text
01-personal/_obsidian/periodic/daily/YYYY-MM-DD.md
```

Generated agent periodic rollups live separately:

```text
master/system/context/YYYY-MM-DD.md
master/system/context/YYYY-Www.md
master/system/context/YYYY-Qn.md
master/system/context/YYYY.md
```

Those agent notes are script-generated composed views. They inline the selected context folder source notes:

````md
## 03-business

_Source: `03-business/_obsidian/periodic/quarterly/2026-Q2.md`_
````

Context folder periodic notes remain the editable source of truth. The agent rollups are generated read-only files for agents that cannot rely on Obsidian plugin rendering. Sync Embeds reference notes are still kept here for older Obsidian-facing rollups and system notes:

```text
master/system/obsidian_notes/beta_plugins_docs/README-sync-embeds.md
```

The generator creates missing context folder periodic notes from each context folder's own local `_obsidian/templates/periodic/<period>-template.md` file, which is the same template path configured in Obsidian. `01-personal` has filled-in starter templates. The other context folders intentionally have blank periodic template files until I customize them.

Generate agent rollups with:

```bash
vault periodic
vault periodic --all
vault periodic --context-folders 04-dev,05-claudeche
```

`context.py` calls this generator for the default refresh path, so one agent-context refresh updates context, realized system notes, and current agent periodic rollups.

Clean current generated master periodic rollups with:

```bash
python3 master/system/scripts/delete_master_periodic_notes_for_now.py
python3 master/system/scripts/delete_master_periodic_notes_for_now.py --context-folders 04-dev,05-claudeche
```

No args deletes the current generated master rollups under `master/system/context`. Use `--context-folders` or `--all` when you also want to clean current context folder source notes.

Monthly periodic notes are intentionally not used.

## TaskNotes

TaskNotes uses one Markdown file per task. Task files live in context folders:

```text
<context-folder>/_obsidian/tasks/
```

The default task status is `backlog`. The configured statuses are:

- `backlog`
- `up-next`
- `to-be-resumed`
- `ongoing`
- `in-progress`
- `done`
- `archived`

In the master vault:

- Default task context is `01-personal`.
- Default task folder is `{{context}}/_obsidian/tasks`.
- A task with context `03-business` goes to `03-business/_obsidian/tasks`.
- A task with no chosen context defaults to `01-personal/_obsidian/tasks`.
- Master TaskNotes command views live in `master/_obsidian/bases`.

In a context folder:

- Default task folder is local `_obsidian/tasks`.
- Default context is that context folder.
- TaskNotes views live in local `_obsidian/tasks` and context dashboards live in local `_obsidian/bases`.

TaskNotes Kanban Bases group columns by `status` and use the `projects` field as horizontal swimlanes, so a board can be scanned by status across each project band.

TaskNotes shorthand in the task creation modal:

- `#tag`: adds an Obsidian tag.
- `@context`: sets context and routes the task to that context folder in the master vault, for example `@03-business`.
- `+project` or `+[[Project Name]]`: links a project, usually a note in `<context-folder>/_obsidian/projects`.
- `tomorrow`, `next Friday`, `January 15 at 3pm`: parsed as dates/times.
- `high`, `normal`, `low`: parsed as priority words.
- `!`: configurable priority trigger; TaskNotes supports it, but it may need to be enabled.
- `backlog`, `up-next`, `to-be-resumed`, `ongoing`, `in-progress`, `done`, `archived`: parsed as status words.
- `*`: configurable status trigger.
- `2h`, `30min`, `1h30m`: parsed as time estimates.
- `daily`, `weekly`, `every Monday`: parsed as recurrence.

Task frontmatter should keep work routing and hierarchy separate:

```yaml
---
title: Example task
status: backlog
priority: normal
due: 2026-06-01
timeEstimate: 60
contexts:
  - 03-business
projects:
  - "[[03-business/_obsidian/projects/Example Project|Example Project]]"
epic: "[[03-business/_obsidian/epics/Example Epic|Example Epic]]"
tags:
  - task
---
```

TaskNotes date properties use the plugin's native frontmatter names:

- `scheduled`: the date to start, surface, or intentionally work on the task.
- `due`: the deadline or true due date.
- Do not use `due_date` or `scheduled_date` for TaskNotes tasks; the current Bases and generated context read `due` and `scheduled`.
- New tasks should not get a `scheduled` date by default. Add `scheduled` only when you intentionally want the task to appear on a specific work date.

Google Calendar task mirrors:

- `Time Blocks`: broad manual or AI-created calendar blocks for planning the day/week. These are normal Google Calendar events, not TaskNotes tasks.
- `Scheduled Tasks`: two-way mirror of TaskNotes `scheduled` values.
- `Due Tasks`: two-way mirror of TaskNotes `due` values.
- Use `vault gcal list --days 7 --calendar all --json` when agents need low-context calendar awareness.
- Agents may create/edit `Time Blocks` through `vault gcal create-block`, but must not create arbitrary events on personal or business calendars.
- Broad work planning should usually use `Time Blocks`; avoid adding `scheduled` to ordinary tasks unless the task truly needs a specific work date/time.
- Native TaskNotes Google export should stay disabled unless intentionally replacing the vault mirror, because the custom mirror owns the separate `Scheduled Tasks` and `Due Tasks` calendars.
- `vault gcal calendars ensure --apply` sets default popup reminders: `Time Blocks` at event start, `Scheduled Tasks` at event start, and `Due Tasks` at event start plus 25 minutes before. The Google Calendar API does not expose the UI-only all-day default reminder time; set "0 days before at 9:00 AM" manually in Google Calendar if needed.
- Context Nine runs `vault gcal sync-tasks --apply` every 5 minutes while Obsidian is open. `vault refresh` also runs the sync once before regenerating context.

TaskNotes time properties use the plugin's native frontmatter names:

- `timeEstimate`: planned effort in minutes. Natural-language input such as `30min`, `1h`, or `1h30m` writes this field.
- `timeEntries`: actual tracked time entries created by TaskNotes time tracking.
- `pomodoros`: Pomodoro session records/counts when using the Pomodoro integration.
- Do not use a generic `duration` field for TaskNotes task effort; use `timeEstimate` for estimates and TaskNotes time tracking for actuals.

Sprints are intentionally not modeled in this workspace. If imported material contains sprint data, ignore it unless I explicitly ask to archive it somewhere.

## Content

Content-enabled context folders store owned content in `_obsidian/content`. This is for assets, drafts, publication definitions, ideas, and content planning. It is not the task system.

Current content-enabled entities:

- `02-personal-brand`: Matt Derman blog, Copy and Context, YouTube, LinkedIn, X, and Substack Notes.
- `03-business`: Impression blog and AI LinkedIn Insights.

Content item frontmatter:

```yaml
---
type: content
entity: 02-personal-brand
content_kind: blog-post
platform: blog
publication: matt-derman
status: idea
publish_date:
source:
repurposed_from:
cta:
conversion_goal:
---
```

Publication frontmatter:

```yaml
---
type: publication
entity: 02-personal-brand
publication_type: newsletter
publication_id: copy-and-context
name: Copy and Context
status: active
primary_cta:
---
```

Master content rollup:

```text
master/_obsidian/bases/content-calendar.base
master/_obsidian/bases/content-kanban.base
```

The master content rollups are a publish calendar and a status pipeline board. `content-calendar.base` shows all content-enabled context folders, with switchable calendar views for each context folder and each platform. Calendar views use the Calendar Bases plugin, which renders a FullCalendar-style calendar from the `publish_date` property while preserving `type: content` frontmatter.

Entity content views:

```text
<context-folder>/_obsidian/bases/content-dashboard.base
<context-folder>/_obsidian/bases/content-queue.base
<context-folder>/_obsidian/bases/content-calendar.base
<context-folder>/_obsidian/bases/content-kanban.base
```

Entity `content-calendar.base` files open with a `Publish Calendar` view. Dragging a calendar item updates that note's `publish_date`.

`content-kanban.base` opens with an `All Content Board` kanban-view grouped by `status`, then platform-specific board views for Blog, Newsletter, YouTube, LinkedIn, X, Substack, and broad Social items. These are true vertical status lanes powered by `kanban-bases-view`, not the built-in Bases cards layout.

V1.1 includes a one-time dry-run migration script for old Matt blog and YouTube notes. The script is intentionally not run as part of bootstrap.

## Projects And Epics

Projects and epics are ordinary Obsidian notes, not TaskNotes tasks.

Project notes live in:

```text
<context-folder>/_obsidian/projects/
```

Project note frontmatter:

```yaml
---
type: project
status: backlog
contexts:
  - 03-business
epic: "[[03-business/_obsidian/epics/Example Epic|Example Epic]]"
---
```

Epic notes live in:

```text
<context-folder>/_obsidian/epics/
```

Epic note frontmatter:

```yaml
---
type: epic
status: backlog
contexts:
  - 03-business
---
```

Use epics for larger themes or areas of work, projects for concrete workstreams, and TaskNotes tasks for the executable next actions and reminders.

## Bases

Bases are dashboards over files and their properties.

Master bases:

- `master/_obsidian/bases/tasks-today.base`
- `master/_obsidian/bases/content-kanban.base`
- `master/_obsidian/bases/tasks-this-week.base`
- `master/_obsidian/bases/epics-all.base`

The master project and epic Bases consolidate active context folders only by default. Archived context folders remain available, but they are excluded from those default master views.

Context folder bases:

- `<context-folder>/_obsidian/bases/context-dashboard.base`
- `<context-folder>/_obsidian/bases/projects-dashboard.base`
- `<context-folder>/_obsidian/bases/epics-dashboard.base`
- `<context-folder>/_obsidian/bases/content-dashboard.base` for content-enabled context folders.
- `<context-folder>/_obsidian/bases/content-kanban.base` for platform-specific content boards.

TaskNotes' own command views are separate from these dashboards. The master command views are in `master/_obsidian/bases`; context folder command views and dashboards live under local `_obsidian` folders.

# Plugins

## Content Calendars

Content views use the Bases-native plugin layer:

- `calendar-bases`: adds Calendar layout support to Obsidian Bases and powers `master/_obsidian/bases/content-calendar.base` plus `<context-folder>/_obsidian/bases/content-calendar.base`.
- `kanban-bases-view`: adds the `kanban-view` layout for Obsidian Bases and powers `master/_obsidian/bases/content-kanban.base` plus `<context-folder>/_obsidian/bases/content-kanban.base`.
- `obsidian-full-calendar`: installs the FullCalendar integration for vault calendars. Native Full Calendar event notes are separate from content notes because they expect event frontmatter; content notes stay on the `type: content` schema and render through Calendar Bases.

The old markdown Kanban plugin is available in the vault, but it is not the content pipeline source of truth. Content pipeline state lives in `_obsidian/content` note frontmatter and is rendered through Bases.

## Sync embeds

Sync Embeds turns embedded notes into editable blocks. Master periodic rollups use this syntax:

````md
```sync
![[01-personal/_obsidian/periodic/daily/2026-05-10]]
```
````

Reference notes for the installed beta plugin live at:

```text
master/system/obsidian_notes/beta_plugins_docs/README-sync-embeds.md
```

## Omnisearch

Omnisearch is installed and enabled as the preferred fast search layer. Its community plugin id is `omnisearch`.

Use it when the goal is to find notes and indexed files quickly by relevance. It behaves like a stronger Quick Switcher: it scores results using the query terms in the filename, directory, headings, and note body, and it is resistant to small typos.

Primary commands and hotkeys:

- `Omnisearch: Vault search`: `Shift then Shift` through Doubleshift, with `Cmd+Shift+F` kept as the fallback hotkey.
- `Omnisearch: In-file search`: `Cmd+F`. This searches inside the active Markdown note and jumps to the selected match with `Enter`.
- Core Global Search remains available on `Cmd+Shift+P`.
- TaskNotes and Context Nine task capture: `Alt+T` opens the native TaskNotes new task dialog for quick capture; `Alt+Cmd+T` opens the same dialog and injects selected Markdown into task details on save, while behaving like normal TaskNotes new task when nothing is selected; `Alt+Cmd+Y` appends the current selection to an existing TaskNotes task and routes selected attachments immediately.
- Context Nine file actions: `Cmd+Backspace` deletes the hovered or selected file with Obsidian's normal confirmation and does not fall back to the active note; `Alt+Cmd+Backspace` is Obsidian's deliberate current-file delete shortcut; `Cmd+N` creates a note in the hovered file-explorer folder, falling back to normal new note behavior otherwise.
- Doubleshift plugin id: `obsidian-doubleshift`. It maps double-tapping left Shift to `omnisearch:show-modal`.

Workflow:

- Use Vault search to find the most relevant document across the vault.
- Press `Tab` from a Vault search result to inspect the matches inside that one note with In-file search.
- Use In-file search directly from an active Markdown note to skim matches; it is unavailable when the active file is not Markdown.

Advanced query tips:

- `path:"somepath"` restricts results to matching paths.
- `ext:"png jpg"`, `ext:png`, or a plain `.png` filters by file type.
- `"exact expressions"` in quotes further filter returned results.
- `-exclusions` removes notes containing excluded words.

PDF, Office document, and image indexing depend on the Text Extractor plugin. Those extra indexing modes are not currently enabled in Omnisearch settings.


## Templater

Templater is set to trigger on new file creation. Folder templates route new notes based on where they are created.

In the master vault:

- `<context-folder>/_obsidian/periodic/daily` uses `<context-folder>/_obsidian/templates/periodic/daily-template.md`.
- `<context-folder>/_obsidian/periodic/weekly` uses `<context-folder>/_obsidian/templates/periodic/weekly-template.md`.
- `<context-folder>/_obsidian/periodic/quarterly` uses `<context-folder>/_obsidian/templates/periodic/quarterly-template.md`.
- `<context-folder>/_obsidian/periodic/yearly` uses `<context-folder>/_obsidian/templates/periodic/yearly-template.md`.
- `<context-folder>/_obsidian/tasks` uses `master/_obsidian/templates/shared/default-tasks-template.md`.

Periodic templates can include `{{current_content_schedule_sync_embed}}`. The periodic generator replaces it with a Sync Embeds block pointing at the active 4-week content schedule when that context folder has enabled cadence JSON.

Shared declaration templates live in:

```text
master/_obsidian/templates/shared/declarations/
```

They are copied or adapted into each active entity's root `DECLARATION.md`.

Each context folder has local `_obsidian/templates` for context-specific periodic templates. Shared non-periodic templates stay under `master/_obsidian/templates/shared`.

Each context folder owns its local periodic templates under `_obsidian/templates/periodic`. `master/_obsidian/templates/shared` intentionally does not contain a `periodic` folder.

Agent periodic rollup notes under `master/system/context` are script-owned. There are no Templater folder rules for manually creating agent rollups.

## Excalidraw

The master Excalidraw folder is:

```text
master/_obsidian/excalidraw
```

The Excalidraw scripts source folder is:

```text
master/_obsidian/excalidraw/Scripts
```

The bootstrap copies that scripts folder into each context folder:

```text
<context-folder>/_obsidian/excalidraw/Scripts
```

The master Excalidraw plugin points to `master/_obsidian/excalidraw`. Context folder Excalidraw files live in local `_obsidian/excalidraw`.

## Library And Wiki

`library` stores learning material, references, swipe files, raw notes, imports, downloaded examples, templates being studied, lead magnets, course material, research dumps, and source material. It can be messy.

`wiki` is for synthesized notes constructed by LLMs according to:

- `wiki/AGENTS.md`
- `wiki/karpathy-initial-proompt.md`

A wiki note should be clearer, more reusable, and more deliberate than the source material in `library`. It should explain concepts, patterns, principles, and reusable knowledge.

Context folders are not learning folders. They are source-of-truth operating spaces for what is happening and being used inside that context folder.

## Linear Calendar Workflow

The linear calendar reference lives at:

```text
master/TODO/Calendar-Lineal-en.md
```

The linear calendar belongs in `master` because it is a workflow/reference pattern, not a context folder source note. If I create recurring planning artifacts from it, the actual dated notes should still live under the relevant context folder's `_obsidian/periodic` folder.

## Bootstrap Export Workflow

The current vault is the source of truth. Public bootstrap export copies a runnable subset to the configured export root:

```bash
vault bootstrap-export --dry-run
vault bootstrap-export --force
```

Default export root:

```text
~/Code/vault-public
```

Configured context folder mapping:

```text
01-personal -> 01-personal
02-personal-brand -> 02-personal-brand
03-business -> 03-business
```

The export copies root agent wiring, root `.obsidian` profile files with configured exclusions, `master` minus generated outputs, empty `library`, and `wiki/AGENTS.md`. Context exports copy `HOME.md`, `DECLARATION.md`, `DECLARATION/`, `_obsidian` folder structure, `_obsidian/bases/**/*.base`, and `_obsidian/templates/**/*.md`.

The root public `README.md` is exported from `master/system/bootstrap/README-bootstrap.md`. It documents the new-machine clone-to-iCloud flow. Internal bootstrap/export mechanics live in `master/system/bootstrap/bootstrapdocs.md`. `--force` mirrors export-owned content into `~/Code/vault-public` without deleting the export root or repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, or contribution docs. Export ownership is tracked in `.bootstrap-export-manifest.json`; legacy exports without a manifest are cleaned at the export-root child level while preserving repo metadata.

Root `.obsidian` is exported through the bootstrap exporter with sensitive path-name exclusions. Plugin directories export only public metadata/styles; plugin bundles and integration config files that may contain local settings or credentials are excluded from public export.

Public installs run `init_vault.sh --no-git` by default. Their installer stores upstream public repo Git state outside iCloud under `~/Library/Application Support/matt-vault-bootstrap/<install-id>/upstream.git`, removes the vault `.git` pointer, and writes `.vault-bootstrap/install.json`. Future setup updates use:

```bash
vault upgrade --dry-run
vault upgrade --apply
vault upgrade doctor
```

Upgrade behavior is controlled by `.vault-bootstrap/policy.json`: scripts/tools/plugin code/root wiring are replaced from upstream, user notes/tasks/declarations are preserved, and versioned migrations under `master/system/migrations/` handle user-owned schema changes when a release enables them. The `vault-upgrade-repair` skill is the fallback for failed migrations or report-driven manual fixes.

Add a new context folder with:

```bash
vault folder -n 06-new-context-folder -s active
vault folder -n 06-new-context-folder -s archived
```

The add-context-folder script creates the context folder structure directly, writes a status-only `HOME.md`, creates local templates/shared-template links, and reruns bootstrap with the discovered context folder list.

Root `.obsidian` is the live Obsidian profile source. Bootstrap does not copy or patch Obsidian profile settings.

## Mobile Obsidian Profile

iPhone must use a separate Obsidian config folder so desktop community plugins do not re-enable on mobile. In Obsidian iOS, set `Settings → Files and links → Override config folder` to:

```text
.obsidian-mobile
```

Then keep `.obsidian-mobile` managed by:

```bash
vault mobile-profile
```

The mobile profile intentionally enables only:

- `tasknotes`
- `calendar`
- `periodic-notes`
- `sync-embeds`
- `obsidian-style-settings`
- `obsidian-file-color`
- `obsidian-icon-folder`

This keeps TaskNotes, Calendar, Sync Embeds, theme/style settings, file colors, and icons on mobile while excluding heavy or desktop-oriented plugins such as `terminal`, `context-nine`, `templater-obsidian`, `omnisearch`, and generators. The script copies the current desktop theme, enabled CSS snippets, required plugin folders/settings, and key core settings such as `daily-notes.json` into `.obsidian-mobile`; it prunes unapproved mobile plugin/theme/snippet folders by default.

## Agent Workflow

Agents should start here:

```text
master/system/context/CONTEXT.md
```

Then read:

```text
AGENTS.md
```

The agent context generator writes:

```text
master/system/context/CONTEXT.md
master/system/context/context.json
master/system/context/*.md
```

These files summarize active periods, context folder statuses, realized system notes, current agent periodic rollups, and TaskNotes tasks.

Regenerate them with:

```bash
vault context
```

Agents should read context folder `HOME.md` status before assuming a context folder belongs in the default working set.

## Migration Rule

Migration from legacy folders is a separate project. Move one small slice at a time from a legacy folder into the matching numbered context folder. Do not bulk move everything just because the new structure exists.
