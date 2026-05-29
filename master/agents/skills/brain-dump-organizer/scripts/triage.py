#!/usr/bin/env python3
"""Prepare and apply Brain Dump triage proposals for this Obsidian vault."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INBOX_PATH = Path("master/system/inbox/BRAIN_DUMP.md")
ATTACHMENTS_DIR = Path("master/system/inbox/BRAIN_DUMP_ATTACHMENTS")
BACKUPS_DIR = Path("master/system/inbox/BRAIN_DUMP_BACKUPS")
PROPOSALS_DIR = Path("master/system/inbox/BRAIN_DUMP_PROPOSALS")
BASE_PATH = Path("master/_obsidian/bases/BRAIN_DUMP_TRIAGE.base")
CONFIG_PATH = Path("master/system/config.json")

ROUTE_TARGETS = {
    "personal-task": {
        "context": "01-personal",
        "kind": "task",
        "directory": Path("01-personal/_obsidian/tasks"),
    },
    "matt-task": {
        "context": "02-personal-brand",
        "kind": "task",
        "directory": Path("02-personal-brand/_obsidian/tasks"),
    },
    "impression-task": {
        "context": "03-business",
        "kind": "task",
        "directory": Path("03-business/_obsidian/tasks"),
    },
    "matt-content-idea": {
        "context": "02-personal-brand",
        "kind": "content-idea",
        "directory": Path("02-personal-brand/_obsidian/content/ideas"),
    },
    "impression-content-idea": {
        "context": "03-business",
        "kind": "content-idea",
        "directory": Path("03-business/_obsidian/content/ideas"),
    },
    "library-thought": {
        "context": "library",
        "kind": "library-note",
        "directory": Path("library/thoughts"),
    },
}

ROUTE_COLUMNS = [
    "unclassified",
    "personal-task",
    "matt-task",
    "impression-task",
    "matt-content-idea",
    "impression-content-idea",
    "library-thought",
    "append-to-existing-task",
    "needs-splitting",
    "skip",
]

PROPOSAL_STATUS_COLUMNS = ["needs-review", "approved", "applied", "skipped", "blocked"]

BASE_CONTENT = """filters:
  and:
    - or:
        - file.hasTag("brain-dump-proposal")
        - type == "brain-dump-proposal"
formulas:
  triageBadge: if(confidence >= 0.8,"High",if(confidence >= 0.5,"Medium","Low"))
properties:
  formula.triageBadge:
    displayName: Confidence
views:
  - type: kanban-view
    name: By Route
    order:
      - formula.triageBadge
      - priority
      - file.name
    groupByProperty: route
    columnOrders:
      note.route:
        - unclassified
        - personal-task
        - matt-task
        - impression-task
        - matt-content-idea
        - impression-content-idea
        - library-thought
        - append-to-existing-task
        - needs-splitting
        - skip
    columnColors:
      note.route:
        unclassified: red
        personal-task: yellow
        matt-task: cyan
        impression-task: blue
        matt-content-idea: green
        impression-content-idea: purple
        library-thought: orange
        append-to-existing-task: blue
        needs-splitting: red
        skip: red
    wrapPropertyValues: false
  - type: kanban-view
    name: By Review Status
    order:
      - route
      - priority
      - file.name
    groupByProperty: proposal_status
    columnOrders:
      note.proposal_status:
        - needs-review
        - approved
        - applied
        - skipped
        - blocked
    columnColors:
      note.proposal_status:
        needs-review: yellow
        approved: cyan
        applied: green
        skipped: red
        blocked: orange
    wrapPropertyValues: false
  - type: table
    name: Edit Fields
    order:
      - file.name
      - proposal_status
      - route
      - target_context
      - apply_action
      - target_path
      - priority
      - task_status
      - platform
      - content_kind
      - confidence
      - applied_to
  - type: table
    name: Needs Attention
    filters:
      or:
        - route == "unclassified"
        - route == "needs-splitting"
        - confidence < 0.5
        - and:
            - route == "append-to-existing-task"
            - target_path == ""
    order:
      - file.name
      - proposal_status
      - route
      - target_path
      - confidence
"""


@dataclass
class ImportSection:
    heading: str
    content: str


@dataclass
class ProposalItem:
    block_id: str
    path: Path
    source_import: str
    body: str


def resolve_root(root_arg: str | None = None) -> Path:
    if root_arg:
        return Path(root_arg).expanduser().resolve()
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "master/system").is_dir():
            return candidate
    script_path = Path(__file__).resolve()
    for candidate in [script_path.parent, *script_path.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "master/system").is_dir():
            return candidate
    raise SystemExit("Could not resolve vault root. Pass --root.")


def load_note_name(root: Path) -> str:
    config_path = root / CONFIG_PATH
    if not config_path.exists():
        return "Brain Dump"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    config = data.get("brain_dump_ingest", {})
    return str(config.get("note_name", "Brain Dump"))


def now_stamp() -> tuple[str, str]:
    now = dt.datetime.now()
    return now.isoformat(timespec="seconds"), now.strftime("%Y%m%dT%H%M%S")


def sanitize_filename(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "-", value).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def slugify(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:80] or fallback


def vault_rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def wiki_link(rel_path: str | Path, alias: str | None = None) -> str:
    rel = str(rel_path)
    return f"[[{rel}|{alias}]]" if alias else f"[[{rel}]]"


def first_heading_or_words(text: str, fallback: str) -> str:
    for line in text.splitlines():
        clean = line.strip().strip("#").strip()
        if clean and not clean.startswith("![["):
            return clean[:90]
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:90] or fallback


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def referenced_wiki_paths(text: str) -> list[str]:
    paths: list[str] = []
    for match in re.finditer(r"!\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?]]", text):
        paths.append(match.group(1).strip())
    return list(dict.fromkeys(paths))


def backup_import(root: Path, note_name: str, timestamp: str, import_text: str) -> tuple[Path, dict[str, str]]:
    backup_dir_name = f"{sanitize_filename(note_name)} {timestamp}"
    backup_dir = root / BACKUPS_DIR / backup_dir_name
    backup_attachments_dir = backup_dir / "_attachments"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / f"{sanitize_filename(note_name)} {timestamp}.md"
    backup_file.write_text(import_text, encoding="utf-8")

    mapping: dict[str, str] = {}
    for rel in referenced_wiki_paths(import_text):
        rel_path = Path(rel)
        if not str(rel_path).startswith(str(ATTACHMENTS_DIR)):
            continue
        source = root / rel_path
        if not source.exists():
            continue
        backup_attachments_dir.mkdir(parents=True, exist_ok=True)
        dest = unique_path(backup_attachments_dir / source.name)
        shutil.copy2(source, dest)
        mapping[rel] = vault_rel(dest, root)
    return backup_file, mapping


def rewrite_wiki_paths(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(old, new)
    return text


def import_body(text: str) -> str:
    return text.strip()


def extract_import_sections(text: str, note_name: str) -> list[ImportSection]:
    body = import_body(text)
    if not body:
        return []
    matches = list(re.finditer(r"^##\s+(.+?)\s+-\s+(.+?)\s*$", body, flags=re.M))
    if not matches:
        return [ImportSection(f"unsectioned - {note_name}", body)]
    sections: list[ImportSection] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        heading = match.group(0).lstrip("# ").strip()
        content = body[start:end].strip()
        if content:
            sections.append(ImportSection(heading, content))
    return sections


def drop_note_title(content: str, note_name: str) -> str:
    lines = content.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].strip().lower() == f"# {note_name}".lower():
        lines.pop(0)
    return "\n".join(lines).strip()


def is_attachment_only(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return bool(lines) and all(re.fullmatch(r"!\[\[[^\]]+]]", line) for line in lines)


def split_blocks(content: str, note_name: str) -> list[str]:
    content = drop_note_title(content, note_name)
    raw_blocks = [block.strip() for block in re.split(r"\n\s*\n+", content) if block.strip()]
    blocks: list[str] = []
    pending_attachment_prefix: list[str] = []
    for block in raw_blocks:
        if is_attachment_only(block):
            if blocks:
                blocks[-1] = f"{blocks[-1]}\n\n{block}"
            else:
                pending_attachment_prefix.append(block)
            continue
        if pending_attachment_prefix:
            block = "\n\n".join([*pending_attachment_prefix, block])
            pending_attachment_prefix = []
        blocks.append(block)
    if pending_attachment_prefix:
        blocks.extend(pending_attachment_prefix)
    return blocks


def yaml_quote(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_quote(item)}")
        else:
            lines.append(f"{key}: {yaml_quote(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(unquote_yaml(line[4:].strip()))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if value == "":
            data[key] = []
        else:
            data[key] = unquote_yaml(value)
    return data, body


def unquote_yaml(value: str) -> Any:
    if value in {"true", "false"}:
        return value == "true"
    if value == '""':
        return ""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def write_proposal(
    root: Path,
    run_id: str,
    index: int,
    source_import: str,
    block: str,
    backup_file: Path,
    created_at: str,
) -> ProposalItem:
    block_id = f"{run_id}-{index:03d}"
    item_dir = root / PROPOSALS_DIR / "runs" / run_id / "items"
    item_dir.mkdir(parents=True, exist_ok=True)
    title = first_heading_or_words(block, f"Brain Dump Block {index:03d}")
    path = item_dir / f"{block_id}-{slugify(title, f'block-{index:03d}')}.md"
    path = unique_path(path)
    rel_path = vault_rel(path, root)
    backup_rel = vault_rel(backup_file, root)
    data = {
        "type": "brain-dump-proposal",
        "title": title,
        "tags": ["brain-dump-proposal"],
        "proposal_status": "needs-review",
        "route": "unclassified",
        "target_context": "",
        "target_kind": "",
        "apply_action": "create-note",
        "target_path": "",
        "priority": "normal",
        "task_status": "backlog",
        "platform": "",
        "content_kind": "",
        "confidence": 0,
        "source_block_id": block_id,
        "source_import": source_import,
        "source_note": wiki_link(INBOX_PATH),
        "backup_note": wiki_link(backup_rel),
        "run_id": run_id,
        "dateCreated": created_at,
        "dateModified": created_at,
    }
    body = (
        f"{frontmatter(data)}\n"
        f"# {title}\n\n"
        f"## Capture\n\n{block.strip()}\n\n"
        "## Proposed Reason\n\n"
        "To be filled by the Brain Dump organizer skill.\n\n"
        "## Apply Notes\n\n"
        f"- Proposal: {wiki_link(rel_path)}\n"
        f"- Backup: {wiki_link(backup_rel)}\n"
    )
    path.write_text(body, encoding="utf-8")
    return ProposalItem(block_id, path, source_import, block)


def ensure_base(root: Path) -> Path:
    path = root / BASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BASE_CONTENT, encoding="utf-8")
    return path


def prepare(root: Path, clear: bool = False) -> dict[str, Any]:
    note_name = load_note_name(root)
    inbox_path = root / INBOX_PATH
    if not inbox_path.exists():
        raise SystemExit(f"Missing Brain Dump import file: {INBOX_PATH}")
    import_text = inbox_path.read_text(encoding="utf-8")
    if not import_body(import_text):
        return {"status": "empty", "message": "Brain Dump import file is empty."}

    created_at, compact_stamp = now_stamp()
    run_id = f"{slugify(note_name, 'brain-dump')}-{compact_stamp}"
    backup_file, attachment_mapping = backup_import(root, note_name, compact_stamp, import_text)
    proposal_text = rewrite_wiki_paths(import_text, attachment_mapping)
    sections = extract_import_sections(proposal_text, note_name)
    items: list[ProposalItem] = []
    index = 0
    for section in sections:
        for block in split_blocks(section.content, note_name):
            index += 1
            items.append(write_proposal(root, run_id, index, section.heading, block, backup_file, created_at))
    base_path = ensure_base(root)
    if clear and items:
        clear_import(root)
    return {
        "status": "ok",
        "run_id": run_id,
        "backup": vault_rel(backup_file, root),
        "base": vault_rel(base_path, root),
        "proposal_count": len(items),
        "proposals": [vault_rel(item.path, root) for item in items],
        "attachment_count": len(attachment_mapping),
        "cleared_import": clear and bool(items),
    }


def clear_import(root: Path) -> None:
    inbox_path = root / INBOX_PATH
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text("", encoding="utf-8")


def clean_target_path(value: str) -> Path:
    clean = value.strip()
    if clean.startswith("[[") and clean.endswith("]]"):
        clean = clean[2:-2].split("|", 1)[0].strip()
    return Path(clean)


def extract_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", flags=re.M)
    match = pattern.search(body)
    if not match:
        return body.strip()
    start = match.end()
    next_match = re.search(r"^##\s+", body[start:], flags=re.M)
    end = start + next_match.start() if next_match else len(body)
    return body[start:end].strip()


def destination_attachment_dir(route: str, target_path: Path, run_id: str) -> Path:
    if route in ROUTE_TARGETS:
        context = ROUTE_TARGETS[route]["context"]
        if context in {"01-personal", "02-personal-brand", "03-business"}:
            return Path(context) / "_obsidian/attachments/brain-dump" / run_id
        if context == "library":
            return Path("library/_attachments/brain-dump") / run_id
    if target_path.parts and target_path.parts[0] in {"01-personal", "02-personal-brand", "03-business"}:
        return Path(target_path.parts[0]) / "_obsidian/attachments/brain-dump" / run_id
    return target_path.parent / "_attachments/brain-dump" / run_id


def copy_and_rewrite_attachments(root: Path, text: str, route: str, target_path: Path, run_id: str) -> str:
    mapping: dict[str, str] = {}
    rels = referenced_wiki_paths(text)
    if not rels:
        return text
    dest_dir = root / destination_attachment_dir(route, target_path, run_id)
    for rel in rels:
        source = root / rel
        if not source.exists() or source.is_dir():
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = unique_path(dest_dir / source.name)
        shutil.copy2(source, dest)
        mapping[rel] = vault_rel(dest, root)
    return rewrite_wiki_paths(text, mapping)


def markdown_title(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip().strip("#").strip()
    return clean or "Untitled"


def create_task(root: Path, proposal_path: Path, props: dict[str, Any], capture: str, now: str) -> Path:
    route = str(props.get("route", ""))
    target = ROUTE_TARGETS[route]
    title = markdown_title(str(props.get("title") or first_heading_or_words(capture, "Brain Dump Task")))
    directory = root / target["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    out_path = unique_path(directory / f"{sanitize_filename(title)}.md")
    capture = copy_and_rewrite_attachments(root, capture, route, out_path.relative_to(root), str(props.get("run_id", "")))
    data = {
        "title": title,
        "status": props.get("task_status") or "backlog",
        "priority": props.get("priority") or "normal",
        "contexts": [target["context"]],
        "dateCreated": now,
        "dateModified": now,
        "tags": ["task"],
    }
    body = (
        f"{frontmatter(data)}\n"
        f"# {title}\n\n"
        f"## Notes\n\n{capture}\n\n"
        f"## Source\n\n- Brain Dump proposal: {wiki_link(vault_rel(proposal_path, root))}\n"
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


def create_content_idea(root: Path, proposal_path: Path, props: dict[str, Any], capture: str, now: str) -> Path:
    route = str(props.get("route", ""))
    target = ROUTE_TARGETS[route]
    title = markdown_title(str(props.get("title") or first_heading_or_words(capture, "Brain Dump Content Idea")))
    directory = root / target["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    out_path = unique_path(directory / f"{sanitize_filename(title)}.md")
    capture = copy_and_rewrite_attachments(root, capture, route, out_path.relative_to(root), str(props.get("run_id", "")))
    data = {
        "type": "content",
        "entity": target["context"],
        "content_kind": props.get("content_kind") or "idea",
        "platform": props.get("platform") or "",
        "publication": "",
        "status": "idea",
        "source": wiki_link(vault_rel(proposal_path, root)),
        "tags": ["content"],
    }
    body = f"{frontmatter(data)}\n# {title}\n\n{capture}\n"
    out_path.write_text(body, encoding="utf-8")
    return out_path


def create_library_note(root: Path, proposal_path: Path, props: dict[str, Any], capture: str) -> Path:
    route = str(props.get("route", ""))
    title = markdown_title(str(props.get("title") or first_heading_or_words(capture, "Brain Dump Thought")))
    directory = root / ROUTE_TARGETS[route]["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    out_path = unique_path(directory / f"{sanitize_filename(title)}.md")
    capture = copy_and_rewrite_attachments(root, capture, route, out_path.relative_to(root), str(props.get("run_id", "")))
    body = f"# {title}\n\n{capture}\n\n## Source\n\n- Brain Dump proposal: {wiki_link(vault_rel(proposal_path, root))}\n"
    out_path.write_text(body, encoding="utf-8")
    return out_path


def append_to_existing_task(root: Path, proposal_path: Path, props: dict[str, Any], capture: str, now: str) -> Path:
    raw_target = str(props.get("target_path", "")).strip()
    if not raw_target:
        raise ValueError(f"{proposal_path}: approved append-to-existing-task is missing target_path")
    target_rel = clean_target_path(raw_target)
    target_path = root / target_rel
    if not target_path.exists():
        raise ValueError(f"{proposal_path}: target_path does not exist: {target_rel}")
    capture = copy_and_rewrite_attachments(root, capture, "append-to-existing-task", target_rel, str(props.get("run_id", "")))
    existing = target_path.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") else "\n"
    addition = (
        f"{separator}\n## Brain Dump Capture - {now}\n\n"
        f"{capture}\n\n"
        f"Source proposal: {wiki_link(vault_rel(proposal_path, root))}\n"
    )
    target_path.write_text(existing + addition, encoding="utf-8")
    return target_path


def update_proposal_status(root: Path, proposal_path: Path, props: dict[str, Any], body: str, output_path: Path, now: str) -> None:
    props["proposal_status"] = "applied"
    props["applied_to"] = wiki_link(vault_rel(output_path, root))
    props["applied_at"] = now
    props["dateModified"] = now
    proposal_path.write_text(f"{frontmatter(props)}\n{body}", encoding="utf-8")


def apply_proposals(root: Path, run_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    search_root = root / PROPOSALS_DIR / "runs"
    if run_id:
        paths = sorted((search_root / run_id / "items").glob("*.md"))
    else:
        paths = sorted(search_root.glob("*/items/*.md"))
    applied: list[str] = []
    skipped: list[str] = []
    blocked: list[str] = []
    now, _ = now_stamp()
    for proposal_path in paths:
        text = proposal_path.read_text(encoding="utf-8")
        props, body = parse_frontmatter(text)
        if props.get("proposal_status") != "approved":
            continue
        route = str(props.get("route", ""))
        capture = extract_section(body, "Capture")
        try:
            if dry_run:
                output_path = Path("dry-run")
            elif route in {"personal-task", "matt-task", "impression-task"}:
                output_path = create_task(root, proposal_path, props, capture, now)
            elif route in {"matt-content-idea", "impression-content-idea"}:
                output_path = create_content_idea(root, proposal_path, props, capture, now)
            elif route == "library-thought":
                output_path = create_library_note(root, proposal_path, props, capture)
            elif route == "append-to-existing-task":
                output_path = append_to_existing_task(root, proposal_path, props, capture, now)
            elif route == "skip":
                props["proposal_status"] = "skipped"
                props["dateModified"] = now
                if not dry_run:
                    proposal_path.write_text(f"{frontmatter(props)}\n{body}", encoding="utf-8")
                skipped.append(vault_rel(proposal_path, root))
                continue
            else:
                raise ValueError(f"{proposal_path}: unsupported approved route: {route}")
            if not dry_run:
                update_proposal_status(root, proposal_path, props, body, output_path, now)
            applied.append(vault_rel(proposal_path, root))
        except ValueError as error:
            blocked.append(f"{vault_rel(proposal_path, root)}: {error}")
    return {
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "blocked_count": len(blocked),
        "applied": applied,
        "skipped": skipped,
        "blocked": blocked,
    }


def cmd_prepare(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    result = prepare(root, clear=args.clear)
    print(json.dumps(result, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    result = apply_proposals(root, run_id=args.run_id, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0 if result["blocked_count"] == 0 else 1


def cmd_clear(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    clear_import(root)
    print(f"Cleared {INBOX_PATH}")
    return 0


def cmd_ensure_base(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    path = ensure_base(root)
    print(vault_rel(path, root))
    return 0


def cmd_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
        (root / ATTACHMENTS_DIR).mkdir(parents=True)
        (root / "master/system").mkdir(parents=True, exist_ok=True)
        (root / CONFIG_PATH).write_text(
            json.dumps({"brain_dump_ingest": {"note_name": "Brain Dump"}}, indent=2),
            encoding="utf-8",
        )
        attachment = root / ATTACHMENTS_DIR / "sample.png"
        attachment.write_bytes(b"fake")
        (root / INBOX_PATH).write_text(
            "## 2026-05-14T10:00:00 - Brain Dump\n\n"
            "# Brain Dump\n\n"
            "Book dentist\n\n"
            "UI references\n\n"
            f"![[{ATTACHMENTS_DIR / 'sample.png'}]]\n",
            encoding="utf-8",
        )
        result = prepare(root)
        assert result["proposal_count"] == 2, result
        assert result["attachment_count"] == 1, result
        proposal_path = root / result["proposals"][0]
        props, body = parse_frontmatter(proposal_path.read_text(encoding="utf-8"))
        props["proposal_status"] = "approved"
        props["route"] = "personal-task"
        props["target_context"] = "01-personal"
        props["target_kind"] = "task"
        proposal_path.write_text(f"{frontmatter(props)}\n{body}", encoding="utf-8")
        applied = apply_proposals(root, run_id=result["run_id"])
        assert applied["applied_count"] == 1, applied
        assert list((root / "01-personal/_obsidian/tasks").glob("*.md"))
        clear_import(root)
        assert (root / INBOX_PATH).read_text(encoding="utf-8") == ""
    print("self-test passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Brain Dump proposal board helper.")
    subparsers = parser.add_subparsers(required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Back up the import file and create proposal notes.")
    prepare_parser.add_argument("--root", default=None)
    prepare_parser.add_argument("--clear", action="store_true", help="Clear the import file after proposal creation.")
    prepare_parser.set_defaults(func=cmd_prepare)

    apply_parser = subparsers.add_parser("apply", help="Apply approved proposal notes.")
    apply_parser.add_argument("--root", default=None)
    apply_parser.add_argument("--run-id", default=None)
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.set_defaults(func=cmd_apply)

    clear_parser = subparsers.add_parser("clear-import", help="Empty the Brain Dump import file.")
    clear_parser.add_argument("--root", default=None)
    clear_parser.set_defaults(func=cmd_clear)

    base_parser = subparsers.add_parser("ensure-base", help="Write the Brain Dump triage Base.")
    base_parser.add_argument("--root", default=None)
    base_parser.set_defaults(func=cmd_ensure_base)

    self_test_parser = subparsers.add_parser("self-test", help="Run isolated script checks.")
    self_test_parser.set_defaults(func=cmd_self_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
