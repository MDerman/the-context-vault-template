# Vault Upgrade Migrations

# Future Migrations

Fresh `_system` installs start with no historic migrations. Add future versioned migration scripts here and register them in `_system/bootstrap/upgrade-policy.json`.

Migrations must be idempotent, dry-runnable, scoped to managed files, and covered by focused tests.

Each migration must support:

```bash
python3 _system/migrations/<script>.py --root /path/to/vault --report /path/to/report.json --dry-run
python3 _system/migrations/<script>.py --root /path/to/vault --report /path/to/report.json --apply
```

Migrations must be idempotent and must write JSON reports.
