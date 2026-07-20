---
name: live-view-plan
description: Create, publish, update, or inspect temporary public plans rendered as live web pages. Use whenever user says "live view plan", "live-view plan", or "HTML plan"; asks to publish or share a plan as a web page; or supplies a plans.ctx9.com plan URL. Default to temporary Markdown source rendered by html-plans, while preserving exact static HTML publishing when user explicitly requests an HTML plan.
---

# Live View Plan

Publish useful standalone plans through `html-plans`. Default to Markdown source. Create source temporarily, upload it, then remove it locally only after successful upload.

## Markdown workflow

1. Find repo root and create `.agents/plans/` when missing.
2. Write `.agents/plans/<lower-kebab-name>.md` with concise Markdown. Do not add frontmatter, secrets, hidden context, or unnecessary absolute paths.
3. Make plan understandable without surrounding chat. Include goal, scope, non-goals, ordered work, risks, validation, rollout, and unresolved decisions when relevant.
4. Prefer headings, lists, task lists, tables, blockquotes, and fenced code. Renderer supplies responsive styling. Raw HTML is escaped.
5. Publish and remove temporary source:

```bash
html-plans upload .agents/plans/<name>.md --project "<project>" --name "<plan title>" --delete-after-upload
```

CLI removes file only after successful upload. It retains local path-to-draft mapping, so recreating same path updates same public URL. Use `--new` only when user requests separate URL.

6. Return latest URL, immutable version URL, and short summary. Do not claim local source remains.

## Explicit HTML plan workflow

When user explicitly requests HTML plan, preserve existing exact-HTML behavior:

1. Create `.agents/plans/<name>.html` with doctype, non-empty title, semantic HTML, responsive inline CSS, and optional static SVG.
2. Never include scripts, event handlers, forms, frames, embeds, objects, meta refresh, or `javascript:` URLs.
3. Upload exact HTML and remove temporary file:

```bash
html-plans upload .agents/plans/<name>.html --project "<project>" --name "<plan title>" --delete-after-upload
```

Service serves uploaded HTML unchanged with security headers. Markdown rendering does not alter this path.

## Revise existing plan

Fetch stored canonical source, edit, republish same draft, then remove local copy:

```bash
html-plans fetch "<plan-url>" --source --output .agents/plans/<name>.md
html-plans upload .agents/plans/<name>.md --draft "<id>" --project "<project>" --name "<title>" --delete-after-upload
```

Use `.html` output for HTML-format plans. Without `--source`, fetch returns rendered public HTML.

If publish fails, keep source for diagnosis and run `html-plans doctor`.
