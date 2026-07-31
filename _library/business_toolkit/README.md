---
status: active
---

# Business Toolkit

The canonical, directly browsable business scaffold is [[_system/bootstrap/templates/business-context/README|Business Context Scaffold]]. This library folder is only its navigation entry point; reusable business research belongs in the most specific topical library category.

## Knowledge routes

- [[_library/business_strategy|Business Strategy]]
- [[_library/business_models|Business Models]]
- [[_library/pricing_and_offers|Pricing and Offers]]
- [[_library/brand|Brand and Positioning]]
- [[_library/agencies|Agencies and Service Delivery]]
- [[_library/operations_and_systems|Operations and Systems]]
- [[_library/business_analytics|Business Analytics]]
- [[_library/business_finance|Business Finance]]
- [[_library/team|Team, Hiring, and Talent]]
- [[_library/sales|Sales and Commercial Relationships]]
- [[_library/affiliates|Affiliates and Partnerships]]
- [[_library/communities|Communities]]
- [[_library/saas|SaaS]]
- [[_library/agents|AI Agents]]
- [[_library/_dev/ai|AI Development]]

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
