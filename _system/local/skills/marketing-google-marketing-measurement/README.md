# Google Marketing Measurement Configuration

This folder owns Matt’s changing Google measurement instance map and exact organization exports. Generic workflows, references, code examples and inspection logic live in [[_system/agents/manual-skills/_marketing/marketing-google-marketing-measurement/SKILL|Google Marketing Measurement skill]].

## Ownership

- `private/instances.json`: observed account/container identifiers and unresolved mappings.
- `private/gtm/<instance>/`: verbatim GTM exports plus snapshot notes.
- `private/evidence/`: user-provided screenshots and observations that support the instance map.
- Authentication belongs in the shared env/auth workflow, never here.

The private subtree is excluded from public vault export. Container/account IDs are not credentials, but the combined map is personal operational context.

## Current Source Repository

The implementation source is logical repository `business`; machine topology resolves its local checkout. Start at `.docs/analytics-and-seo.md`, then use `.docs/analytics/google/marketing-measurement.json` for exact current instance state. The skill contains a clean provenance snapshot so the measurement design remains reviewable even when the repo changes.

## Updating a GTM Snapshot

1. Export the published version from **GTM → Admin → Export Container**.
2. Keep the original JSON unchanged under `private/gtm/<instance>/`.
3. Run the skill’s `scripts/inspect-gtm-export.mjs` against it.
4. Update that instance’s README and `instances.json` with the version, export time and mapping status.
5. Commit the snapshot and notes before changing the live container.

## Confirmed Impression Mapping

- GA4 account: Friday Studios (`318291231`).
- GA4 property: `446193417`.
- Web stream: `8263816288`, measurement ID `G-8QN2M5Y7FV`.
- GTM account: `6235439030`.
- GTM container: `187628653`, public ID `GTM-5WD7VD5B`.
- Automatic first-visit consent currently grants all seven categories by explicit user decision; a later stored choice must win.

The Impression repository's `.docs/analytics/google/` directory owns the portable project manifest and exact Git snapshots. This private config owns Matt's cross-project instance registry and user-provided evidence.
