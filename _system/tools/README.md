# General Tools

Reusable tools outside the `vault` dispatcher.

## Add Or Change Tools

- Put general utilities under `_system/tools/<tool-name>/`.
- Put reusable commands under `_system/commands/` only when they belong behind `vault`.
- Give each non-trivial tool folder a local `README.md`.
- Add public Vault runtime packages to `_system/deps/packages.yaml`.
- Update `_system/deps/install.py` only when structured install behavior changes; bootstrap only invokes it.

## Run Tools

Read this doorway, then tool folder's `README.md`. Use dry-run or help commands first when available.

Invoice flow lives in [[_system/tools/invoice-generation/README|Invoice Generation]].

macOS login actions and the `vault mac-startup` workflow live in [[_system/tools/mac-automation/README|macOS Automation]].
