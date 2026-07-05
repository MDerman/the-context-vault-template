#!/usr/bin/env python3
"""Standardize Obsidian note attachments under each top-level root.

Default mode is a dry run that writes a report. Use --apply to move/copy files
and rewrite Markdown links. The migration is intentionally conservative:

- import attachment folders are emptied, with unreferenced files quarantined
- referenced cross-root attachments are copied into the consuming note's root
- obvious note sidecar folders are migrated
- standalone media libraries are left alone
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

from script_utils import discover_context_folders


ROOT = Path(__file__).resolve().parents[3]

SYSTEM_ROOTS = {
    "_library",
    "_master",
    "_wiki",
}


@lru_cache(maxsize=1)
def top_roots() -> set[str]:
    return set(discover_context_folders(ROOT)) | SYSTEM_ROOTS

SENSITIVE_DIR_NAMES = {
    ".env",
    "key",
    "keys",
    "kubeconfig",
    "secret",
    "secrets",
    "token",
    "tokens",
}

ATTACHMENT_EXTENSIONS = {
    ".avif",
    ".csv",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".svg",
    ".wav",
    ".webp",
    ".md",
}

MEDIA_SIDE_CAR_EXTENSIONS = ATTACHMENT_EXTENSIONS - {".md"}

LOCAL_SKIP_SCHEMES = (
    "http://",
    "https://",
    "mailto:",
    "obsidian://",
    "file://",
    "data:",
)

IMPORT_FOLDERS = [
    ROOT / "personal-brand" / "_obsidian" / "attachments" / "notion-import",
    ROOT / "business" / "_obsidian" / "attachments" / "notion-task-import",
]
IMPORT_MARKERS = {
    "notion-import": ROOT / "personal-brand" / "_obsidian" / "attachments" / "notion-import",
    "notion-task-import": ROOT / "business" / "_obsidian" / "attachments" / "notion-task-import",
}

MASTER_ATTACHMENTS = ROOT / "_master" / "_obsidian" / "attachments"
MASTER_INBOX = MASTER_ATTACHMENTS / "_inbox"
ARTIFACT_ROOT = Path.home() / "Downloads" / "vault-generated"
REPORT_ROOT = ARTIFACT_ROOT / "import-reports"
QUARANTINE_ROOT = ARTIFACT_ROOT / "attachment-cleanup-quarantine"
ICONIZE_PATH = ROOT / ".obsidian" / "plugins" / "obsidian-icon-folder" / "data.json"
FILE_COLOR_PATH = ROOT / ".obsidian" / "plugins" / "obsidian-file-color" / "data.json"

ID_SUFFIX_RE = re.compile(
    r"\s+(?:[0-9a-f]{32}|[0-9a-f]{4,}(?:-[0-9a-f]{4,}){1,})$",
    re.IGNORECASE,
)
WIKI_LINK_RE = re.compile(r"(!?)\[\[([^\n]*?)\]\]")
MARKDOWN_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!_])")
IMPORT_MARKER_MARKDOWN_RE = re.compile(
    r"(!?)\[([^\]]*)\]\(([^)\n]*(?:notion-import|notion-task-import)[^)\n]*)\)"
)
GENERIC_PASTE_RE = re.compile(r"^(?:Pasted image|image)(?:\s+(\d{8,14}))?$", re.IGNORECASE)


@dataclass(frozen=True)
class LinkSpan:
    kind: str
    start: int
    end: int
    bang: bool
    label: str
    target: str
    fragment: str = ""
    alias: str = ""


@dataclass
class PlannedDestination:
    source: Path
    destination: Path
    note_root: str
    reason: str
    remove_source: bool


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def open_in_finder(path: Path) -> None:
    if sys.platform != "darwin":
        return
    opener = shutil.which("open")
    if not opener:
        return
    subprocess.run([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def top_root(path: Path) -> str | None:
    try:
        first = path.resolve().relative_to(ROOT).parts[0]
    except (IndexError, ValueError):
        return None
    return first if first in top_roots() else None


def clean_name(name: str) -> str:
    if name == ".DS_Store":
        return name
    stem, suffix = os.path.splitext(name)
    cleaned = ID_SUFFIX_RE.sub("", stem).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).rstrip(" .")
    if not cleaned:
        cleaned = stem.strip() or "Untitled"
    return cleaned + suffix


def clean_parts(parts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(clean_name(part) for part in parts if part not in {"notion-import", "notion-task-import", "_inbox"})


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return cleaned or "attachment"


def clean_master_inbox_name(source: Path, note: Path | None) -> str:
    stem, suffix = os.path.splitext(clean_name(source.name))
    match = GENERIC_PASTE_RE.match(stem)
    if not match:
        return stem + suffix
    prefix = slugify(note.stem if note else "master-inbox")
    timestamp = match.group(1)
    suffix_part = f"-{timestamp}" if timestamp else ""
    return f"{prefix}-pasted-image{suffix_part}{suffix}"


def is_local_target(target: str) -> bool:
    lowered = target.lower().strip()
    return bool(lowered) and not lowered.startswith(LOCAL_SKIP_SCHEMES)


def markdown_unescape(value: str) -> str:
    return MARKDOWN_ESCAPE_RE.sub(r"\1", value)


def split_fragment(target: str) -> tuple[str, str]:
    if "#" not in target:
        return target, ""
    before, after = target.split("#", 1)
    return before, "#" + after


def strip_markdown_title(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1 : raw.index(">")]
    return raw


def normalize_target_path(raw: str) -> str:
    target = strip_markdown_title(raw)
    return markdown_unescape(unquote(target)).replace("\\", "/").strip()


def attachment_dir(root_name: str) -> Path:
    return ROOT / root_name / "_obsidian" / "attachments"


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def relative_to_first_matching_parent(path: Path, parents: list[Path]) -> tuple[Path, Path] | None:
    resolved = path.resolve()
    for parent in parents:
        try:
            return parent, resolved.relative_to(parent.resolve())
        except ValueError:
            continue
    return None


def iter_markdown_files() -> list[Path]:
    paths: list[Path] = []
    ignored_parts = {
        ".git",
        ".obsidian",
        "_master/import-reports",
        "other/attachment-cleanup-quarantine",
    }
    for path in ROOT.rglob("*.md"):
        rel_path = rel(path)
        if any(part in SENSITIVE_DIR_NAMES for part in Path(rel_path).parts):
            continue
        if any(rel_path == part or rel_path.startswith(part + "/") for part in ignored_parts):
            continue
        if "/_obsidian/attachments/" in rel_path:
            continue
        paths.append(path)
    return sorted(paths)


def find_closing_bracket(text: str, start: int) -> int:
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "]":
            return idx
    return -1


def find_closing_paren(text: str, start: int) -> int:
    escaped = False
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            if depth == 0:
                return idx
            depth -= 1
    return -1


def iter_markdown_link_spans(text: str) -> list[LinkSpan]:
    spans: list[LinkSpan] = []
    idx = 0
    while idx < len(text):
        bang = text[idx] == "!" and idx + 1 < len(text) and text[idx + 1] == "["
        if bang:
            start = idx
            label_start = idx + 2
        elif text[idx] == "[" and not (idx + 1 < len(text) and text[idx + 1] == "["):
            start = idx
            label_start = idx + 1
        else:
            idx += 1
            continue

        label_end = find_closing_bracket(text, label_start)
        if label_end == -1 or label_end + 1 >= len(text) or text[label_end + 1] != "(":
            idx += 1
            continue
        target_start = label_end + 2
        target_end = find_closing_paren(text, target_start)
        if target_end == -1:
            idx += 1
            continue
        label = text[label_start:label_end]
        raw_target = text[target_start:target_end]
        target_path, fragment = split_fragment(raw_target)
        spans.append(
            LinkSpan(
                kind="markdown",
                start=start,
                end=target_end + 1,
                bang=bang,
                label=label,
                target=target_path,
                fragment=fragment,
            )
        )
        idx = target_end + 1
    return spans


def iter_import_marker_markdown_spans(text: str) -> list[LinkSpan]:
    spans: list[LinkSpan] = []
    for match in IMPORT_MARKER_MARKDOWN_RE.finditer(text):
        raw_target = match.group(3)
        target_path, fragment = split_fragment(raw_target)
        spans.append(
            LinkSpan(
                kind="markdown",
                start=match.start(),
                end=match.end(),
                bang=bool(match.group(1)),
                label=match.group(2),
                target=target_path,
                fragment=fragment,
            )
        )
    return spans


def iter_wiki_link_spans(text: str) -> list[LinkSpan]:
    spans: list[LinkSpan] = []
    for match in WIKI_LINK_RE.finditer(text):
        bang = bool(match.group(1))
        body = match.group(2)
        if "|" in body:
            target_part, alias = body.split("|", 1)
        else:
            target_part, alias = body, ""
        target_path, fragment = split_fragment(target_part)
        spans.append(
            LinkSpan(
                kind="wiki",
                start=match.start(),
                end=match.end(),
                bang=bang,
                label="",
                target=target_path,
                fragment=fragment,
                alias=alias,
            )
        )
    return spans


def iter_link_spans(text: str) -> list[LinkSpan]:
    primary = iter_wiki_link_spans(text) + iter_markdown_link_spans(text)
    spans = primary[:]
    for fallback in iter_import_marker_markdown_spans(text):
        if any(not (fallback.end <= span.start or fallback.start >= span.end) for span in primary):
            continue
        spans.append(fallback)
    return sorted(spans, key=lambda span: span.start)


def build_basename_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    for root_name in top_roots():
        root_path = ROOT / root_name
        if not root_path.exists():
            continue
        for path in root_path.rglob("*"):
            if any(part in SENSITIVE_DIR_NAMES for part in path.relative_to(ROOT).parts):
                continue
            if path.is_file() and path.suffix.lower() in ATTACHMENT_EXTENSIONS:
                index[path.name].append(path.resolve())
    return index


def resolve_link_target(note: Path, target: str, basename_index: dict[str, list[Path]]) -> Path | None:
    target_path = normalize_target_path(target)
    if not is_local_target(target_path) or target_path.startswith("attachment:"):
        return None

    candidates: list[Path] = []
    path_obj = Path(target_path)
    parts = target_path.lstrip("/").split("/")
    if target_path.startswith("/"):
        candidates.append((ROOT / target_path.lstrip("/")).resolve())
    elif parts and parts[0] in top_roots():
        candidates.append((ROOT / target_path).resolve())
    else:
        candidates.append((note.parent / target_path).resolve())
        if "/" in target_path:
            candidates.append((ROOT / target_path).resolve())

    expanded: list[Path] = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.suffix == "":
            expanded.append(candidate.with_suffix(".md"))

    seen: set[Path] = set()
    for candidate in expanded:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    if "/" not in target_path and not path_obj.is_absolute():
        matches = basename_index.get(Path(target_path).name, [])
        if len(matches) == 1:
            return matches[0]

    return None


def target_relative_for_source(source: Path, note_root: str, reason: str, note: Path | None = None) -> tuple[str, ...]:
    source = source.resolve()
    import_match = relative_to_first_matching_parent(source, IMPORT_FOLDERS)
    if import_match:
        _parent, source_rel = import_match
        return clean_parts(source_rel.parts)

    if is_under(source, MASTER_INBOX):
        return (clean_master_inbox_name(source, note),)

    if is_under(source, MASTER_ATTACHMENTS):
        source_rel = source.relative_to(MASTER_ATTACHMENTS)
        return clean_parts(source_rel.parts)

    source_root = top_root(source)
    if source_root:
        try:
            parts = source.relative_to(ROOT / source_root).parts
        except ValueError:
            parts = (source.name,)
        if "_obsidian" in parts and "attachments" in parts:
            attach_index = parts.index("attachments")
            return clean_parts(parts[attach_index + 1 :])
        return clean_parts(parts)

    return (clean_name(source.name),)


def import_tail_from_target(target: str) -> tuple[str, tuple[str, ...]] | None:
    normalized = normalize_target_path(target)
    parts = tuple(part for part in normalized.split("/") if part and part != ".")
    for marker in IMPORT_MARKERS:
        if marker not in parts:
            continue
        marker_index = parts.index(marker)
        tail = parts[marker_index + 1 :]
        if tail:
            return marker, clean_parts(tail)
    return None


def find_quarantined_source(original_source: Path) -> Path | None:
    try:
        original_rel = original_source.resolve().relative_to(ROOT)
    except ValueError:
        return None
    if not QUARANTINE_ROOT.exists():
        return None
    for quarantine_dir in sorted(QUARANTINE_ROOT.iterdir(), reverse=True):
        candidate = quarantine_dir / original_rel
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def plan_import_marker_destination(
    note: Path,
    target: str,
    used: dict[Path, Path],
) -> PlannedDestination | None:
    note_root = top_root(note)
    parsed = import_tail_from_target(target)
    if not note_root or not parsed:
        return None
    marker, tail = parsed
    original_source = IMPORT_MARKERS[marker].joinpath(*tail)
    intended = attachment_dir(note_root).joinpath(*tail)

    if original_source.exists():
        source = original_source.resolve()
        remove_source = True
    elif intended.exists():
        source = intended.resolve()
        remove_source = False
    else:
        quarantined = find_quarantined_source(original_source)
        if not quarantined:
            return None
        source = quarantined
        remove_source = True

    destination = unique_destination(source, intended, used)
    return PlannedDestination(
        source=source,
        destination=destination,
        note_root=note_root,
        reason=f"{marker}-textual-reference",
        remove_source=remove_source,
    )


def sidecar_dir_for_note(note: Path) -> Path:
    return note.with_suffix("")


def is_sidecar_source(note: Path, source: Path) -> bool:
    sidecar = sidecar_dir_for_note(note)
    return sidecar.exists() and is_under(source, sidecar)


def should_migrate_reference(note: Path, source: Path) -> tuple[bool, str, bool]:
    note_root = top_root(note)
    if not note_root:
        return False, "", False

    if relative_to_first_matching_parent(source, IMPORT_FOLDERS):
        return True, "import-folder-reference", True

    if is_under(source, MASTER_INBOX):
        return True, "master-inbox-reference", True

    if is_under(source, MASTER_ATTACHMENTS) and "_inbox" not in source.relative_to(MASTER_ATTACHMENTS).parts:
        if note_root != "_master":
            return True, "_master-attachment-cross-root-reference", False
        return False, "", False

    source_root = top_root(source)
    if source_root:
        parts = source.relative_to(ROOT / source_root).parts
        if "_obsidian" in parts and "attachments" in parts:
            attach_index = parts.index("attachments")
            attachment_parts = parts[attach_index + 1 :]
            if source_root != note_root:
                return True, "cross-root-attachment-reference", False
            if any(part in {"notion-import", "notion-task-import", "_inbox"} for part in attachment_parts):
                return True, "staging-label-reference", True
            return False, "", False
        if "_attachments" in parts and source.suffix.lower() in MEDIA_SIDE_CAR_EXTENSIONS:
            return True, "legacy-attachments-folder-reference", True

    if is_sidecar_source(note, source) and source.suffix.lower() in MEDIA_SIDE_CAR_EXTENSIONS:
        return True, "note-sidecar-reference", True

    return False, "", False


def collect_sidecar_sources(markdown_files: list[Path]) -> list[tuple[Path, Path, str]]:
    sources: list[tuple[Path, Path, str]] = []
    for note in markdown_files:
        note_root = top_root(note)
        if not note_root:
            continue
        sidecar = sidecar_dir_for_note(note)
        if not sidecar.exists() or not sidecar.is_dir():
            continue
        for source in sorted(sidecar.rglob("*")):
            if source.is_file() and source.suffix.lower() in MEDIA_SIDE_CAR_EXTENSIONS:
                sources.append((note, source.resolve(), "note-sidecar-folder"))
    return sources


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def same_content(left: Path, right: Path) -> bool:
    if not left.exists() or not right.exists() or left.stat().st_size != right.stat().st_size:
        return False
    return file_digest(left) == file_digest(right)


def unique_destination(source: Path, intended: Path, used: dict[Path, Path]) -> Path:
    intended = intended.resolve()
    source = source.resolve()
    existing_source = used.get(intended)
    if existing_source == source:
        return intended
    if existing_source and same_content(source, existing_source):
        return intended
    if intended.exists() and same_content(source, intended):
        used[intended] = source
        return intended

    candidate = intended
    counter = 2
    while candidate in used or (candidate.exists() and not same_content(source, candidate)):
        candidate = intended.with_name(f"{intended.stem} ({counter}){intended.suffix}")
        counter += 1
    used[candidate] = source
    return candidate


def plan_destination(
    source: Path,
    note_root: str,
    reason: str,
    remove_source: bool,
    used: dict[Path, Path],
    note: Path | None = None,
) -> PlannedDestination:
    relative_parts = target_relative_for_source(source, note_root, reason, note)
    intended = attachment_dir(note_root).joinpath(*relative_parts)
    destination = unique_destination(source, intended, used)
    return PlannedDestination(
        source=source.resolve(),
        destination=destination.resolve(),
        note_root=note_root,
        reason=reason,
        remove_source=remove_source,
    )


def replacement_for(span: LinkSpan, destination: Path) -> str:
    dest_rel = rel(destination)
    target = dest_rel + span.fragment
    if span.kind == "wiki":
        alias = f"|{span.alias}" if span.alias else ""
        bang = "!" if span.bang else ""
        return f"{bang}[[{target}{alias}]]"
    if span.bang:
        return f"![[{target}]]"
    label = span.label.strip()
    if label and label != dest_rel:
        return f"[[{target}|{label}]]"
    return f"[[{target}]]"


def rewrite_note(text: str, replacements: dict[tuple[int, int], str]) -> str:
    if not replacements:
        return text
    chunks: list[str] = []
    cursor = 0
    for (start, end), replacement in sorted(replacements.items()):
        chunks.append(text[cursor:start])
        chunks.append(replacement)
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks)


def build_plan() -> tuple[
    dict[tuple[Path, str], PlannedDestination],
    dict[Path, dict[tuple[int, int], str]],
    list[dict[str, str]],
    Counter,
]:
    stats: Counter = Counter()
    markdown_files = iter_markdown_files()
    basename_index = build_basename_index()
    used_destinations: dict[Path, Path] = {}
    planned: dict[tuple[Path, str], PlannedDestination] = {}
    note_replacements: dict[Path, dict[tuple[int, int], str]] = defaultdict(dict)
    unresolved: list[dict[str, str]] = []

    for note in markdown_files:
        note_root = top_root(note)
        if not note_root:
            continue
        text = note.read_text(encoding="utf-8", errors="replace")
        for span in iter_link_spans(text):
            normalized = normalize_target_path(span.target)
            if normalized.startswith("attachment:"):
                unresolved.append(
                    {
                        "note": rel(note),
                        "target": normalized,
                        "reason": "attachment-colon-link",
                    }
                )
                stats["attachment_colon_links"] += 1
                continue
            source = resolve_link_target(note, span.target, basename_index)
            if not source:
                import_marker_plan = plan_import_marker_destination(note, span.target, used_destinations)
                if import_marker_plan:
                    key = (import_marker_plan.source, import_marker_plan.note_root)
                    planned.setdefault(key, import_marker_plan)
                    note_replacements[note][(span.start, span.end)] = replacement_for(span, import_marker_plan.destination)
                    stats[f"planned_{import_marker_plan.reason}"] += 1
                    stats["planned_link_rewrites"] += 1
                    continue
            if not source:
                continue
            migrate, reason, remove_source = should_migrate_reference(note, source)
            if not migrate:
                continue
            key = (source.resolve(), note_root)
            if key not in planned:
                planned[key] = plan_destination(source, note_root, reason, remove_source, used_destinations, note)
                stats[f"planned_{reason}"] += 1
            note_replacements[note][(span.start, span.end)] = replacement_for(span, planned[key].destination)
            stats["planned_link_rewrites"] += 1

    for note, source, reason in collect_sidecar_sources(markdown_files):
        note_root = top_root(note)
        if not note_root:
            continue
        key = (source.resolve(), note_root)
        if key not in planned:
            planned[key] = plan_destination(source, note_root, reason, True, used_destinations, note)
            stats[f"planned_{reason}"] += 1

    return planned, note_replacements, unresolved, stats


def ensure_attachment_dirs(dry_run: bool, stats: Counter) -> None:
    for root_name in sorted(top_roots()):
        directory = attachment_dir(root_name)
        stats["attachment_dirs_checked"] += 1
        if not directory.exists():
            stats["attachment_dirs_created"] += 1
            if not dry_run:
                directory.mkdir(parents=True, exist_ok=True)
    inbox = MASTER_INBOX
    if not inbox.exists():
        stats["attachment_inbox_created"] += 1
        if not dry_run:
            inbox.mkdir(parents=True, exist_ok=True)


def copy_planned_files(planned: dict[tuple[Path, str], PlannedDestination], dry_run: bool, stats: Counter) -> None:
    for item in planned.values():
        if item.source == item.destination:
            stats["files_already_in_place"] += 1
            continue
        if item.destination.exists() and same_content(item.source, item.destination):
            stats["files_reused_existing_destination"] += 1
            continue
        stats["files_copied"] += 1
        if not dry_run:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item.source, item.destination)


def rewrite_notes(note_replacements: dict[Path, dict[tuple[int, int], str]], dry_run: bool, stats: Counter) -> None:
    for note, replacements in sorted(note_replacements.items(), key=lambda item: rel(item[0])):
        text = note.read_text(encoding="utf-8", errors="replace")
        rewritten = rewrite_note(text, replacements)
        if rewritten == text:
            continue
        stats["notes_updated"] += 1
        if not dry_run:
            note.write_text(rewritten, encoding="utf-8")


def quarantine_path_for(source: Path, quarantine_root: Path, used: set[Path]) -> Path:
    try:
        source_rel = source.resolve().relative_to(ROOT)
    except ValueError:
        source_rel = Path(source.name)
    target = quarantine_root / source_rel
    candidate = target
    counter = 2
    while candidate in used or candidate.exists():
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        counter += 1
    used.add(candidate)
    return candidate


def cleanup_sources(
    planned: dict[tuple[Path, str], PlannedDestination],
    dry_run: bool,
    report_dir: Path,
    stats: Counter,
) -> list[dict[str, str]]:
    mapped_sources = {item.source for item in planned.values()}
    removable_sources = {item.source for item in planned.values() if item.remove_source}
    quarantine_root = QUARANTINE_ROOT / report_dir.name
    used_quarantine: set[Path] = set()
    quarantine_manifest: list[dict[str, str]] = []

    cleanup_folders = IMPORT_FOLDERS + [MASTER_INBOX]
    for cleanup_folder in cleanup_folders:
        if not cleanup_folder.exists():
            continue
        for source in sorted(cleanup_folder.rglob("*")):
            if not source.is_file():
                continue
            resolved = source.resolve()
            if source.name == ".DS_Store":
                stats["ds_store_deleted"] += 1
                if not dry_run:
                    source.unlink(missing_ok=True)
                continue
            if resolved in mapped_sources:
                continue
            target = quarantine_path_for(source, quarantine_root, used_quarantine)
            quarantine_manifest.append(
                {
                    "source": rel(source),
                    "destination": rel(target),
                    "reason": "unreferenced-staging-file",
                    "size": str(source.stat().st_size),
                }
            )
            stats["files_quarantined"] += 1
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))

    for source in sorted(removable_sources, key=rel):
        if not source.exists():
            continue
        stats["original_sources_removed"] += 1
        if not dry_run:
            source.unlink()

    for folder in IMPORT_FOLDERS:
        remove_empty_tree(folder, dry_run=dry_run, stats=stats)

    for source in sorted(removable_sources, key=rel):
        if is_under(source, QUARANTINE_ROOT):
            stop_at = QUARANTINE_ROOT
        else:
            stop_at = ROOT / (top_root(source) or "")
        remove_empty_parents(source.parent, stop_at=stop_at, dry_run=dry_run, stats=stats)

    return quarantine_manifest


def remove_empty_tree(path: Path, dry_run: bool, stats: Counter) -> None:
    if not path.exists():
        return
    for current, dirs, _files in os.walk(path, topdown=False):
        current_path = Path(current)
        for dirname in dirs:
            child = current_path / dirname
            try:
                if dry_run:
                    stats["empty_dirs_to_remove"] += 1
                else:
                    child.rmdir()
                    stats["empty_dirs_removed"] += 1
            except OSError:
                pass
        try:
            if dry_run:
                stats["empty_dirs_to_remove"] += 1
            else:
                current_path.rmdir()
                stats["empty_dirs_removed"] += 1
        except OSError:
            pass


def remove_empty_parents(path: Path, stop_at: Path, dry_run: bool, stats: Counter) -> None:
    current = path
    stop = stop_at.resolve()
    while current.exists():
        try:
            current_resolved = current.resolve()
            if current_resolved == stop or current_resolved == ROOT:
                break
            if dry_run:
                stats["empty_dirs_to_remove"] += 1
                break
            current.rmdir()
            stats["empty_dirs_removed"] += 1
            current = current.parent
        except OSError:
            break


def cleanup_obsidian_metadata(dry_run: bool, stats: Counter) -> None:
    stale_markers = ("notion-import", "notion-task-import")
    if ICONIZE_PATH.exists():
        data = json.loads(ICONIZE_PATH.read_text(encoding="utf-8"))
        keys = [key for key in data if any(marker in key for marker in stale_markers)]
        if keys:
            stats["iconize_entries_removed"] += len(keys)
            if not dry_run:
                for key in keys:
                    data.pop(key, None)
                ICONIZE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if FILE_COLOR_PATH.exists():
        data = json.loads(FILE_COLOR_PATH.read_text(encoding="utf-8"))
        entries = data.get("fileColors", [])
        kept = [
            entry
            for entry in entries
            if not any(marker in str(entry.get("path", "")) for marker in stale_markers)
        ]
        removed = len(entries) - len(kept)
        if removed:
            stats["file_color_entries_removed"] += removed
            if not dry_run:
                data["fileColors"] = kept
                FILE_COLOR_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_reports(
    report_dir: Path,
    planned: dict[tuple[Path, str], PlannedDestination],
    note_replacements: dict[Path, dict[tuple[int, int], str]],
    unresolved: list[dict[str, str]],
    quarantine_manifest: list[dict[str, str]],
    stats: Counter,
    dry_run: bool,
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest = [
        {
            "source": rel(item.source),
            "destination": rel(item.destination),
            "note_root": item.note_root,
            "reason": item.reason,
            "remove_source": item.remove_source,
        }
        for item in sorted(planned.values(), key=lambda item: (item.note_root, rel(item.source), rel(item.destination)))
    ]
    (report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "unresolved.json").write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "quarantine_manifest.json").write_text(
        json.dumps(quarantine_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Attachment Standardization Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Mode: {'dry-run' if dry_run else 'apply'}",
        "",
        "## Counts",
        "",
    ]
    for key, value in sorted(stats.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Planned destinations: {len(manifest)}",
            f"- Notes with rewrites: {len(note_replacements)}",
            f"- Unresolved links: {len(unresolved)}",
            f"- Quarantined files: {len(quarantine_manifest)}",
            "",
        ]
    )
    (report_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def print_summary(report_dir: Path, stats: Counter, planned_count: int, unresolved_count: int, dry_run: bool) -> None:
    print("mode:", "dry-run" if dry_run else "apply")
    print("output:", rel(ARTIFACT_ROOT))
    print("report:", rel(report_dir))
    print("planned destinations:", planned_count)
    print("unresolved links:", unresolved_count)
    for key, value in sorted(stats.items()):
        print(f"{key}: {value}")


def apply_migration(dry_run: bool) -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_dir = REPORT_ROOT / f"{timestamp}-attachment-standardization-{'dry-run' if dry_run else 'apply'}"
    planned, note_replacements, unresolved, stats = build_plan()
    ensure_attachment_dirs(dry_run, stats)
    copy_planned_files(planned, dry_run, stats)
    rewrite_notes(note_replacements, dry_run, stats)
    quarantine_manifest = cleanup_sources(planned, dry_run, report_dir, stats)
    cleanup_obsidian_metadata(dry_run, stats)
    write_reports(report_dir, planned, note_replacements, unresolved, quarantine_manifest, stats, dry_run)
    print_summary(report_dir, stats, len(planned), len(unresolved), dry_run)
    open_in_finder(ARTIFACT_ROOT)
    return 0


def verify() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    basename_index = build_basename_index()

    for folder in IMPORT_FOLDERS:
        if folder.exists():
            leftovers = [path for path in folder.rglob("*") if path.is_file()]
            if leftovers:
                failures.append(f"{rel(folder)} still has {len(leftovers)} file(s)")
            else:
                failures.append(f"{rel(folder)} still exists")

    for root_name in top_roots():
        if not attachment_dir(root_name).exists():
            failures.append(f"missing attachment folder: {root_name}/_obsidian/attachments")

    for note in iter_markdown_files():
        text = note.read_text(encoding="utf-8", errors="replace")
        note_root = top_root(note)
        for span in iter_link_spans(text):
            normalized = normalize_target_path(span.target)
            if "notion-import" in normalized or "notion-task-import" in normalized:
                failures.append(f"{rel(note)} references import path: {normalized}")
            if normalized.startswith("attachment:"):
                warnings.append(f"{rel(note)} has unresolved attachment pseudo-link")
                continue
            source = resolve_link_target(note, span.target, basename_index)
            if not source:
                continue
            source_root = top_root(source)
            if (
                note_root
                and source_root
                and is_under(source, ROOT / source_root / "_obsidian" / "attachments")
                and source_root != note_root
            ):
                failures.append(f"{rel(note)} links to cross-root attachment {rel(source)}")
            if note_root != "_master" and is_under(source, MASTER_ATTACHMENTS):
                failures.append(f"{rel(note)} links to _master attachment {rel(source)}")

    if failures:
        print("verification: failed")
        for item in failures[:100]:
            print("-", item)
        if len(failures) > 100:
            print(f"... {len(failures) - 100} more")
        return 1

    print("verification: ok")
    if warnings:
        print("warnings:")
        for item in warnings[:50]:
            print("-", item)
        if len(warnings) > 50:
            print(f"... {len(warnings) - 50} more")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Perform the migration. Default is dry-run.")
    parser.add_argument("--verify-only", action="store_true", help="Run verification only.")
    args = parser.parse_args(argv)

    if args.verify_only:
        return verify()
    return apply_migration(dry_run=not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
