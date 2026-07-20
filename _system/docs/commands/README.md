---
type: agent-reference
status: enabled
---
# Scripts

Use terminal command first:

```bash
vault --help
```

Main script implementations live in:

```text
_system/commands/
```

Vault Command Center command labels, argument arrays, and hover descriptions are shared through [[_system/commands/vault-commands.json]]. Update that JSON when a cockpit-visible command description changes.

For global routing, read root [[AGENTS]]. For tool and skill SOPs, read [[_system/tools/README|general tools README]] or [[_system/agents/README|agents README]].

Open only the script doc needed for the current task. Create a separate `README-<topic>.md` only when a command needs richer examples, SOPs, or quick start notes.

## Script Docs

- [[_system/docs/commands/Root|Root]]
- [[_system/docs/commands/Init Vault|Init Vault]]
- [[_system/docs/commands/Bootstrap Export|Bootstrap Export]]
- [[_system/docs/commands/Public Vault Upgrade|Public Vault Upgrade]]
- [[_system/docs/commands/Dependency Repos|Dependency Repos]]
- [[_system/docs/commands/Agent Skills Sync|Agent Skills Sync]]
- [[_system/docs/commands/Refresh|Refresh]]
- [[_system/docs/commands/Inventory|Inventory]]
- [[_system/docs/commands/Machines|Machines]]
- [[_system/docs/commands/Tasks And Projects|Tasks And Projects]]
- [[_system/docs/commands/Content Schedules|Content Schedules]]
- [[_system/docs/commands/Periodic Rollups|Periodic Rollups]]
- [[_system/docs/commands/Epics|Epics]]
- [[_system/docs/commands/Google Calendar|Google Calendar]]
- [[_system/docs/commands/Brain Dump|Brain Dump]]
- [[_system/docs/commands/Attachments|Attachments]]
- [[_system/docs/commands/Context Folders|Context Folders]]
- [[_system/docs/commands/Obsidian Profile|Obsidian Profile]]
- [[_system/docs/commands/Todoist CLI|Todoist CLI]]
