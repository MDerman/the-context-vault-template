# Brain Dump Routing

Use this SOP to recommend and apply destinations for one section of `_system/inbox/BRAIN_DUMP.md`. A section is text between full-line `***` or `---` separators; file start or end can serve as outer boundary.

## Core Distinction

Context folders hold information specific to that entity. `_library` holds reusable knowledge, learning, examples, prompts, and reference material.

- `personal`: Matt's actual life state and records—blood results, medical history, finances, goals, decisions, routines, relationships, home, and personal work.
- `business`: Impression-specific product, company, customer, marketing, operations, plans, and work.
- `personal-brand`: Matt Derman brand-specific positioning, content, audience, offers, and publishing work.
- `_library`: reusable or external knowledge not bound to one entity. Most Brain Dump reference material belongs here.
- `_wiki`: synthesized, durable, cross-context knowledge. Use after source material has been distilled, not for raw capture by default.
- `_system`: vault operating rules, agent SOPs, scripts, templates, and system material only. Do not route ordinary personal or reference captures here.

Test: if material stays useful without Matt's actual data or one entity's current state, prefer `_library`. If it records what happened to Matt, Impression, or Matt's brand, prefer matching context folder.

## Library Routing

Read [[_library/LIBRARY|Library Routing Rules]] before recommending library paths.

- Prefer existing topic folder when topic has established home.
- Create `_library/<topic>/` when reusable subject does not fit existing structure.
- Put pure prompts, templates, examples, swipe files, and sample structures in `_library/<topic>/_templates/`.
- Use `_library/_personal_development/` for character, habits, attention, execution, learning, reviews, and self-development frameworks—not personal records.
- Route reusable business material to its specific lowercase snake_case topic folder, such as `_library/business_strategy/`, `_library/business_models/`, `_library/operations_and_systems/`, `_library/economics_and_investing/`, `_library/pricing_and_offers/`, `_library/sales/`, or `_library/marketing/`.
- Use `_library/_dev/` for reusable software, AI/dev tooling, networks, and computer-science learning.
- Use `_library/thoughts/` for loose non-actionable ideas that do not yet warrant stronger topical home.
- Put synthesized notes in topic root, pure templates/examples in `_templates`, and largely unmodified external documents in `_resources`.
- Route LinkedIn/X growth material under `_library/platform_growth/<platform>/` and platform copy templates under `_library/copywriting/_templates/<platform>/`.
- Route community, affiliate, and PR material to `_library/communities/`, `_library/affiliates/`, and `_library/public_relations/` rather than combined `etc` folders.
- When appending to a lossless split hub, follow its child links and append to matching child topic note; do not rebuild a new composite dump in hub.

Examples:

- Generic blood-panel analysis prompt → `_library/health/_templates/`.
- General notes about biomarkers or nutrition → `_library/health/`.
- Matt's blood results → `personal/Health/Blood Tests/`.
- Matt's clinician-approved protocol → `personal/Health/Protocols/`.
- Reusable outreach framework → relevant `_library` business or sales topic.
- Impression competitor feature list → append to relevant Impression task/project note or create Impression task.

## Task, Project, Content, Or Note

- Route executable personal work to `personal/_obsidian/tasks/`, Matt Derman brand work to `personal-brand/_obsidian/tasks/`, and Impression work to `business/_obsidian/tasks/`.
- Create TaskNotes task only for executable next action, reminder, or decision needing follow-up.
- Append to existing task when capture advances same outcome. Preserve task's project and epic routing.
- Create new task when action has distinct outcome. Use existing context, project, epic, status, and priority names from `vault inventory`.
- Append to project note when material changes project scope, requirements, or durable project context but is not itself next action.
- Create context note when information is entity-specific but non-actionable.
- Create structured content item only for owned publishable angle, draft seed, platform plan, or content definition.
- Treat attachments next to UI, product, or development language as likely Impression material unless capture says otherwise.
- Split mixed section when parts clearly belong to different destinations. State split explicitly as one recommendation.
- Skip duplicate, obsolete, or low-value capture only as visible recommendation; never silently discard it.

## Recommendation Standard

Inspect current vault before recommending. Use filename-first search, then inspect likely note openings and relevant READMEs. Return 3–5 ranked options. Each option must include:

1. Exact vault-relative target path or proposed new path.
2. Operation: append to existing note/task, create note, create task/content item, split, or skip.
3. Proposed title or destination heading.
4. Transformation: how raw text will be cleaned, summarized, structured, or divided while preserving useful information.
5. Why destination fits and main tradeoff.
6. Confidence from `0` to `1`; use below `0.5` for uncertain or risky routes.

Name one recommended option. Do not write or delete until user chooses, unless user's invocation already states exact approved destination and action.

## Apply Protocol

1. Re-read source section and chosen target immediately before editing; Brain Dump sync may change file concurrently.
2. Preserve meaning and useful details. Fix formatting, obvious typos, and structure. Do not invent claims.
3. Use `[[Obsidian links]]` for internal links.
4. Require exact existing target path before append. Confirm it exists; never guess similar filename.
5. Apply target write first. Use collision-safe filename when creating new note; never overwrite unrelated note.
6. Carry embeds associated with section into target. Copy attachment to owning top-level folder's `_obsidian/attachments/brain-dump/` path, use collision-safe filename, and rewrite embed before source removal.
7. Re-read target and verify transferred text and attachments.
8. Remove only transferred source section after verification.
9. For interior section removal, leave exactly one separator between neighboring sections: retain leading separator and remove trailing separator with chosen block. At file start, remove block plus trailing separator. At file end, remove leading separator plus block.
10. Never delete Brain Dump backup folders. Do not remove original attachment files unless user approved attachment deletion.
11. Do not call external LLM APIs for classification; current agent performs routing.
12. Report target, transformation, and exact source section removed.

If target write fails, leave source unchanged and report blocker. If source changed and exact section cannot be rematched safely, stop before deletion and ask user to identify it again.
