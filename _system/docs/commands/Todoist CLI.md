---
type: agent-reference
status: enabled
---
# Todoist CLI

Use official Todoist CLI `td` for simple personal Todoist tasks.

## Install

```bash
npm install -g @doist/todoist-cli
td --help
```

## Auth

Use interactive auth when setting up manually:

```bash
td auth login
td auth status
```

Use the CLI's native credential manager for both interactive and scripted work:

```bash
td auth status
```

The legacy `TODOIST_API_TOKEN` placeholder remains only until its quarantined Vault source crosses protected equality and deletion review. Do not use or update that source.

## Simple Tasks

Add an inbox task with Todoist natural language due text:

```bash
td add "Set alarm for July 7 wake-up Jul 6 5am"
```

List inbox tasks:

```bash
td inbox
```

Complete a task:

```bash
td task complete "Task name"
```

Delete a task:

```bash
td task delete "Task name" --yes
```

Use due dates only for this workflow. Do not add Todoist reminders unless explicitly asked.
