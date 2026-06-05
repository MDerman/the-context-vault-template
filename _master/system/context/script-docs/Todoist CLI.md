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

For script/env use, keep the real token in ignored `_master/env/.env` and load it before running `td`:

```bash
TODOIST_API_TOKEN=
source "$(vault root)/_master/env/load-env.sh"
td auth status
```

`TODOIST_API_TOKEN` in `_master/env/.env.base` is only a placeholder. Do not put real tokens in tracked files.

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
