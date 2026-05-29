#!/usr/bin/env python3
"""Flatten UCT course pages and normalize Brainfood learning notes.

This is a one-time companion cleanup after the Notion import:

- move course pages from Courses/<course>/<course>.md to Courses/<course>.md
- move all learning-note pages with a course into Brainfood/
- move learning-note pages without a course into Brainfood No Courses/
- add course-page Dataview sections plus static fallback links
- rewrite relative Markdown links affected by the moves
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote


ROOT = Path(__file__).resolve().parents[3]
UCT = ROOT / "personal-brand" / "Learning" / "UCT - Student Dashboard"
COURSES = UCT / "Courses"
BRAINFOOD = UCT / "Brainfood"
BRAINFOOD_NO_COURSE = UCT / "Brainfood No Courses"
BASES = ROOT / "personal-brand" / "_obsidian" / "bases"
REPORT_ROOT = Path.home() / "Downloads" / "vault-generated" / "import-reports"
REPORT_DIR = REPORT_ROOT / "2026-05-11-uct-course-flatten"

LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
WIKI_RE = re.compile(r"(!?)\[\[([^\]|#]+)(#[^\]|]+)?(\|[^\]]+)?\]\]")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "obsidian://", "file://", "data:")
ID_SUFFIX_RE = re.compile(
    r"\s+(?:[0-9a-f]{32}|[0-9a-f]{4,}(?:-[0-9a-f]{4,}){1,})$",
    re.IGNORECASE,
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


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].splitlines()
    body = text[end + 5 :]
    data: dict[str, str] = {}
    for line in raw:
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        data[key.strip()] = value
    return data, body


def has_frontmatter(text: str) -> bool:
    return text.startswith("---\n") and "\n---\n" in text[4:]


def ensure_scalar_property(text: str, key: str, value: str) -> str:
    if not value:
        return text
    if not has_frontmatter(text):
        return f"---\n{key}: \"{value}\"\n---\n\n{text}"
    start = 4
    end = text.find("\n---\n", start)
    fm = text[start:end]
    body = text[end:]
    pattern = re.compile(rf"^{re.escape(key)}:\s*.*$", re.M)
    if pattern.search(fm):
        return text
    return f"---\n{fm.rstrip()}\n{key}: \"{value}\"\n{body}"


def ensure_learning_frontmatter(text: str, course: str | None) -> str:
    text = ensure_scalar_property(text, "type", "learning-note")
    if course:
        text = ensure_scalar_property(text, "course", course)
    return text


def split_link_target(target: str) -> tuple[str, str]:
    target = target.strip()
    if "#" in target:
        before, after = target.split("#", 1)
        return before, "#" + after
    return target, ""


def is_local_link(target: str) -> bool:
    lowered = target.lower().strip()
    return bool(lowered) and not lowered.startswith(SKIP_SCHEMES)


def unique_dest(path: Path, used: set[Path]) -> Path:
    candidate = path
    index = 2
    while candidate in used or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    used.add(candidate)
    return candidate


def note_type_and_course(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    props, _body = parse_frontmatter(text)
    return props.get("type", ""), props.get("course", "")


def course_from_course_subfolder(path: Path) -> str:
    try:
        relative = path.relative_to(COURSES)
    except ValueError:
        return ""
    return relative.parts[0] if len(relative.parts) >= 2 else ""


def build_manifest() -> list[dict[str, str]]:
    if not UCT.exists():
        raise SystemExit(f"Missing UCT dashboard folder: {UCT}")

    used: set[Path] = set()
    entries: list[dict[str, str]] = []
    for path in sorted(UCT.rglob("*.md")):
        typ, course = note_type_and_course(path)
        destination: Path | None = None
        reason = ""
        derived_course = ""
        in_brainfood = path.is_relative_to(BRAINFOOD)
        in_no_course = path.is_relative_to(BRAINFOOD_NO_COURSE)

        if typ == "course" and course_from_course_subfolder(path):
            destination = unique_dest(COURSES / path.name, used)
            reason = "flatten-course-page"
        elif typ == "learning-note" and course_from_course_subfolder(path) and not course:
            # Notes imported under a course folder without explicit course
            # metadata should still be treated as course-linked material.
            derived_course = course_from_course_subfolder(path)
            destination = unique_dest(BRAINFOOD / path.name, used)
            reason = "course-folder-note-promoted-to-learning-note"
        elif typ == "learning-note":
            if course:
                if not in_brainfood or path.parent != BRAINFOOD:
                    destination = unique_dest(BRAINFOOD / path.name, used)
                    reason = "coursed-learning-note-to-brainfood"
            elif in_brainfood and not in_no_course:
                destination = unique_dest(BRAINFOOD_NO_COURSE / path.name, used)
                reason = "uncoursed-learning-note-to-brainfood-no-courses"
            else:
                destination = None
                reason = ""
        elif course_from_course_subfolder(path):
            # Course subfolder notes such as Marks, Power Set, and exam notes are
            # useful course-linked learning material even if the import did not
            # tag them as learning-note.
            derived_course = course_from_course_subfolder(path)
            destination = unique_dest(BRAINFOOD / path.name, used)
            reason = "course-folder-note-promoted-to-learning-note"

        if destination and destination.resolve() != path.resolve():
            entries.append(
                {
                    "source": rel(path),
                    "destination": rel(destination),
                    "reason": reason,
                    "type": typ,
                    "course": course,
                    "derived_course": derived_course,
                }
            )
    return entries


def resolve_target(current_path: Path, target: str) -> Path | None:
    path_part, _fragment = split_link_target(target)
    if not is_local_link(path_part):
        return None
    decoded = unquote(path_part)
    if decoded.startswith("/"):
        candidate = (ROOT / decoded.lstrip("/")).resolve()
    else:
        candidate = (current_path.parent / decoded).resolve()
    candidates = [candidate]
    if candidate.suffix == "":
        candidates.append(candidate.with_suffix(".md"))
    for item in candidates:
        if item.exists():
            return item
    return candidate


def rewrite_links(text: str, file_path: Path, path_map: dict[Path, Path], stats: Counter[str]) -> str:
    safe = "/#%[]()'&,+-_."

    def replace_md(match: re.Match[str]) -> str:
        bang, label, target = match.groups()
        path_part, fragment = split_link_target(target)
        resolved = resolve_target(file_path, path_part)
        if not resolved:
            return match.group(0)
        mapped = path_map.get(resolved.resolve())
        if not mapped:
            return match.group(0)
        relative = Path(os.path.relpath(mapped, start=file_path.parent)).as_posix()
        stats["markdown_links_rewritten"] += 1
        return f"{bang}[{label}]({quote(relative, safe=safe)}{fragment})"

    def replace_wiki(match: re.Match[str]) -> str:
        bang, target, fragment, alias = match.groups()
        target_path = target.strip()
        if not target_path:
            return match.group(0)
        candidates = []
        if "/" in target_path:
            candidates.append((file_path.parent / target_path).resolve())
        candidates.append((ROOT / "personal-brand" / target_path).resolve())
        for candidate in list(candidates):
            if candidate.suffix == "":
                candidates.append(candidate.with_suffix(".md"))
        for candidate in candidates:
            mapped = path_map.get(candidate.resolve())
            if mapped:
                stats["wiki_links_rewritten"] += 1
                return f"{bang}[[{mapped.relative_to(ROOT).as_posix()}{fragment or ''}{alias or ''}]]"
        return match.group(0)

    text = LINK_RE.sub(replace_md, text)
    text = WIKI_RE.sub(replace_wiki, text)
    return text


def course_pages() -> list[Path]:
    pages = []
    for path in COURSES.glob("*.md"):
        typ, _course = note_type_and_course(path)
        if typ == "course":
            pages.append(path)
    return sorted(pages)


def fallback_links_for_course(course: str) -> list[str]:
    links = []
    for path in sorted(BRAINFOOD.glob("*.md")):
        typ, note_course = note_type_and_course(path)
        if typ == "learning-note" and note_course == course:
            links.append(f"- [[{path.relative_to(ROOT).as_posix()}|{path.stem}]]")
    return links


def inject_course_section(text: str, course: str) -> str:
    marker = "## Brainfood Notes"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n\n"
    fallback = "\n".join(fallback_links_for_course(course)) or "- No related Brainfood notes found."
    section = f"""## Brainfood Notes

```dataview
TABLE subject, topic, confidence, created
FROM "personal-brand/Learning/UCT - Student Dashboard/Brainfood"
WHERE type = "learning-note" AND course = this.course
SORT file.name ASC
```

### Current Links

{fallback}
"""
    return text.rstrip() + "\n\n" + section


def write_bases(dry_run: bool) -> Counter[str]:
    stats: Counter[str] = Counter()
    courses_base = BASES / "learning-courses.base"
    brainfood_base = BASES / "learning-brainfood.base"
    courses_content = """# personal-brand UCT Courses

filters:
  and:
    - file.inFolder("Learning/UCT - Student Dashboard/Courses")
    - 'type == "course"'

views:
  - type: table
    name: "Courses"
    order:
      - file.name
      - course
      - field
      - level
      - credits
"""
    brainfood_content = """# personal-brand UCT Brainfood

filters:
  and:
    - or:
        - file.inFolder("Learning/UCT - Student Dashboard/Brainfood")
        - file.inFolder("Learning/UCT - Student Dashboard/Brainfood No Courses")
    - 'type == "learning-note"'

views:
  - type: table
    name: "Brainfood"
    order:
      - file.name
      - course
      - subject
      - topic
      - confidence
      - created
      - file.folder
"""
    for path, content in [(courses_base, courses_content), (brainfood_base, brainfood_content)]:
        if not path.exists() or path.read_text(encoding="utf-8", errors="replace") != content:
            stats["bases_written"] += 1
            if not dry_run:
                path.write_text(content, encoding="utf-8")
    return stats


def apply_manifest(entries: list[dict[str, str]], dry_run: bool) -> Counter[str]:
    stats: Counter[str] = Counter()
    path_map = {((ROOT / e["source"]).resolve()): ((ROOT / e["destination"]).resolve()) for e in entries}
    if dry_run:
        for entry in entries:
            stats[entry["reason"]] += 1
        return stats

    for destination in [BRAINFOOD, BRAINFOOD_NO_COURSE, COURSES]:
        destination.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        source = ROOT / entry["source"]
        destination = ROOT / entry["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8", errors="replace")
        if entry["reason"] == "course-folder-note-promoted-to-learning-note":
            text = ensure_learning_frontmatter(text, entry["derived_course"])
        destination.write_text(text, encoding="utf-8")
        source.unlink()
        stats[entry["reason"]] += 1

    # Rewrite links in all UCT Markdown files after the moves exist on disk.
    for path in sorted(UCT.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rewritten = rewrite_links(text, path, path_map, stats)
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")
            stats["notes_with_links_rewritten"] += 1

    # Add the course page dynamic query plus static fallback list.
    for page in course_pages():
        _typ, course = note_type_and_course(page)
        text = page.read_text(encoding="utf-8", errors="replace")
        updated = inject_course_section(text, course or page.stem)
        if updated != text:
            page.write_text(updated, encoding="utf-8")
            stats["course_pages_updated"] += 1

    # Remove empty folders left by course/brainfood flattening.
    for directory, _dirs, _files in os.walk(UCT, topdown=False):
        path = Path(directory)
        if path in {UCT, COURSES, BRAINFOOD, BRAINFOOD_NO_COURSE}:
            continue
        try:
            path.rmdir()
            stats["empty_dirs_removed"] += 1
        except OSError:
            pass

    return stats


def write_report(entries: list[dict[str, str]], stats: Counter[str], dry_run: bool) -> None:
    if dry_run:
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "manifest.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# UCT Course Flatten Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Counts",
        "",
    ]
    for key, value in sorted(stats.items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    (REPORT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def verify() -> int:
    failures: list[str] = []
    if any(path.is_dir() for path in COURSES.iterdir()):
        failures.append("Courses contains subfolders")
    for path in COURSES.glob("*.md"):
        typ, _course = note_type_and_course(path)
        if typ != "course":
            failures.append(f"Non-course note in Courses root: {rel(path)}")
    for path in BRAINFOOD.rglob("*.md"):
        typ, course = note_type_and_course(path)
        if typ == "learning-note" and not course:
            failures.append(f"Uncoursed learning note in Brainfood: {rel(path)}")
    for path in BRAINFOOD_NO_COURSE.rglob("*.md"):
        typ, course = note_type_and_course(path)
        if typ == "learning-note" and course:
            failures.append(f"Coursed learning note in Brainfood No Courses: {rel(path)}")
    for path in course_pages():
        text = path.read_text(encoding="utf-8", errors="replace")
        if "## Brainfood Notes" not in text or "```dataview" not in text or "### Current Links" not in text:
            failures.append(f"Course page missing Brainfood section: {rel(path)}")
    id_paths = [path for path in UCT.rglob("*") if ID_SUFFIX_RE.search(path.stem)]
    if id_paths:
        failures.append(f"UCT paths with trailing Notion IDs: {len(id_paths)}")

    if failures:
        print("verification: failed")
        for failure in failures[:80]:
            print("-", failure)
        if len(failures) > 80:
            print(f"- ... {len(failures) - 80} more")
        return 1
    print("verification: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        return verify()
    dry_run = not args.apply
    entries = build_manifest()
    stats = apply_manifest(entries, dry_run)
    stats.update(write_bases(dry_run))
    write_report(entries, stats, dry_run)
    print("mode:", "dry-run" if dry_run else "apply")
    if not dry_run:
        print("report:", rel(REPORT_DIR))
    print("manifest entries:", len(entries))
    for key, value in sorted(stats.items()):
        print(f"{key}: {value}")
    if not dry_run:
        open_in_finder(REPORT_ROOT.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
