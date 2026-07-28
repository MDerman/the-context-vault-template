# General Tools

Reusable tools outside the `vault` dispatcher.

## Add Or Change Tools

- Put general utilities under `_system/tools/<tool-name>/`.
- Put reusable commands under `_system/commands/` only when they belong behind `vault`.
- Give each non-trivial tool folder a local `README.md`.
- Add needed Homebrew formulas to `_system/bootstrap/Brewfile`.
- Update `_system/bootstrap/install_dependencies.sh` only when install behavior changes.

## Run Tools

Read this doorway, then tool folder's `README.md`. Use dry-run or help commands first when available.

Invoice flow lives in [[_system/tools/invoice-generation/README|Invoice Generation]].
