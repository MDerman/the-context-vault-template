---
status: active
context_type: business
content_enabled: true
default_capture: false
---
# business

## Add This Shared Folder To Another Vault

If this folder was shared into another bootstrap vault through Relay, run from that vault root:

```bash
cd "$(vault root)"
vault folder register business
```

Impression business workspace for product, clients, leads, content, records, team, resources, partners, and strategic ideas.

## Start Here

- [[DECLARATION|DECLARATION.md]] is the compact operating truth.
- Use this `HOME.md` as the folder routing map before creating new Impression notes.
- Use `_obsidian/tasks`, `_obsidian/projects`, and `_obsidian/epics` for operating work rather than burying tasks in ordinary notes.

## Folder Map

| Folder                                                               | Use                                                                                                                                          |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| [[_obsidian/content]]                                                | Structured Impression content pipeline and publication records.                                                                              |
| [[_obsidian/content-schedules]]                                      | Generated 4-week content schedule planning pages when [[DECLARATION/content-cadence.json|content-cadence.json]] is enabled.                 |
| [[Clients]]                                                          | Client-specific assets and records.                                                                                                          |
| [[Leads]]                                                            | CRM, lead lists, feedback, outreach material, and lead research.                                                                             |
| [[Content]]                                                          | Marketing assets, blog/SEO assets, email templates, sales copy, pitch decks, and content resources.                                          |
| [[Financial & Records]]                                              | Legal, banking, invoices, account statements, financial models, registrations, and official records.                                         |
| [[Team]]                                                             | Hiring, collaborators, internal team docs, and people operations.                                                                            |
| [[Resources]]                                                        | Product/repo samples, technical references, reusable business resources, and implementation references.                                      |
| [[Media and Graphics]]                                               | Brand, media, graphic, and design assets.                                                                                                    |
| [[Archive]]                                                          | Old product docs, superseded specs, inactive material, and historical reference.                                                             |
| [[Lots of ideas here]]                                               | Current ideas, competitors, strategic scratch space, and unstructured business thinking. Future rename candidate: `Ideas/`; do not move yet. |
| [[Impression Partners Co-founers]]                                   | Current partner, cofounder, and strategic relationship material. Future rename candidate: `Partners/`; do not move yet.                      |
| [[_obsidian]]                                                        | Tasks, projects, epics, periodic notes, templates, content pipeline, dashboards, and other Obsidian operating files.                         |

## Routing Rules

- Use ordinary root folders for business source-of-truth docs, assets, and reference material.
- Use `_obsidian/content` only for structured content pipeline items and publication definitions.
- Use `Lots of ideas here` for now when the material is still idea-shaped and does not clearly belong in another folder.
- Use `_obsidian/tasks` only for executable next actions, reminders, and decisions that need follow-up.
