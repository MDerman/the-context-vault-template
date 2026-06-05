---
type: agent-reference
status: enabled
---
# Public Vault Upgrade

Public bootstrap installs keep upstream Git state outside iCloud and use it for setup updates:

```bash
vault upgrade status
vault upgrade --dry-run
vault upgrade --apply
vault upgrade doctor
vault upgrade repair-prompt
```

Install metadata lives in `.vault-bootstrap/install.json`; exported policy and release metadata live in `.vault-bootstrap/policy.json` and `.vault-bootstrap/release.json`. Upgrade reports live under `.vault-upgrade/`.

Implementation script: `_master/system/scripts/upgrade.py`.
