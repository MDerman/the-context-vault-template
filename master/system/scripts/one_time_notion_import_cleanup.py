#!/usr/bin/env python3
"""One-time cleanup for imported Notion exports and attachment routing.

This script is intentionally specific to the May 2026 workspace cleanup:

- copy 03-business attachments referenced from master/_obsidian/attachments into the
  03-business vault attachment folder and rewrite links
- move 02-personal-brand/TODO_EXPORTED_NOTION into 02-personal-brand with Notion IDs
  stripped from visible filenames
- centralize imported non-Markdown resources under 02-personal-brand/_obsidian/attachments
- add lightweight Learning/course frontmatter where the Notion CSV export gives
  enough metadata
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote


ROOT = Path(__file__).resolve().parents[3]
VAULT_02 = ROOT / "02-personal-brand"
SOURCE = VAULT_02 / "TODO_EXPORTED_NOTION"
VAULT_03 = ROOT / "03-business"
MASTER_ATTACHMENTS = ROOT / "master" / "_obsidian" / "attachments"
REPORT_ROOT = Path.home() / "Downloads" / "vault-generated" / "import-reports"
REPORT_DIR = REPORT_ROOT / "2026-05-11-notion-cleanup"
ICONIZE_PATH = ROOT / ".obsidian" / "plugins" / "obsidian-icon-folder" / "data.json"

ID_SUFFIX_RE = re.compile(
    r"\s+(?:[0-9a-f]{32}|[0-9a-f]{4,}(?:-[0-9a-f]{4,}){1,})$",
    re.IGNORECASE,
)
MD_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
WIKI_MASTER_ATTACHMENT_RE = re.compile(
    r"\[\[master/_obsidian/attachments/([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]"
)
LOCAL_SKIP_SCHEMES = (
    "http://",
    "https://",
    "mailto:",
    "obsidian://",
    "file://",
    "data:",
)


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


def clean_name(name: str) -> str:
    if name == ".DS_Store":
        return name
    stem, suffix = os.path.splitext(name)
    cleaned = ID_SUFFIX_RE.sub("", stem).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(" .")
    if not cleaned:
        cleaned = stem.strip() or "Untitled"
    return cleaned + suffix


def clean_parts(parts: tuple[str, ...]) -> list[str]:
    return [clean_name(part) for part in parts]


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() == ".md"


def is_ds_store(path: Path) -> bool:
    return path.name == ".DS_Store"


def is_tasks_time_database_path(source_rel: Path) -> bool:
    parts = source_rel.parts
    if not parts or parts[0] != "Tasks and Time":
        return False
    if len(parts) >= 2 and parts[1] in {"Sprints", "Tasks", "Products and Epics"}:
        return True
    root_database_prefixes = (
        "Sprints ",
        "Sprint board ",
        "Tasks ",
        "Products and Epics ",
        "Projects ",
    )
    return len(parts) == 2 and any(parts[1].startswith(prefix) for prefix in root_database_prefixes)


def is_learning_database_path(source_rel: Path) -> bool:
    parts = source_rel.parts
    return len(parts) >= 2 and parts[0] == "Learning" and parts[1] == "Databases"


def split_link_target(target: str) -> tuple[str, str]:
    raw = target.strip()
    if "#" in raw:
        before, after = raw.split("#", 1)
        return before, "#" + after
    return raw, ""


def is_local_target(target: str) -> bool:
    lowered = target.lower().strip()
    return bool(lowered) and not lowered.startswith(LOCAL_SKIP_SCHEMES)


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).strip()
    if not text:
        return '""'
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def frontmatter_block(props: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in props.items():
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def has_frontmatter(text: str) -> bool:
    return text.startswith("---\n")


def add_frontmatter(text: str, props: dict[str, Any]) -> str:
    if has_frontmatter(text):
        return text
    return frontmatter_block(props) + text


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        return list(csv.DictReader(handle))


def course_code_from_relation(value: str) -> str:
    if not value:
        return ""
    before = value.split("(", 1)[0].strip()
    return before.split()[0].strip() if before else ""


def load_learning_metadata() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    courses: dict[str, dict[str, str]] = {}
    course_csvs = [
        SOURCE / "Learning/UCT - Student Dashboard/Courses 948b41664759460dbb96e0d565bf4cf1_all.csv",
        SOURCE / "Learning/UCT - Student Dashboard/Courses 948b41664759460dbb96e0d565bf4cf1.csv",
    ]
    for csv_path in course_csvs:
        for row in read_csv_rows(csv_path):
            code = (row.get("Subjects") or "").strip()
            if not code:
                continue
            existing = courses.setdefault(code, {"code": code})
            for source_key, dest_key in [
                ("Credits", "credits"),
                ("Field", "field"),
                ("Level", "level"),
            ]:
                value = (row.get(source_key) or "").strip()
                if value and not existing.get(dest_key):
                    existing[dest_key] = value

    brainfood: dict[str, dict[str, str]] = {}
    brainfood_csvs = [
        SOURCE / "Learning/UCT - Student Dashboard/Brainfood 59778d662a1b46d2a59e632f2a288edc_all.csv",
        SOURCE / "Learning/UCT - Student Dashboard/Brainfood 59778d662a1b46d2a59e632f2a288edc.csv",
        SOURCE / "Learning/UCT - Student Dashboard/Untitled d2ab48c165f94bc5a3beba84347e2495.csv",
        SOURCE / "Learning/Brainfood (1) 35af4725f46880b6b44cc97db608d38b_all.csv",
        SOURCE / "Learning/Brainfood (1) 35af4725f46880b6b44cc97db608d38b.csv",
    ]
    for csv_path in brainfood_csvs:
        for row in read_csv_rows(csv_path):
            title = (row.get("Title") or "").strip()
            if not title:
                continue
            existing = brainfood.setdefault(title, {"title": title})
            course = course_code_from_relation(row.get("Course") or "")
            if course and not existing.get("course"):
                existing["course"] = course
            for source_key, dest_key in [
                ("Subject", "subject"),
                ("Topic/Field", "topic"),
                ("Confidence", "confidence"),
                ("Created", "created"),
                ("Tags", "tags"),
            ]:
                value = (row.get(source_key) or "").strip()
                if value and not existing.get(dest_key):
                    existing[dest_key] = value
    return courses, brainfood


def note_title_from_path(path: Path) -> str:
    return ID_SUFFIX_RE.sub("", path.stem).strip()


def dest_for_markdown(source_rel: Path, courses: dict[str, dict[str, str]], brainfood: dict[str, dict[str, str]]) -> Path:
    parts = source_rel.parts
    cleaned = clean_parts(parts)

    if parts[0] == "Learning":
        # Put Learning's own Notion wrapper pages inside their matching folders.
        if len(parts) == 2 and is_markdown(source_rel):
            title = clean_name(parts[1])[:-3]
            if title in {"Dev", "UCT - Student Dashboard"}:
                return VAULT_02 / "Learning" / title / f"{title}.md"

        if len(parts) >= 4 and parts[1] == "UCT - Student Dashboard" and parts[2] == "Courses":
            if len(parts) == 4 and is_markdown(source_rel):
                course = clean_name(parts[3])[:-3]
                if course in courses or re.fullmatch(r"[A-Z]{3}\d{4}[FSW]?", course):
                    return VAULT_02 / "Learning" / "UCT - Student Dashboard" / "Courses" / course / f"{course}.md"
            if len(parts) >= 4:
                course_folder = clean_name(parts[3])
                return VAULT_02.joinpath("Learning", "UCT - Student Dashboard", "Courses", course_folder, *cleaned[4:])

        if len(parts) >= 3 and parts[1] in {"Brainfood", "Brainfood (1)"} and is_markdown(source_rel):
            title = note_title_from_path(source_rel)
            meta = brainfood.get(title, {})
            course = meta.get("course")
            if course:
                return VAULT_02 / "Learning" / "UCT - Student Dashboard" / "Courses" / course / "Notes" / f"{clean_name(source_rel.name)}"
            return VAULT_02 / "Learning" / "UCT - Student Dashboard" / "Brainfood" / clean_name(source_rel.name)

        if len(parts) >= 3 and parts[1] in {"Brainfood", "Brainfood (1)"}:
            return VAULT_02.joinpath("Learning", "UCT - Student Dashboard", "Brainfood", *cleaned[2:])

    return VAULT_02.joinpath(*cleaned)


def dest_for_attachment(source_rel: Path) -> Path:
    parts = source_rel.parts
    cleaned = clean_parts(parts)
    if is_tasks_time_database_path(source_rel):
        return VAULT_02.joinpath("_obsidian", "attachments", "notion-import", "_skipped-databases", *cleaned)
    if is_learning_database_path(source_rel):
        return VAULT_02.joinpath("_obsidian", "attachments", "notion-import", "learning", "_databases", *cleaned[2:])
    return VAULT_02.joinpath("_obsidian", "attachments", "notion-import", *cleaned)


def unique_dest(path: Path, used: set[Path]) -> Path:
    candidate = path
    counter = 2
    while candidate in used or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        counter += 1
    used.add(candidate)
    return candidate


def build_manifest() -> tuple[list[dict[str, Any]], dict[Path, Path], dict[str, Any]]:
    courses, brainfood = load_learning_metadata()
    used: set[Path] = set()
    entries: list[dict[str, Any]] = []
    path_map: dict[Path, Path] = {}

    if not SOURCE.exists():
        raise SystemExit(f"Missing source export: {SOURCE}")

    for source_path in sorted(SOURCE.rglob("*")):
        if source_path.is_dir():
            continue
        source_rel = source_path.relative_to(SOURCE)
        action = "move"
        reason = ""
        if is_ds_store(source_path):
            action = "delete"
            dest = None
            reason = "macOS metadata"
        elif is_tasks_time_database_path(source_rel):
            dest = unique_dest(dest_for_attachment(source_rel), used)
            action = "archive-skipped-database"
            reason = "Tasks and Time Notion database/sprints/products/tasks material"
        elif is_markdown(source_path):
            dest = unique_dest(dest_for_markdown(source_rel, courses, brainfood), used)
        else:
            dest = unique_dest(dest_for_attachment(source_rel), used)

        entry = {
            "source": rel(source_path),
            "action": action,
            "reason": reason,
            "destination": rel(dest) if dest else None,
        }
        entries.append(entry)
        if dest:
            path_map[source_path.resolve()] = dest.resolve()

    metadata = {"courses": courses, "brainfood": brainfood}
    return entries, path_map, metadata


def resolve_source_link_candidates(current_source: Path, target: str) -> list[Path]:
    target_path, _fragment = split_link_target(target)
    if not is_local_target(target_path):
        return []
    decoded = unquote(target_path)
    if decoded.startswith("/"):
        candidate = ROOT / decoded.lstrip("/")
    else:
        candidate = (current_source.parent / decoded).resolve()
    candidates = [candidate]
    if candidate.suffix == "":
        candidates.append(candidate.with_suffix(".md"))
    try:
        relative_to_source = candidate.relative_to(SOURCE.resolve())
        if relative_to_source.parts and relative_to_source.parts[0] == "Dev":
            candidates.append((SOURCE / "Learning" / Path(*relative_to_source.parts[1:])).resolve())
            if candidates[-1].suffix == "":
                candidates.append(candidates[-1].with_suffix(".md"))
    except ValueError:
        pass
    unique: list[Path] = []
    seen: set[Path] = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def rewrite_markdown_links(text: str, source_path: Path, dest_path: Path, path_map: dict[Path, Path], stats: Counter) -> str:
    def replace(match: re.Match[str]) -> str:
        bang, label, target = match.groups()
        target_path, fragment = split_link_target(target)
        mapped = None
        for resolved in resolve_source_link_candidates(source_path.resolve(), target_path):
            mapped = path_map.get(resolved.resolve())
            if mapped:
                break
        if not mapped:
            return match.group(0)
        relative = os.path.relpath(mapped, start=dest_path.parent.resolve())
        relative = Path(relative).as_posix()
        rewritten = quote(relative, safe="/#%[]()'&,+-_.")
        stats["rewritten_markdown_links"] += 1
        return f"{bang}[{label}]({rewritten}{fragment})"

    return MD_LINK_RE.sub(replace, text)


def learning_frontmatter(source_path: Path, dest_path: Path, metadata: dict[str, Any]) -> dict[str, Any] | None:
    try:
        dest_rel = dest_path.relative_to(VAULT_02)
    except ValueError:
        return None
    parts = dest_rel.parts
    if not parts or parts[0] != "Learning" or dest_path.suffix.lower() != ".md":
        return None
    props: dict[str, Any] = {"contexts": ["02-personal-brand"]}
    courses: dict[str, dict[str, str]] = metadata["courses"]
    brainfood: dict[str, dict[str, str]] = metadata["brainfood"]

    if len(parts) >= 5 and parts[1] == "UCT - Student Dashboard" and parts[2] == "Courses" and parts[4] == f"{parts[3]}.md":
        course = parts[3]
        info = courses.get(course, {})
        props.update(
            {
                "type": "course",
                "course": course,
                "field": info.get("field", ""),
                "level": info.get("level", ""),
                "credits": info.get("credits", ""),
            }
        )
        return props

    title = dest_path.stem
    meta = brainfood.get(title, {})
    props.update(
        {
            "type": "learning-note",
            "course": meta.get("course", ""),
            "subject": meta.get("subject", ""),
            "topic": meta.get("topic", ""),
            "confidence": meta.get("confidence", ""),
            "created": meta.get("created", ""),
        }
    )
    tags = [tag.strip() for tag in re.split(r"[,;]", meta.get("tags", "")) if tag.strip()]
    if tags:
        props["tags"] = tags
    return props


def apply_02_import(entries: list[dict[str, Any]], path_map: dict[Path, Path], metadata: dict[str, Any], dry_run: bool) -> Counter:
    stats: Counter = Counter()
    if dry_run:
        for entry in entries:
            stats[entry["action"]] += 1
        return stats

    for entry in entries:
        source = ROOT / entry["source"]
        destination = ROOT / entry["destination"] if entry["destination"] else None
        action = entry["action"]
        stats[action] += 1

        if action == "delete":
            if source.exists():
                source.unlink()
            continue

        if not destination:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)

        if is_markdown(source) and action == "move":
            text = source.read_text(encoding="utf-8", errors="replace")
            text = rewrite_markdown_links(text, source, destination, path_map, stats)
            props = learning_frontmatter(source, destination, metadata)
            if props:
                text = add_frontmatter(text, props)
                stats["frontmatter_added"] += 1
            destination.write_text(text, encoding="utf-8")
            source.unlink()
        else:
            shutil.move(str(source), str(destination))

    for directory, _dirs, files in os.walk(SOURCE, topdown=False):
        path = Path(directory)
        if path == SOURCE:
            continue
        try:
            path.rmdir()
            stats["empty_dirs_removed"] += 1
        except OSError:
            pass

    return stats


def copy_03_master_attachments(dry_run: bool) -> Counter:
    stats: Counter = Counter()
    attachment_dest_dir = VAULT_03 / "_obsidian" / "attachments" / "notion-task-import"
    referenced: set[str] = set()
    for md_path in VAULT_03.rglob("*.md"):
        text = md_path.read_text(encoding="utf-8", errors="replace")
        for match in WIKI_MASTER_ATTACHMENT_RE.finditer(text):
            referenced.add(match.group(1))

    filename_map: dict[str, str] = {}
    used_names: set[str] = set()
    for name in sorted(referenced):
        source = MASTER_ATTACHMENTS / name
        cleaned = clean_name(name)
        candidate = cleaned
        idx = 2
        while candidate in used_names:
            candidate = f"{Path(cleaned).stem} ({idx}){Path(cleaned).suffix}"
            idx += 1
        used_names.add(candidate)
        filename_map[name] = candidate
        if not source.exists():
            stats["03_missing_master_attachments"] += 1
            continue
        destination = attachment_dest_dir / candidate
        stats["03_attachments_referenced"] += 1
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def replace(match: re.Match[str]) -> str:
        original_name = match.group(1)
        fragment = match.group(2) or ""
        alias = match.group(3) or ""
        mapped = filename_map.get(original_name, clean_name(original_name))
        stats["03_links_rewritten"] += 1
        return f"[[03-business/_obsidian/attachments/notion-task-import/{mapped}{fragment}{alias}]]"

    for md_path in VAULT_03.rglob("*.md"):
        text = md_path.read_text(encoding="utf-8", errors="replace")
        rewritten = WIKI_MASTER_ATTACHMENT_RE.sub(replace, text)
        if rewritten != text:
            stats["03_notes_updated"] += 1
            if not dry_run:
                md_path.write_text(rewritten, encoding="utf-8")

    return stats


def update_iconize(dry_run: bool) -> Counter:
    stats: Counter = Counter()
    updates = {
        "02-personal-brand/Matt writing etc": "✍️",
        "02-personal-brand/Matt writing etc.md": "✍️",
        "02-personal-brand/Matt writing etc/Blogs": "📝",
        "02-personal-brand/Matt writing etc/Youtube Factory": "🎬",
        "02-personal-brand/Matt writing etc/Content Schedules": "🗓️",
        "02-personal-brand/Matt writing etc/Content Pillars.md": "🏛️",
        "02-personal-brand/Learning": "🎓",
        "02-personal-brand/Learning/Dev": "💻",
        "02-personal-brand/Learning/UCT - Student Dashboard": "🎓",
    }
    if not ICONIZE_PATH.exists():
        return stats
    data = json.loads(ICONIZE_PATH.read_text(encoding="utf-8"))
    for key, value in updates.items():
        if data.get(key) != value:
            data[key] = value
            stats["iconize_updates"] += 1
    if stats["iconize_updates"] and not dry_run:
        ICONIZE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def write_reports(entries: list[dict[str, Any]], stats: Counter, dry_run: bool) -> None:
    if dry_run:
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "manifest.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    phase_counts = Counter()
    for entry in entries:
        dest = entry.get("destination") or ""
        if "Matt writing etc" in dest:
            phase_counts["phase1_matt_writing"] += 1
        elif "Tasks and Time" in dest or "_skipped-databases/Tasks and Time" in dest:
            phase_counts["phase2_tasks_time"] += 1
        elif "Notion Dashboard Overview" in dest:
            phase_counts["phase3_dashboard"] += 1
        elif "/Learning/" in dest:
            phase_counts["phase4_learning"] += 1
        else:
            phase_counts["root_or_other"] += 1

    lines = [
        "# Notion Import Cleanup Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Counts",
        "",
    ]
    for key, value in sorted(stats.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Phase Counts", ""])
    for key, value in sorted(phase_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    (REPORT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def print_summary(entries: list[dict[str, Any]], stats: Counter, dry_run: bool) -> None:
    print("mode:", "dry-run" if dry_run else "apply")
    if not dry_run:
        print("report:", rel(REPORT_DIR))
    print("manifest entries:", len(entries))
    for key, value in sorted(stats.items()):
        print(f"{key}: {value}")
    destinations_with_ids = [
        entry["destination"]
        for entry in entries
        if entry.get("destination") and ID_SUFFIX_RE.search(Path(entry["destination"]).stem)
    ]
    print("destinations_with_visible_notion_ids:", len(destinations_with_ids))
    if destinations_with_ids[:10]:
        print("sample destinations with ids:")
        for item in destinations_with_ids[:10]:
            print(" -", item)


def verify() -> int:
    failures: list[str] = []

    if SOURCE.exists():
        leftovers = [path for path in SOURCE.rglob("*") if path.is_file() and path.name != ".DS_Store"]
        if leftovers:
            failures.append(f"TODO_EXPORTED_NOTION still has {len(leftovers)} files")

    result = os.popen(f"rg -n 'master/_obsidian/attachments' {quote(str(VAULT_03), safe='/ ._-')!r} -g '*.md'").read().strip()
    if result:
        failures.append("03-business still references master/_obsidian/attachments")

    id_paths = []
    for path in VAULT_02.rglob("*"):
        if SOURCE in path.parents:
            continue
        if path.is_file() or path.is_dir():
            if ID_SUFFIX_RE.search(path.stem):
                id_paths.append(path)
    if id_paths:
        failures.append(f"02-personal-brand still has {len(id_paths)} visible paths ending in Notion IDs")

    if failures:
        print("verification: failed")
        for item in failures:
            print("-", item)
        return 1
    print("verification: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Perform the migration. Default is dry-run.")
    parser.add_argument("--verify-only", action="store_true", help="Run post-migration verification only.")
    args = parser.parse_args(argv)

    if args.verify_only:
        return verify()

    dry_run = not args.apply
    entries, path_map, metadata = build_manifest()
    stats: Counter = Counter()
    stats.update(copy_03_master_attachments(dry_run))
    stats.update(apply_02_import(entries, path_map, metadata, dry_run))
    stats.update(update_iconize(dry_run))
    write_reports(entries, stats, dry_run)
    print_summary(entries, stats, dry_run)
    if not dry_run:
        open_in_finder(REPORT_ROOT.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
