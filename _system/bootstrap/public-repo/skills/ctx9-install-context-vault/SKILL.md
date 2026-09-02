---
name: ctx9-install-context-vault
description: Install Context Vault into a user-chosen folder, guide its interactive setup, and verify the finished local Vault. Use when someone asks to install, bootstrap, or set up Context Vault.
license: MIT
---

# CTX9 · Install Context Vault

Install the public Context Vault with the user in control of its location and setup choices.

## Workflow

1. Ask the user where the Vault should live. Expand `~`, resolve the absolute path, and confirm the destination is absent or empty.
2. Check that `git`, `python3`, and an interactive TTY are available. Do not read credential files.
3. Download `install.sh` from `https://github.com/MDerman/the-context-vault-template` into a temporary directory.
4. Run the installer from a real TTY and pass the chosen target path:

```bash
/bin/bash /path/to/install.sh '/absolute/path/to/Vault'
```

5. Stay with the user while the context-folder wizard asks its questions. If the optional CTX9 skill system is selected, let its setup wizard finish too.
6. Verify the target contains `_system/bootstrap/release.json`, the selected context folders, `.obsidian/plugins/context-nine/main.js`, an active `context-nine` entry in `.obsidian/community-plugins.json`, and a working `vault inventory` command.
7. Report the final absolute Vault path and any optional component the user declined.

Never overwrite a non-empty target or replace an existing Vault.
