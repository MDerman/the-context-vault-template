# Next.js SEO Audit and Fix Configuration

This folder owns Matt's changing site/repository map and dated audit evidence for [[_system/agents/manual-skills/_marketing/marketing-nextjs-seo-audit-and-fix/SKILL|Next.js SEO Audit and Fix skill]]. Generic audit logic, fix patterns, scripts and primary sources stay in skill folder.

## Ownership

- `private/sites.json`: target domains, repository routing, app/tenant paths and last-known findings.
- Search Console observations are evidence snapshots, not live guarantees; recheck before acting.
- Google measurement account/container facts remain in [[_system/config/marketing-google-marketing-measurement/README|Google Marketing Measurement Configuration]].
- Authentication remains in owning Google/env workflows.

Private config is excluded from public vault export. Public skill remains usable with an explicit URL and repository path when this config is absent.

## Schema

Each site may define:

- `id`, `canonicalOrigin`, `repositoryId` or `repositoryPath`
- `appPath`, optional `tenantPath`, and docs to read first
- `sourceObservation` with commit, cleanliness and observed date
- `liveObservation` and `platformObservation` with dated findings
- `relatedSkills` for measurement or campaign-link delegation

Resolve `repositoryId` through topology config. Expand `~` only at runtime. Never assume stored findings still exist.

## Updating

1. Run skill live audit and record deployment/date.
2. Inspect current source and Git commit without merging dirty-tree observations into committed-source claims.
3. Read current Search Console data when available.
4. Replace stale findings rather than accumulating contradictory snapshots.
5. Keep implemented/resolved findings only when useful as regression history.
