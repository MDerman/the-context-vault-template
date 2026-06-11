#!/usr/bin/env python3
"""Dry-run migration planner for old Matt blog/YouTube notes into `_obsidian/content`.

This script is intentionally conservative:
- dry-run is the default;
- `--apply` is required to write destination files;
- `--delete-source` also requires `--apply` and `--yes-delete-source`;
- source drafts are copied into normalized content notes rather than moved unless
  deletion is explicitly requested.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from script_utils import vault_relative_path_string


BLOG_SOURCE = Path("personal-brand/Matt writing etc/Blogs/Blog Database")
YOUTUBE_SOURCE = Path("personal-brand/Matt writing etc/Youtube Factory/Content Database")
DEFAULT_MANIFEST = Path("_master/migration-reports/matt-content-migration-manifest.json")
ID_TAIL = re.compile(
    r"[\s_-]+(?:[0-9a-f]{32}|[0-9a-f]{24}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.I,
)


@dataclass
class MigrationItem:
    source: Path
    destination: Path
    entity: str
    content_kind: str
    platform: str
    publication: str
    status: str
    title: str
    body: str
    metadata: dict[str, str]


def slugify(value: str) -> str:
    value = strip_id_tail(value)
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "untitled"


def strip_id_tail(value: str) -> str:
    previous = None
    current = value.strip()
    while previous != current:
        previous = current
        current = ID_TAIL.sub("", current).strip()
    return current


def relative_slug(relative: Path) -> str:
    parts = [strip_id_tail(part) for part in relative.with_suffix("").parts]
    return slugify(" ".join(parts))


def parse_loose_note(path: Path) -> tuple[str, dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    title = path.stem
    metadata: dict[str, str] = {}
    body_start = 0

    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip() or title
        body_start = 1

    index = body_start
    while index < len(lines) and not lines[index].strip():
        index += 1

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped == "---":
            index += 1
            break
        if not stripped:
            index += 1
            continue
        if ":" not in line or line.startswith(" ") or line.startswith("- "):
            break
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
        index += 1

    body = "\n".join(lines[index:]).strip()
    if not body:
        body = text.strip()
    return title, metadata, body


def normalize_status(raw: str) -> str:
    value = raw.strip().lower()
    if not value:
        return "idea"
    if "draft" in value:
        return "draft"
    if "publish" in value or "done" in value:
        return "published"
    if "review" in value:
        return "review"
    if "progress" in value:
        return "in-progress"
    return slugify(value)


def scalar(value: str | None) -> str:
    if value is None or value == "":
        return ""
    return json.dumps(value, ensure_ascii=False)


def content_frontmatter(item: MigrationItem, root: Path) -> str:
    source = vault_relative_path_string(item.source, root)
    lines = [
        "---",
        "type: content",
        f"entity: {item.entity}",
        f"content_kind: {item.content_kind}",
        f"platform: {item.platform}",
        f"publication: {item.publication}",
        f"status: {item.status}",
        "publish_date:",
        f"source: {scalar(source)}",
        "repurposed_from:",
        "cta:",
        "conversion_goal:",
        "tags:",
        "  - content",
        "---",
    ]
    return "\n".join(lines)


def destination_for_blog(root: Path, source_root: Path, path: Path, title: str, metadata: dict[str, str]) -> tuple[str, Path, str]:
    website = metadata.get("Websites", metadata.get("Website", ""))
    entity = "impression" if "impression" in website.lower() else "personal-brand"
    publication = "impression" if entity == "impression" else "personal-brand"
    relative = path.relative_to(source_root)
    if len(relative.parts) > 1:
        parent_slug = slugify(relative.parts[0])
        filename = relative_slug(Path(*relative.parts[1:])) + ".md"
        destination = root / entity / "_obsidian/content/items/blog-posts" / parent_slug / filename
    else:
        destination = root / entity / "_obsidian/content/items/blog-posts" / f"{slugify(title)}.md"
    return entity, destination, publication


def destination_for_youtube(root: Path, source_root: Path, path: Path, title: str, metadata: dict[str, str]) -> tuple[Path, str, str]:
    form = metadata.get("Form", "").strip().lower()
    if form == "post" or form == "reel":
        folder = "social-posts"
        kind = "social-post"
        platform = "social"
    else:
        folder = "youtube-videos"
        kind = "youtube-video" if form == "youtube" else "youtube-support"
        platform = "youtube"

    relative = path.relative_to(source_root)
    if len(relative.parts) > 1:
        parent_slug = slugify(relative.parts[0])
        filename = relative_slug(Path(*relative.parts[1:])) + ".md"
        destination = root / "personal-brand" / "_obsidian/content/items" / folder / parent_slug / filename
    else:
        destination = root / "personal-brand" / "_obsidian/content/items" / folder / f"{slugify(title)}.md"
    return destination, kind, platform


def blog_items(root: Path, source_root: Path) -> list[MigrationItem]:
    items: list[MigrationItem] = []
    for path in sorted(source_root.rglob("*.md")):
        title, metadata, body = parse_loose_note(path)
        entity, destination, publication = destination_for_blog(root, source_root, path, title, metadata)
        items.append(
            MigrationItem(
                source=path,
                destination=destination,
                entity=entity,
                content_kind="blog-post",
                platform="blog",
                publication=publication,
                status=normalize_status(metadata.get("status", metadata.get("Status", ""))),
                title=title,
                body=body,
                metadata=metadata,
            )
        )
    return items


def youtube_items(root: Path, source_root: Path) -> list[MigrationItem]:
    items: list[MigrationItem] = []
    for path in sorted(source_root.rglob("*.md")):
        title, metadata, body = parse_loose_note(path)
        destination, kind, platform = destination_for_youtube(root, source_root, path, title, metadata)
        items.append(
            MigrationItem(
                source=path,
                destination=destination,
                entity="personal-brand",
                content_kind=kind,
                platform=platform,
                publication="personal-brand-youtube" if platform == "youtube" else metadata.get("Platform", ""),
                status=normalize_status(metadata.get("Progress", metadata.get("status", metadata.get("Status", "")))),
                title=title,
                body=body,
                metadata=metadata,
            )
        )
    return items


def render_item(item: MigrationItem, root: Path) -> str:
    metadata_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(item.metadata.items()))
    metadata_block = f"\n## Original Metadata\n\n{metadata_lines}\n" if metadata_lines else ""
    return f"{content_frontmatter(item, root)}\n# {item.title}\n\n{item.body}\n{metadata_block}"


def apply_item(item: MigrationItem, root: Path, overwrite: bool) -> None:
    if item.destination.exists() and not overwrite:
        raise FileExistsError(f"Destination exists: {item.destination}")
    item.destination.parent.mkdir(parents=True, exist_ok=True)
    item.destination.write_text(render_item(item, root), encoding="utf-8")


def detect_duplicate_destinations(items: list[MigrationItem], root: Path) -> dict[str, list[str]]:
    destinations: dict[str, list[str]] = {}
    for item in items:
        destination = str(item.destination.relative_to(root))
        destinations.setdefault(destination, []).append(str(item.source.relative_to(root)))
    return {destination: sources for destination, sources in destinations.items() if len(sources) > 1}


def detect_existing_destinations(items: list[MigrationItem], root: Path) -> list[str]:
    return [
        str(item.destination.relative_to(root))
        for item in items
        if item.destination.exists()
    ]


def detect_id_tail_destinations(items: list[MigrationItem], root: Path) -> list[str]:
    hits: list[str] = []
    for item in items:
        relative = str(item.destination.relative_to(root))
        if ID_TAIL.search(item.destination.stem):
            hits.append(relative)
    return hits


def write_manifest(path: Path, root: Path, items: list[MigrationItem], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": mode,
        "count": len(items),
        "items": [
            {
                "source": str(item.source.relative_to(root)),
                "destination": str(item.destination.relative_to(root)),
                "entity": item.entity,
                "content_kind": item.content_kind,
                "platform": item.platform,
                "publication": item.publication,
                "status": item.status,
                "title": item.title,
            }
            for item in items
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Plan or apply old Matt content migration into _content.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--blog-source", default=str(BLOG_SOURCE))
    parser.add_argument("--youtube-source", default=str(YOUTUBE_SOURCE))
    parser.add_argument("--apply", action="store_true", help="Write destination files. Omitted means dry-run.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting destination files when applying.")
    parser.add_argument("--delete-source", action="store_true", help="Delete source files after successful apply.")
    parser.add_argument("--yes-delete-source", action="store_true", help="Required confirmation for --delete-source.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to write the source-to-destination manifest.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of planned items for inspection.")
    args = parser.parse_args(argv)

    if args.delete_source and (not args.apply or not args.yes_delete_source):
        raise SystemExit("--delete-source requires --apply and --yes-delete-source")

    from script_utils import resolve_vault_root

    root = resolve_vault_root(args.root, __file__)
    blog_source = root / args.blog_source
    youtube_source = root / args.youtube_source

    items: list[MigrationItem] = []
    if blog_source.exists():
        items.extend(blog_items(root, blog_source))
    if youtube_source.exists():
        items.extend(youtube_items(root, youtube_source))

    if args.limit:
        items = items[: args.limit]

    mode = "APPLY" if args.apply else "DRY-RUN"
    duplicate_destinations = detect_duplicate_destinations(items, root)
    if duplicate_destinations:
        print("Duplicate destination paths detected; aborting before write.")
        for destination, sources in duplicate_destinations.items():
            print(destination)
            for source in sources:
                print(f"  - {source}")
        raise SystemExit(1)

    id_tail_destinations = detect_id_tail_destinations(items, root)
    if id_tail_destinations:
        print("ID-like destination filename tails detected; aborting before write.")
        for destination in id_tail_destinations:
            print(destination)
        raise SystemExit(1)

    if args.apply and not args.overwrite:
        existing_destinations = detect_existing_destinations(items, root)
        if existing_destinations:
            print("Destination files already exist; aborting before write. Use --overwrite only after verification.")
            for destination in existing_destinations[:100]:
                print(destination)
            if len(existing_destinations) > 100:
                print(f"...and {len(existing_destinations) - 100} more")
            raise SystemExit(1)

    manifest_path = root / args.manifest
    write_manifest(manifest_path, root, items, mode.lower())
    print(f"{mode}: {len(items)} item(s)")
    print(f"Manifest: {manifest_path.relative_to(root)}")
    for item in items:
        print(f"{item.source.relative_to(root)} -> {item.destination.relative_to(root)}")
        if args.apply:
            apply_item(item, root, args.overwrite)
            if args.delete_source:
                item.source.unlink()

    if args.apply and args.delete_source:
        for source_root in [blog_source, youtube_source]:
            for directory in sorted((path for path in source_root.rglob("*") if path.is_dir()), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
        for source_root in [blog_source, youtube_source]:
            try:
                source_root.rmdir()
            except OSError:
                pass

    if args.apply:
        print("Migration write complete.")
    else:
        print("No files written. Re-run with --apply to create destination notes.")


if __name__ == "__main__":
    main()
