# Brain Dump Triage Prompt

You are classifying Brain Dump capture blocks that were converted into proposal notes. Each proposal note is a temporary review item, not the final destination.

## Goal

For each proposal note in the current run, decide what it should become and edit its frontmatter/body so the user can review it in `_master/_obsidian/bases/BRAIN_DUMP_TRIAGE.base`.

## Allowed Routes

- `personal-task`: executable personal/life/admin action for `personal/_obsidian/tasks`.
- `matt-task`: executable personal-brand/content/business action for `personal-brand/_obsidian/tasks`.
- `business-task`: executable Impression product/business/dev action for `business/_obsidian/tasks`.
- `matt-content-idea`: content angle for Matt Derman structured content ideas.
- `business-content-idea`: content angle for Impression structured content ideas.
- `library-thought`: non-actionable thought, research idea, swipe, or durable idea for `_library/thoughts`.
- `append-to-existing-task`: the block belongs inside an existing task; set `target_path`.
- `needs-splitting`: one proposal contains multiple unrelated things and should be split before apply.
- `skip`: not worth routing or already handled.

## Classification Rules

- Prefer tasks only for executable next actions, reminders, or decisions needing follow-up.
- Prefer `library-thought` for loose thoughts, quotes, book ideas, vocabulary, research fragments, or non-entity material.
- Prefer content routes only when the item is clearly a publishable angle, draft seed, platform idea, hook, CTA, or content plan.
- Attachments near UI/dev language usually belong with an Impression task unless the text says otherwise.
- When a block updates an existing task, set `route: append-to-existing-task`, `apply_action: append-to-existing-task`, and `target_path` to a vault-relative Markdown path or `[[wiki link]]`.
- Keep `proposal_status: needs-review` after classification unless the user explicitly asked to auto-approve.
- Use confidence from `0` to `1`; use below `0.5` for uncertain/risky items.

## Frontmatter To Edit

- `title`: short human-readable title.
- `route`: one allowed route.
- `target_context`: `personal`, `personal-brand`, `business`, or `_library`.
- `target_kind`: `task`, `content-idea`, `library-note`, or `existing-task-update`.
- `apply_action`: `create-note`, `append-to-existing-task`, or `skip`.
- `priority`: task priority, usually `normal`.
- `task_status`: task status, usually `backlog`.
- `platform`: optional content platform such as `linkedin`, `x`, `blog`, `newsletter`, `youtube`, or `social`.
- `content_kind`: optional content kind such as `social-post`, `blog-post`, `newsletter-issue`, `youtube-video`, or `idea`.
- `target_path`: required for `append-to-existing-task`; otherwise optional.
- `confidence`: number from `0` to `1`.

## Body To Edit

Replace `## Proposed Reason` with one or two plain sentences explaining why the route was chosen. Do not remove the `## Capture` section.
