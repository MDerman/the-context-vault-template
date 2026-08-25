# Context Vault template repository instructions

This repository owns the public Obsidian Vault template, bootstrap and upgrade system, `vault` commands, bundled agent skills, and Obsidian configuration.

- Read `README.md`, `docs/README.md`, and `docs/agent-operations.md` before changing workflows, scripts, `_system/`, or Vault structure.
- Use Obsidian `[[links]]` inside Vault notes. Keep note structure minimal and never bulk-move, restructure, delete, or overwrite user content without explicit authorization.
- Working Vault files live only in the full iCloud Vault on approved Macs. Linux and non-iCloud hosts may change this code repository but must not clone, read, or edit a live Vault.
- Keep private or machine-local state below the documented `_system/local/` boundaries and out of public exports.
- Update the relevant skill and documentation whenever an agent-facing workflow changes so future agents can discover the operating contract.
- Repository-level architecture, bootstrap, release, and contributor documentation lives in `docs/`; keep `docs/README.md` current. End-user notes and SOPs intentionally shipped inside a Vault remain in `_system/docs/` and are indexed from the repository docs.
- Preserve the detailed Git, host, routing, and completion rules in `docs/agent-operations.md`.
