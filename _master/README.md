# Master Operating Layer

This folder holds vault operating docs, scripts, bootstrap/export machinery, agent skills, reusable tools, generated context, and Obsidian support files.

Read next:

- [[_master/01-Context|01-Context]] for vault architecture, folder model, context folder rules, tasks, projects, epics, content, dashboards, and Relay collaboration.
- [[_master/system/README|System README]] for bootstrap, public export, upgrade mechanics, and system folder map.
- [[_master/system/context/README-scripts|Scripts README]] for `vault` commands and command docs routing.
- [[_master/system/context/README-script-reference|Script Reference]] for full script inventory and one-time script cautions.
- [[_master/system/context/README-obsidian-profile|Obsidian Profile]] for plugins, settings, templates, UI, and profile details.
- [[_master/agents/README|Agents README]] for shared skills and skill storage.
- [[_master/general-tools/README|General Tools README]] for reusable tools outside the `vault` dispatcher.
- [[_master/env/README|Env README]] for env workflow and tracked placeholders.

Folder map:

- `system/`: bootstrap, public export, `vault` scripts, generated context, migrations, Obsidian notes, and system-local state.
- `agents/`: shared active skills, manual-only skills, dormant skill storage, and skill backups.
- `general-tools/`: reusable tools that do not belong behind `vault`.
- `env/`: env tooling docs, placeholders, and loader scripts.
- `_obsidian/`: master-level Obsidian templates, bases, notes, attachments, and periodic notes.
- `backup-and-sync/`: rclone backup/sync tooling.

Naming standard:

- Use `README.md` for folder doorway docs.
- Use `README-<topic>.md` for companion SOPs, references, and quick starts.
- Use `AGENTS.md` only for agent behavior and routing policy.
