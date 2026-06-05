---
type: agent-reference
status: enabled
---
# Bootstrap Export

Export the public bootstrap vault from the current vault:

```bash
vault bootstrap-export --dry-run
vault bootstrap-export --force
```

The export writes a root `README.md` from `_master/system/bootstrap/README-bootstrap.md`. Internal bootstrap/export mechanics live in `_master/system/bootstrap/bootstrapdocs.md`. With `--force`, the exporter mirrors export-owned files into the configured export root while preserving repo metadata such as `.git`, `.github`, `.gitignore`, `.gitattributes`, license files, and contribution docs.

Default export root and context folder output mapping live in:

```text
_master/system/bootstrap/bootstrap-export.json
```

Implementation script: `_master/system/scripts/bootstrap_export.py`.
