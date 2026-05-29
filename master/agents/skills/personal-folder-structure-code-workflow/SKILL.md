---
name: personal-folder-structure-code-workflow
description: Locate Matt Derman's local code workspace, vault, repo categories, and preferred checkout destinations. Use when deciding where repos, references, open source checkouts, vault files, personal projects, or local tooling should live on Matt's machine.
---

# Personal Folder Structure And Code Workflow

Use this skill for local placement/routing only.

Roots:

- Code lives under `~/Code`.
- Vault lives at `/Users/matthewderman/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault`; prefer `vault root` when available.
- Agent skills live under `$(vault root)/master/agents/skills`.

Code folder meanings:

- `open_source`: external open source forks/checkouts and upstream contribution work.
- `references`: cloned repos used for reading, examples, or research.
- `Personal`: standalone personal projects.
- `personal_monorepo`: personal monorepo work.
- `vault-public`: public/exportable vault content.
- `env-tooling`: shared env CLI/wrapper tooling.

Defaults:

- Search for repos under `~/Code` first.
- Clone open source repos to `~/Code/open_source/<repo-name>`.
- Clone reference/research repos to `~/Code/references/<repo-name>`.
- Create personal standalone repos in `~/Code/Personal`.
- Reuse existing project folders when task clearly belongs there.
