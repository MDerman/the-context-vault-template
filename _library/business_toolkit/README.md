---
status: active
---

# Business Toolkit

The canonical business scaffold lives under `_system/bootstrap/templates/business-context/`; operating instructions live in [[Business Toolkit]]. This library folder is only its navigation entry point; reusable business research belongs in the most specific topical library category.

## Knowledge routes

- [[business_strategy]]
- [[business_models]]
- [[pricing_and_offers]]
- [[brand]]
- [[agencies]]
- [[operations_and_systems]]
- [[business_analytics]]
- [[business_finance]]
- [[team]]
- [[sales]]
- [[affiliates]]
- [[communities]]
- [[saas]]
- [[agents]]
- [[ai]]

## Commands

Create a new business context with the complete ordinary folder scaffold:

```bash
vault folder -n studio -s active --context-type business
```

Registering an existing folder is conservative: it installs only selected managed templates, Templater rules, toolkit state, and 📋 icons for operating folders that already exist.

```bash
vault folder register studio --context-type business
vault business-toolkit
vault business-toolkit sync --context-folders studio
vault business-toolkit sync --context-folders studio --apply
vault business-toolkit status --all-business
```

Normal synchronization never creates, deletes, or restructures ordinary business folders. It protects locally edited managed templates and changed managed icons. Interactive apply asks once before replacing all detected drift; non-interactive apply aborts atomically unless `--force` is supplied.

Periodic and TaskNotes templates remain part of core vault bootstrap infrastructure.
