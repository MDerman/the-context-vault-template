#!/usr/bin/env python3
"""Reconcile Notion-exported Learning media and deterministic generic embeds.

The command is intentionally dry-run by default.  It treats a fresh Notion
export as attachment truth while preserving current vault note prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import attachments
from script_utils import resolve_vault_root


MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".webp", ".heic"}
GENERIC_MEDIA_RE = re.compile(r"^Untitled(?: \d+)?\.(?:png|jpe?g|gif|pdf|webp|heic)$", re.IGNORECASE)
NOTION_ID_RE = re.compile(r"\s+[0-9a-f]{32}$", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)


@dataclass(frozen=True)
class AssetAction:
    source: Path
    destination: Path
    digest: str
    from_export: bool


@dataclass(frozen=True)
class NoteEdit:
    note: Path
    source_note: Path | None
    before: str
    after: str
    restored_embeds: int


@dataclass
class ReconcilePlan:
    asset_actions: list[AssetAction]
    note_edits: list[NoteEdit]
    conflicts: list[dict[str, str]]
    unmatched: list[dict[str, str]]
    stats: dict[str, int]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = NOTION_ID_RE.sub("", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def note_title(path: Path, text: str | None = None) -> str:
    text = text if text is not None else path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return NOTION_ID_RE.sub("", path.stem)


def slugify(value: str, maximum: int = 80) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    value = value[:maximum].rstrip("-")
    return value or "learning"


def snakeify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value or "attachment"


def natural_media_key(path: Path) -> tuple[str, int, str]:
    match = re.match(r"^(.*?)(?: (\d+))?$", path.stem)
    assert match
    return (match.group(1).casefold(), int(match.group(2) or 0), path.suffix.casefold())


def iter_media_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            yield path.resolve()


def media_spans(text: str) -> list[tuple[attachments.LinkSpan, str]]:
    found: list[tuple[attachments.LinkSpan, str]] = []
    for span in attachments.iter_link_spans(text):
        if not span.bang:
            continue
        target = attachments.normalize_target_path(span.target)
        if attachments.is_local_target(target) and Path(target).suffix.lower() in MEDIA_EXTENSIONS:
            found.append((span, target))
    return found


def export_targets(export_note: Path, text: str | None = None) -> list[Path]:
    text = text if text is not None else export_note.read_text(encoding="utf-8", errors="replace")
    targets: list[Path] = []
    for _span, target in media_spans(text):
        path = (export_note.parent / target).resolve()
        if not path.is_file():
            raise ValueError(f"export embed is missing: {export_note} -> {target}")
        targets.append(path)
    return targets


def normalized_body(text: str) -> str:
    text = FRONTMATTER_RE.sub("", text)
    replacements: list[tuple[int, int, str]] = []
    for span, target in media_spans(text):
        replacements.append((span.start, span.end, " MEDIA "))
    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    text = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^)]*\))*\)", r"\1", text)
    text = re.sub(r"<([^>]+)>", r"\1", text)
    text = re.sub(r"[0-9a-f]{32}", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def choose_export_note(
    current: Path,
    candidates: list[Path],
    export_root: Path,
    vault_root: Path,
    *,
    unique_export_title: bool,
) -> Path | None:
    rel = current.relative_to(vault_root / "_library")
    filtered = candidates[:]
    if rel.parts[0] == "_dev":
        filtered = [path for path in filtered if path.relative_to(export_root).parts[0] == "Dev"]
    elif rel.parts[0] == "_uct":
        branch = rel.parts[1] if len(rel.parts) > 1 else ""
        if branch == "brainfood_no_courses":
            filtered = [path for path in filtered if path.relative_to(export_root).parts[0] == "Brainfood (1)"]
        elif branch == "brainfood":
            text = current.read_text(encoding="utf-8", errors="replace")
            wants_top = "../UCT%20-%20Student%20Dashboard/" in text or "../UCT - Student Dashboard/" in text
            preferred = "Brainfood (1)" if wants_top else "UCT - Student Dashboard"
            narrowed = [path for path in filtered if path.relative_to(export_root).parts[0] == preferred]
            filtered = narrowed or filtered
        else:
            narrowed = [path for path in filtered if path.relative_to(export_root).parts[0] == "UCT - Student Dashboard"]
            filtered = narrowed or filtered
    if not filtered:
        return None
    if unique_export_title and len(filtered) == 1:
        return filtered[0]
    current_body = normalized_body(current.read_text(encoding="utf-8", errors="replace"))
    scored = sorted(
        ((similarity(current_body, normalized_body(path.read_text(encoding="utf-8", errors="replace"))), path) for path in filtered),
        key=lambda item: (-item[0], item[1].as_posix()),
    )
    if scored[0][0] < 0.35:
        return None
    if len(scored) == 1 or scored[0][0] > scored[1][0] + 0.02:
        return scored[0][1]
    return None


def similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    # Fast, deterministic overlap score is sufficient after exact title/branch filtering.
    left_words = set(left.split())
    right_words = set(right.split())
    return len(left_words & right_words) / max(len(left_words | right_words), 1)


def map_library_notes(vault_root: Path, export_root: Path) -> tuple[dict[Path, Path], list[dict[str, str]]]:
    export_by_title: dict[str, list[Path]] = defaultdict(list)
    all_export_by_title: dict[str, list[Path]] = defaultdict(list)
    for path in export_root.rglob("*.md"):
        key = normalized_title(note_title(path))
        all_export_by_title[key].append(path.resolve())
        if export_targets(path):
            export_by_title[key].append(path.resolve())

    mappings: dict[Path, Path] = {}
    unmatched: list[dict[str, str]] = []
    for scope in (vault_root / "_library" / "_dev", vault_root / "_library" / "_uct"):
        for current in scope.rglob("*.md"):
            current = current.resolve()
            key = normalized_title(note_title(current))
            candidates = export_by_title.get(key, [])
            if current == (vault_root / "_library/_dev/networks/networks.md").resolve():
                candidates = [
                    path
                    for path in export_root.rglob("Networks *.md")
                    if path.relative_to(export_root).parts[:2] == ("Dev", "Networks")
                ]
            if not candidates:
                continue
            chosen = choose_export_note(
                current,
                candidates,
                export_root,
                vault_root,
                unique_export_title=len(all_export_by_title.get(key, [])) == 1,
            )
            if chosen:
                mappings[current] = chosen
            elif media_spans(current.read_text(encoding="utf-8", errors="replace")):
                unmatched.append({"note": current.relative_to(vault_root).as_posix(), "reason": "ambiguous export-note mapping"})
    return mappings, unmatched


def unique_asset_names(
    targets: set[Path],
    hashes: dict[Path, str],
    reserved: set[str],
    existing_media_names: dict[str, list[tuple[Path, str]]],
) -> tuple[dict[str, str], dict[str, Path]]:
    canonical_by_hash: dict[str, Path] = {}
    for target in sorted(targets):
        canonical_by_hash.setdefault(hashes[target], target)
    name_by_hash: dict[str, str] = {}
    for digest, target in sorted(canonical_by_hash.items(), key=lambda item: item[1].as_posix()):
        siblings = sorted(
            [path for path in target.parent.iterdir() if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS],
            key=natural_media_key,
        )
        ordinal = siblings.index(target) + 1
        base = f"{slugify(target.parent.name)}-image-{ordinal:03d}{target.suffix.lower()}"
        candidate = base
        existing = existing_media_names.get(candidate.casefold(), [])
        already_canonical = len(existing) == 1 and existing[0][1] == digest
        if not already_canonical:
            if candidate.casefold() in reserved:
                candidate = f"{Path(base).stem}-{digest[:8]}{Path(base).suffix}"
            counter = 2
            while candidate.casefold() in reserved:
                candidate = f"{Path(base).stem}-{digest[:8]}-{counter}{Path(base).suffix}"
                counter += 1
        reserved.add(candidate.casefold())
        name_by_hash[digest] = candidate
    return name_by_hash, canonical_by_hash


def export_destination(export_root: Path, target: Path, attachment_root: Path, filename: str) -> Path:
    rel = target.relative_to(export_root)
    if rel.parts[0] == "Dev":
        branch = "dev"
    elif rel.parts[0] == "UCT - Student Dashboard":
        branch = "uct_student_dashboard"
    else:
        raise ValueError(f"cannot route exported asset outside Learning branches: {rel}")
    folders = [snakeify(part) for part in rel.parts[1:-1]]
    return attachment_root.joinpath(branch, *folders, filename).resolve()


def replace_spans(text: str, replacements: list[tuple[int, int, str]]) -> str:
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def anchor_text(line: str) -> str:
    if media_spans(line):
        return ""
    line = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^)]*\))*\)", r"\1", line)
    line = re.sub(r"[0-9a-f]{32}", "", line, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", line).casefold())


def insert_missing_embeds(current_text: str, export_text: str, missing: list[tuple[int, str]]) -> tuple[str, list[str]]:
    if not missing:
        return current_text, []
    export_lines = export_text.splitlines()
    current_lines = current_text.splitlines()
    current_anchors: dict[str, list[int]] = defaultdict(list)
    for index, line in enumerate(current_lines):
        anchor = anchor_text(line)
        if anchor:
            current_anchors[anchor].append(index)
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for export_line_index, embed in missing:
        previous = ""
        following = ""
        for line in reversed(export_lines[:export_line_index]):
            previous = anchor_text(line)
            if previous:
                break
        for line in export_lines[export_line_index + 1 :]:
            following = anchor_text(line)
            if following:
                break
        groups[(previous, following)].append(embed)
    conflicts: list[str] = []
    insertions: list[tuple[int, list[str]]] = []
    for (previous, following), embeds in groups.items():
        prev_hits = current_anchors.get(previous, []) if previous else []
        next_hits = current_anchors.get(following, []) if following else []
        position: int | None = None
        if len(next_hits) == 1 and (not prev_hits or prev_hits[-1] < next_hits[0]):
            position = next_hits[0]
        elif len(prev_hits) == 1:
            position = prev_hits[0] + 1
        if position is None:
            conflicts.append(f"could not align missing embed between {previous!r} and {following!r}")
        else:
            insertions.append((position, embeds))
    if conflicts:
        return current_text, conflicts
    for position, embeds in sorted(insertions, reverse=True):
        block = ["", *embeds, ""]
        current_lines[position:position] = block
    suffix = "\n" if current_text.endswith("\n") else ""
    return "\n".join(current_lines).rstrip("\n") + suffix, []


def rewrite_from_export(
    current: Path,
    source_note: Path,
    name_by_hash: dict[str, str],
    hashes: dict[Path, str],
) -> tuple[str, int, list[str]]:
    before = current.read_text(encoding="utf-8", errors="replace")
    export_text = source_note.read_text(encoding="utf-8", errors="replace")
    source_targets = export_targets(source_note, export_text)
    current_spans = media_spans(before)
    if len(current_spans) == len(source_targets) and all(
        GENERIC_MEDIA_RE.match(Path(target).name) for _span, target in current_spans
    ):
        replacements = [
            (span.start, span.end, f"![[{name_by_hash[hashes[target]]}]]")
            for (span, _raw_target), target in zip(current_spans, source_targets)
        ]
        return replace_spans(before, replacements), 0, []
    source_by_basename: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for index, target in enumerate(source_targets):
        source_by_basename[target.name.casefold()].append((index, target))
    used: set[int] = set()
    replacements: list[tuple[int, int, str]] = []
    for span, raw_target in media_spans(before):
        basename = Path(raw_target).name.casefold()
        candidates = source_by_basename.get(basename, [])
        available = [item for item in candidates if item[0] not in used]
        if not available:
            continue
        chosen: tuple[int, Path] | None = None
        if len(available) == 1:
            chosen = available[0]
        else:
            canonical_names = {name_by_hash[hashes[item[1]]] for item in available}
            if len(canonical_names) == 1:
                chosen = available[0]
            normalized_raw = raw_target.casefold().replace("\\", "/")
            exact = [item for item in available if item[1].name.casefold() == basename and item[1].parent.name.casefold() in normalized_raw]
            if chosen is None and len(exact) == 1:
                chosen = exact[0]
            if chosen is None and GENERIC_MEDIA_RE.match(Path(raw_target).name):
                # Notion can reuse names such as "Untitled 2.png" in nested
                # directories. The current import loses that directory context,
                # but retains embed order, so consume the exported occurrences
                # in the same order.
                chosen = available[0]
        if chosen is None:
            continue
        index, target = chosen
        used.add(index)
        filename = name_by_hash[hashes[target]]
        replacements.append((span.start, span.end, f"![[{filename}]]"))
    rewritten = replace_spans(before, replacements)
    missing: list[tuple[int, str]] = []
    source_spans = media_spans(export_text)
    for index, target in enumerate(source_targets):
        if index in used:
            continue
        filename = name_by_hash[hashes[target]]
        embed = f"![[{filename}]]"
        if embed in rewritten:
            continue
        line_index = export_text[: source_spans[index][0].start].count("\n")
        missing.append((line_index, embed))
    rewritten, conflicts = insert_missing_embeds(rewritten, export_text, missing)
    return rewritten, len(missing), conflicts


def build_primary_plan(vault_root: Path, export_root: Path, reserved: set[str]) -> ReconcilePlan:
    mappings, unmatched = map_library_notes(vault_root, export_root)
    target_notes = set(mappings.values())
    targets: set[Path] = set()
    for source_note in target_notes:
        targets.update(export_targets(source_note))
    hashes = {target: sha256_file(target) for target in targets}
    learning_root = (vault_root / "_library/_obsidian/attachments/learning").resolve()
    existing_by_hash: dict[str, list[Path]] = defaultdict(list)
    existing_media_names: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path in iter_media_files(vault_root):
        digest = sha256_file(path)
        existing_media_names[path.name.casefold()].append((path, digest))
    for path in iter_media_files(learning_root):
        existing_by_hash[sha256_file(path)].append(path)
    name_by_hash, canonical = unique_asset_names(targets, hashes, reserved, existing_media_names)
    actions: list[AssetAction] = []
    for digest, canonical_target in canonical.items():
        filename = name_by_hash[digest]
        existing = sorted(existing_by_hash.get(digest, []))
        if existing:
            source = existing[0]
            destination = source.with_name(filename)
            from_export = False
        else:
            source = canonical_target
            destination = export_destination(export_root, canonical_target, learning_root, filename)
            from_export = True
        if source != destination:
            actions.append(AssetAction(source, destination, digest, from_export))
    edits: list[NoteEdit] = []
    conflicts: list[dict[str, str]] = []
    for note, source_note in sorted(mappings.items()):
        before = note.read_text(encoding="utf-8", errors="replace")
        after, restored, problems = rewrite_from_export(note, source_note, name_by_hash, hashes)
        if problems:
            conflicts.append(
                {
                    "scope": "primary",
                    "note": note.relative_to(vault_root).as_posix(),
                    "source_note": source_note.relative_to(export_root).as_posix(),
                    "reason": "; ".join(problems),
                }
            )
            continue
        if after != before:
            edits.append(NoteEdit(note, source_note, before, after, restored))
    stats = {
        "mapped_library_notes": len(mappings),
        "export_asset_targets": len(targets),
        "unique_export_assets": len(canonical),
        "asset_actions": len(actions),
        "note_edits": len(edits),
        "restored_embeds": sum(edit.restored_embeds for edit in edits),
    }
    return ReconcilePlan(actions, edits, conflicts, unmatched, stats)


def deterministic_generic_plan(vault_root: Path, reserved: set[str], excluded_notes: set[Path]) -> ReconcilePlan:
    vault_root = vault_root.resolve()
    attachment_dirs: dict[str, dict[Path, set[str]]] = defaultdict(lambda: defaultdict(set))
    for path in vault_root.rglob("*"):
        if not path.is_file() or not GENERIC_MEDIA_RE.match(path.name):
            continue
        rel = path.relative_to(vault_root)
        if ".git" in rel.parts:
            continue
        if tuple(part.casefold() for part in rel.parts[:4]) == ("_library", "_obsidian", "attachments", "learning"):
            continue
        attachment_dirs[rel.parts[0]][path.parent.resolve()].add(path.name.casefold())

    note_to_dir: dict[Path, Path] = {}
    conflicts: list[dict[str, str]] = []
    for note in vault_root.rglob("*.md"):
        note = note.resolve()
        rel = note.relative_to(vault_root)
        if note in excluded_notes or ".git" in rel.parts or ".obsidian" in rel.parts:
            continue
        if len(rel.parts) >= 2 and rel.parts[0] == "_library" and rel.parts[1].casefold() in {"_dev", "_uct"}:
            continue
        if rel.parts[:3] == ("_system", "state", "library-reorg"):
            continue
        needed = {
            Path(target).name.casefold()
            for _span, target in media_spans(note.read_text(encoding="utf-8", errors="replace"))
            if GENERIC_MEDIA_RE.match(Path(target).name)
        }
        if not needed:
            continue
        candidates = [directory for directory, names in attachment_dirs[rel.parts[0]].items() if needed <= names]
        note_name = normalized_title(note.stem)
        named = [directory for directory in candidates if normalized_title(directory.name) == note_name]
        suffix: list[Path] = []
        attachment_root = vault_root / rel.parts[0] / "_obsidian/attachments"
        note_parts = [normalized_title(part) for part in note.with_suffix("").relative_to(vault_root / rel.parts[0]).parts]
        for directory in candidates:
            try:
                dir_parts = [normalized_title(part) for part in directory.relative_to(attachment_root).parts]
            except ValueError:
                continue
            if len(dir_parts) >= len(note_parts) and dir_parts[-len(note_parts) :] == note_parts:
                suffix.append(directory)
        chosen = suffix[0] if len(suffix) == 1 else named[0] if len(named) == 1 else None
        if chosen:
            note_to_dir[note] = chosen
        else:
            conflicts.append(
                {
                    "scope": "deterministic-global",
                    "note": rel.as_posix(),
                    "reason": "no deterministic generic attachment directory" if not candidates else f"{len(candidates)} possible attachment directories",
                }
            )

    source_to_name: dict[Path, str] = {}
    actions: list[AssetAction] = []
    for directory in sorted(set(note_to_dir.values())):
        files = sorted([path for path in directory.iterdir() if path.is_file() and GENERIC_MEDIA_RE.match(path.name)], key=natural_media_key)
        for ordinal, source in enumerate(files, start=1):
            digest = sha256_file(source)
            base = f"{slugify(directory.name)}-image-{ordinal:03d}{source.suffix.lower()}"
            candidate = base
            if candidate.casefold() in reserved:
                candidate = f"{Path(base).stem}-{digest[:8]}{Path(base).suffix}"
            counter = 2
            while candidate.casefold() in reserved:
                candidate = f"{Path(base).stem}-{digest[:8]}-{counter}{Path(base).suffix}"
                counter += 1
            reserved.add(candidate.casefold())
            source_to_name[source.resolve()] = candidate
            actions.append(AssetAction(source.resolve(), source.with_name(candidate).resolve(), digest, False))

    edits: list[NoteEdit] = []
    for note, directory in sorted(note_to_dir.items()):
        before = note.read_text(encoding="utf-8", errors="replace")
        replacements: list[tuple[int, int, str]] = []
        by_basename = {source.name.casefold(): name for source, name in source_to_name.items() if source.parent == directory}
        for span, target in media_spans(before):
            name = by_basename.get(Path(target).name.casefold())
            if name:
                replacements.append((span.start, span.end, f"![[{name}]]"))
        after = replace_spans(before, replacements)
        if after != before:
            edits.append(NoteEdit(note, None, before, after, 0))
    stats = {
        "deterministic_global_notes": len(note_to_dir),
        "deterministic_global_asset_actions": len(actions),
        "deterministic_global_note_edits": len(edits),
    }
    return ReconcilePlan(actions, edits, conflicts, [], stats)


def merge_plans(primary: ReconcilePlan, secondary: ReconcilePlan | None) -> ReconcilePlan:
    if not secondary:
        return primary
    actions_by_source = {action.source: action for action in primary.asset_actions}
    for action in secondary.asset_actions:
        actions_by_source.setdefault(action.source, action)
    edits_by_note = {edit.note: edit for edit in primary.note_edits}
    for edit in secondary.note_edits:
        edits_by_note.setdefault(edit.note, edit)
    return ReconcilePlan(
        list(actions_by_source.values()),
        list(edits_by_note.values()),
        primary.conflicts + secondary.conflicts,
        primary.unmatched + secondary.unmatched,
        {**primary.stats, **secondary.stats},
    )


def serialize_plan(plan: ReconcilePlan, vault_root: Path, export_root: Path) -> dict[str, object]:
    def display(path: Path) -> str:
        try:
            return path.relative_to(vault_root).as_posix()
        except ValueError:
            try:
                return "EXPORT/" + path.relative_to(export_root).as_posix()
            except ValueError:
                return path.as_posix()
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "vault_root": vault_root.as_posix(),
        "export_root": export_root.as_posix(),
        "stats": plan.stats,
        "asset_actions": [
            {
                "source": display(action.source),
                "destination": display(action.destination),
                "sha256": action.digest,
                "from_export": action.from_export,
            }
            for action in sorted(plan.asset_actions, key=lambda item: item.destination.as_posix())
        ],
        "note_edits": [
            {
                "note": display(edit.note),
                "source_note": display(edit.source_note) if edit.source_note else None,
                "restored_embeds": edit.restored_embeds,
            }
            for edit in sorted(plan.note_edits, key=lambda item: item.note.as_posix())
        ],
        "conflicts": plan.conflicts,
        "unmatched": plan.unmatched,
    }


def write_reports(plan: ReconcilePlan, vault_root: Path, export_root: Path) -> tuple[Path, Path]:
    payload = serialize_plan(plan, vault_root, export_root)
    state_dir = vault_root / "_system/local/state/learning-attachment-reconciliation"
    external_dir = Path.home() / "Downloads/vault-generated/learning-attachment-reconciliation"
    state_dir.mkdir(parents=True, exist_ok=True)
    external_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "latest.json"
    external_path = external_dir / "latest.json"
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    state_path.write_text(rendered, encoding="utf-8")
    external_path.write_text(rendered, encoding="utf-8")
    return state_path, external_path


def validate_plan(plan: ReconcilePlan) -> None:
    destinations: dict[Path, AssetAction] = {}
    names: dict[str, Path] = {}
    for action in plan.asset_actions:
        if sha256_file(action.source) != action.digest:
            raise ValueError(f"source hash changed: {action.source}")
        if action.destination in destinations and destinations[action.destination].digest != action.digest:
            raise ValueError(f"destination collision: {action.destination}")
        if action.destination.exists() and action.destination != action.source and sha256_file(action.destination) != action.digest:
            raise ValueError(f"destination already contains different content: {action.destination}")
        destinations[action.destination] = action
        folded = action.destination.name.casefold()
        if folded in names and names[folded] != action.destination:
            raise ValueError(f"global basename collision: {action.destination.name}")
        names[folded] = action.destination


def apply_plan(plan: ReconcilePlan) -> None:
    validate_plan(plan)
    for action in sorted(plan.asset_actions, key=lambda item: item.destination.as_posix()):
        action.destination.parent.mkdir(parents=True, exist_ok=True)
        if action.destination.exists():
            if sha256_file(action.destination) != action.digest:
                raise ValueError(f"refusing to overwrite different file: {action.destination}")
        elif action.from_export:
            shutil.copy2(action.source, action.destination)
        else:
            action.source.rename(action.destination)
        if sha256_file(action.destination) != action.digest:
            raise ValueError(f"destination verification failed: {action.destination}")
    for edit in sorted(plan.note_edits, key=lambda item: item.note.as_posix()):
        current = edit.note.read_text(encoding="utf-8", errors="replace")
        if current != edit.before:
            raise ValueError(f"note changed after planning: {edit.note}")
        edit.note.write_text(edit.after, encoding="utf-8")


def current_reserved_basenames(vault_root: Path) -> set[str]:
    return {path.name.casefold() for path in vault_root.rglob("*") if path.is_file()}


def verify_applied(plan: ReconcilePlan, vault_root: Path) -> list[str]:
    failures: list[str] = []
    rewritten_names = {action.destination.name.casefold() for action in plan.asset_actions}
    basename_index: dict[str, list[Path]] = defaultdict(list)
    for path in vault_root.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(vault_root).parts:
            basename_index[path.name.casefold()].append(path)
    for action in plan.asset_actions:
        if not action.destination.is_file() or sha256_file(action.destination) != action.digest:
            failures.append(f"bad destination: {action.destination}")
    for edit in plan.note_edits:
        text = edit.note.read_text(encoding="utf-8", errors="replace")
        for _span, target in media_spans(text):
            name = Path(target).name.casefold()
            if name in rewritten_names and len(basename_index[name]) != 1:
                failures.append(f"non-unique rewritten basename: {edit.note} -> {Path(target).name}")
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconcile-learning-export", required=True, type=Path, metavar="PATH")
    parser.add_argument("--repair-deterministic-global", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vault_root = resolve_vault_root(args.root, __file__)
    export_root = args.reconcile_learning_export.expanduser().resolve()
    if not export_root.is_dir():
        raise SystemExit(f"Learning export not found: {export_root}")
    reserved = current_reserved_basenames(vault_root)
    primary = build_primary_plan(vault_root, export_root, reserved)
    secondary = None
    if args.repair_deterministic_global:
        secondary = deterministic_generic_plan(vault_root, reserved, set(primary_note.note for primary_note in primary.note_edits))
    plan = merge_plans(primary, secondary)
    validate_plan(plan)
    state_report, external_report = write_reports(plan, vault_root, export_root)
    print(json.dumps(plan.stats, indent=2))
    print(f"conflicts: {len(plan.conflicts)}")
    print(f"unmatched: {len(plan.unmatched)}")
    print(f"state report: {state_report}")
    print(f"external report: {external_report}")
    if not args.apply:
        print("dry-run: no vault notes or attachments changed")
        return 0
    blocking_conflicts = [item for item in plan.conflicts if item.get("scope") == "primary"]
    if blocking_conflicts or plan.unmatched:
        print("apply refused: resolve or explicitly exclude all primary reconciliation conflicts")
        return 2
    apply_plan(plan)
    failures = verify_applied(plan, vault_root)
    if failures:
        for failure in failures[:100]:
            print(f"verification failure: {failure}")
        return 1
    print("apply complete and verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
