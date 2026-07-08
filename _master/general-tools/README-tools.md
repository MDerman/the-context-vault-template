# Tooling SOP

## Add Or Change Tools

- Put general utilities under `_master/general-tools/<tool-name>/`.
- Put reusable agent-facing vault commands under `_master/system/scripts/` only when they belong in `vault`.
- Give each non-trivial tool folder a local `README.md`.
- Put workflow-specific SOPs in `README-<topic>.md` near the workflow.
- Prefer Homebrew for CLI dependencies and add needed formulas to `_master/system/bootstrap/Brewfile`.
- Update `_master/system/bootstrap/install_dependencies.sh` only when install behavior changes.
- Keep real auth, tokens, local credentials, and secrets out of tracked files.

## Run Tools

Before running a tool:

1. Read `_master/general-tools/README.md`.
2. Read this file.
3. Read the tool folder's `README.md`.
4. Run dry-run or help commands first when available.

## Invoices

Invoice generation lives in `_master/general-tools/invoice-generation/`.

Standard flow:

1. Add or confirm client in `invoice.constants.json`.
2. Choose mode from `invoice_modes`.
3. Run `generate_invoice.py` with `--invoice-number`, `--mode`, `--client`, and `--item`.
4. Keep source-note snippets as short CLI commands, not Python wrappers.

Read `_master/general-tools/invoice-generation/README.md` before generating invoices.
