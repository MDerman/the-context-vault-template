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

Install metadata lives in `_master/system/bootstrap/state/install.json`; exported policy and release metadata live under `_master/system/bootstrap/state/`. Upgrade reports live under `_master/system/bootstrap/state/upgrade-reports/`.

`vault upgrade --dry-run` also previews external dependency repo sync from `_master/system/config/deps.json`. `vault upgrade --apply` applies public bootstrap updates first, then runs `vault deps sync --apply` so tracked dependency repos are pulled and managed projections are rebuilt.

If the current vault has no public bootstrap install state, `vault upgrade --dry-run` and `vault upgrade --apply` skip the public bootstrap step and run dependency repo sync only. This lets source/private vaults still use `vault upgrade` as the broad "bring external dependencies current" command.

Implementation script: `_master/system/scripts/upgrade.py`.
