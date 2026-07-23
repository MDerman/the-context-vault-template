---
name: live-view-plan
description: Publish, create, update, or inspect temporary public live views rendered by configured publishing service for Markdown or HTML artifacts, including existing documents, code-change overviews, PR descriptions, and plans. Use when user says "live view plan", "live-view plan", or "HTML plan"; asks to publish or share a document as web page; or supplies configured service URL. Preserve supplied source exactly by default. Author or convert content into plan only when explicitly requested.
---

# Live View Publishing

Read `_system/config/live-view-plan/README.md` and private config first. Publish Markdown and safe static HTML through configured service. Treat service/host names as publishing mechanism names, not automatic instructions to turn content into plan. Default visual language is dark neutral monochrome: `#181818` page, dark-gray surfaces, near-white text, gray links and borders. Reserve color for diagrams, data visualization, syntax highlighting, and semantic status/callout states.

## Preserve artifact intent

Classify request before writing:

- Existing file or supplied document + publish, display, share, view online, or “make this a live-view plan”: publish existing content unchanged.
- Explicit “create a plan,” “turn this into a plan,” or “rewrite this as a plan”: author plan structure.
- Explicit code-change overview, implementation overview, PR description, release notes, review, or other artifact: keep requested artifact type. Do not add plan sections unless requested.
- Explicit edit or rewrite before publishing: make only requested content changes, then publish.

Do not silently restructure, summarize, retitle, remove frontmatter, add task lists, or invent goal/scope/rollout sections for supplied content. When intent remains materially ambiguous, preserve source instead of transforming it.

Before public upload, inspect intended source for accidental credentials, secrets, private-only notes, or hidden context. If found, stop and ask; do not silently redact or publish.

## Publish existing Markdown unchanged

Use source file directly. Do not copy it into `.agents/plans/`, edit it, or pass `--delete-after-upload`.

Infer display title from first H1, then filename when H1 is absent:

```bash
html-plans upload path/to/source.md --project "<project>" --name "<document title>"
```

This preserves local source and publishes same Markdown content. Renderer supplies always-dark neutral responsive styling; raw HTML inside Markdown is escaped. Mermaid and code syntax may use color for readability.

For an existing draft, preserve same public URL:

```bash
html-plans upload path/to/source.md --draft "<id>" --project "<project>" --name "<document title>"
```

Use `--new` only when user requests separate URL.

## Create requested artifact

Create source only when user asks to author new content. Match requested artifact type.

- Plans: `.agents/plans/<lower-kebab-name>.md`.
- Other temporary live-view artifacts: `.agents/live-view/<lower-kebab-name>.md`.

For an explicitly requested plan, make it understandable without surrounding chat. Include goal, scope, non-goals, ordered work, risks, validation, rollout, and unresolved decisions when relevant.

For code-change overviews, PR descriptions, release notes, and other artifacts, use structure appropriate to that artifact. Do not force plan structure.

Prefer Markdown headings, lists, tables, blockquotes, and fenced code. Do not add secrets, private context, or unnecessary absolute paths.

Publish generated temporary source and remove it only after successful upload:

```bash
html-plans upload .agents/<plans-or-live-view>/<name>.md --project "<project>" --name "<document title>" --delete-after-upload
```

CLI retains local path-to-draft mapping, so recreating same temporary path updates same public URL.

## Publish explicit HTML

Use HTML only when user explicitly requests an HTML artifact or exact HTML rendering.

For generated HTML:

1. Start from `assets/dark-monochrome.html`. Preserve its neutral page/surface/text tokens and adapt layout to artifact. Keep ordinary chrome monochrome; use color only for diagrams, data, syntax, and semantic status/callout states.
2. Create `.agents/live-view/<name>.html` with doctype, non-empty title, semantic HTML, responsive inline CSS, and optional static SVG.
3. Never include scripts, event handlers, forms, frames, embeds, objects, meta refresh, or `javascript:` URLs.
4. Upload and remove temporary file after success:

```bash
html-plans upload .agents/live-view/<name>.html --project "<project>" --name "<document title>" --delete-after-upload
```

Direct HTML is stored and served byte-exact; server does not inject theme CSS. For supplied HTML, preserve content only when it satisfies same safety restrictions. Restyle supplied HTML only when user explicitly asks. Otherwise stop and explain safety conflict instead of rewriting silently.

## Revise or replace existing live view

When user wants edits to stored canonical source, fetch source, edit only requested parts, republish same draft, then remove fetched temporary copy:

```bash
html-plans fetch "<plan-url>" --source --output .agents/live-view/<name>.md
html-plans upload .agents/live-view/<name>.md --draft "<id>" --project "<project>" --name "<document title>" --delete-after-upload
```

Use `.html` for HTML-format artifacts. Without `--source`, fetch returns rendered public HTML.

Markdown renderer upgrades affect only new versions. To apply a renderer theme change to an existing Markdown URL, fetch source and upload to same draft ID. Latest URL then changes; prior immutable `/v/<version>` URLs do not.

When replacing live content from an existing local source file, upload that source directly with `--draft`; keep local source unchanged.

## Return result

Return:

- Latest URL.
- Immutable version URL.
- One-line description of what was published.
- Source disposition: existing source preserved, or generated temporary source removed.

If upload fails, retain temporary source for diagnosis and run `html-plans doctor`.
