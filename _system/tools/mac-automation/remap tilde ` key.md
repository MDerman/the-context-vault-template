---
contexts:
  - "personal-brand"
type: "learning-note"
---

# remap tilde ` key

The current managed workflow is documented in [[_system/tools/mac-automation/README|macOS Automation]] and configured by [[_system/config/mac-startup/README|macOS Startup Configuration]]. Use:

```bash
vault mac-startup status
vault mac-startup install
```

The enabled `mattbook` action maps HID usage `0x35` to `0x64`:

```bash
hidutil property --set '{"UserKeyMapping":[{"HIDKeyboardModifierMappingSrc":0x700000035,"HIDKeyboardModifierMappingDst":0x700000064}]}'
```

`hidutil` mappings are lost on restart, so the vault-managed per-user LaunchAgent reapplies this mapping after login. The copied runtime remains available even if the iCloud vault is not ready yet.

The former `com.user.loginscript` mapping used the inverse direction. `vault mac-startup install` replaces configured legacy jobs recoverably by unloading their jobs and moving their plist files into:

```text
~/Library/Application Support/obsidian-context-vault/mac-startup/legacy-launchagents/
```

Reference: [Apple Technical Note TN2450](https://developer.apple.com/library/archive/technotes/tn2450/_index.html).
