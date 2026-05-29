# Vault Upgrade Migrations

Versioned migration scripts live here. `vault upgrade` runs only migrations listed in `.vault-bootstrap/policy.json`.

Each migration must support:

```bash
python3 master/system/migrations/<script>.py --root /path/to/vault --report /path/to/report.json --dry-run
python3 master/system/migrations/<script>.py --root /path/to/vault --report /path/to/report.json --apply
```

Migrations must be idempotent and must write JSON reports.
