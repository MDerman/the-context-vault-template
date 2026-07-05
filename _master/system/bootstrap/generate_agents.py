#!/usr/bin/env python3
"""Generate root AGENTS.md from discovered context folders."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from script_utils import context_folder_note_path  # noqa: E402


MARKER = "managed-by: _master/system/bootstrap/generate_agents.py"
OLD_MARKERS = (
    "managed-by: _master/system/bootstrap/bootstrap_vault.py",
    "managed-by: _master/system/bootstrap/setup/bootstrap_vault.py",
    "managed-by: _master/bootstrap/setup/bootstrap_vault.py",
)
TEMPLATE_PATH = Path("_master/system/bootstrap/AGENTS.template.md")
AGENTS_PATH = Path("AGENTS.md")


@dataclass(frozen=True)
class ContextFolder:
    name: str
    status: str
    context_type: str
    content_enabled: bool
    default_capture: bool


def simple_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    data: dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line or raw_line.startswith(" "):
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        if value.lower() == "true":
            data[key.strip()] = True
        elif value.lower() == "false":
            data[key.strip()] = False
        else:
            data[key.strip()] = value
    return data


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "1", "on"}


def discover_context_folders(root: Path) -> list[ContextFolder]:
    contexts: list[ContextFolder] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name.startswith("_"):
            continue
        note = context_folder_note_path(child)
        if not note.exists():
            continue
        metadata = simple_frontmatter(note.read_text(encoding="utf-8", errors="replace"))
        if not (metadata.get("status") or metadata.get("context_type")):
            continue
        contexts.append(
            ContextFolder(
                name=child.name,
                status=str(metadata.get("status") or "none").strip().lower(),
                context_type=str(metadata.get("context_type") or "business").strip().lower(),
                content_enabled=bool_value(metadata.get("content_enabled")),
                default_capture=bool_value(metadata.get("default_capture")),
            )
        )
    if not contexts:
        raise SystemExit("No context folders found. Run bootstrap_vault.py first.")
    return contexts


def inline_code_list(items: list[str]) -> str:
    if not items:
        return "None"
    return ", ".join(f"`{item}`" for item in items)


def shell_paths(paths: list[str]) -> str:
    if not paths:
        return shlex.quote(".")
    return " ".join(shlex.quote(path) for path in paths)


def default_context(contexts: list[ContextFolder]) -> str:
    marked = [context.name for context in contexts if context.default_capture]
    if marked:
        return marked[0]
    active = [context.name for context in contexts if context.status == "active"]
    if active:
        return active[0]
    return contexts[0].name


def sample_task_context(root: Path, contexts: list[ContextFolder], default: str) -> str:
    active = [context.name for context in contexts if context.status == "active" and context.name != default]
    candidates = [default, *active, *[context.name for context in contexts if context.name not in {default, *active}]]
    for context in candidates:
        if (root / context / "_obsidian/tasks/starter-task.md").exists():
            return context
    return default


def first_task_path(root: Path, context: str) -> str:
    starter = root / context / "_obsidian/tasks/starter-task.md"
    if starter.exists():
        return starter.relative_to(root).as_posix()
    task_dir = root / context / "_obsidian/tasks"
    if task_dir.exists():
        for path in sorted(task_dir.glob("*.md")):
            return path.relative_to(root).as_posix()
    return f"{context}/_obsidian/tasks/starter-task.md"


def render(root: Path, generated_at: str) -> str:
    template_path = root / TEMPLATE_PATH
    if not template_path.exists():
        raise SystemExit(f"Missing AGENTS template: {template_path}")
    contexts = discover_context_folders(root)
    configured = [context.name for context in contexts]
    active = [context.name for context in contexts if context.status == "active"]
    archived = [context.name for context in contexts if context.status != "active"]
    content = [context.name for context in contexts if context.content_enabled]
    default = default_context(contexts)
    sample_context = sample_task_context(root, contexts, default)
    active_or_default = active or [default]
    active_task_dirs = [f"{context}/_obsidian/tasks" for context in active_or_default]
    content_item_dirs = [f"{context}/_obsidian/content/items" for context in content]
    if content_item_dirs:
        content_status_query = (
            "rg -l '^status: (idea|cogs-are-turning|draft|planning-scripting|scheduled)$' "
            f"{shell_paths(content_item_dirs)} 2>/dev/null | head -50"
        )
        content_enabled_note = f"Content storage is enabled for: {inline_code_list(content)}."
    else:
        content_status_query = "# No content-enabled context folders yet."
        content_enabled_note = "No context folder has content storage enabled yet."

    replacements = {
        "{{generated_at}}": generated_at,
        "{{managed_marker}}": MARKER,
        "{{active_context_folders}}": inline_code_list(active),
        "{{archived_context_folders}}": inline_code_list(archived),
        "{{configured_context_folders}}": inline_code_list(configured),
        "{{content_enabled_context_folders}}": inline_code_list(content),
        "{{default_context_folder}}": default,
        "{{sample_task_path}}": first_task_path(root, sample_context),
        "{{sample_task_dir}}": shlex.quote(f"{sample_context}/_obsidian/tasks"),
        "{{active_task_dirs}}": shell_paths(active_task_dirs),
        "{{content_status_query}}": content_status_query,
        "{{content_enabled_note}}": content_enabled_note,
    }
    text = template_path.read_text(encoding="utf-8")
    for needle, value in replacements.items():
        text = text.replace(needle, value)
    unresolved = sorted(set(re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", text)))
    if unresolved:
        raise SystemExit(f"Unresolved AGENTS template placeholders: {', '.join(unresolved)}")
    return text.rstrip() + "\n"


def can_replace_agents(path: Path) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    return MARKER in text or any(marker in text for marker in OLD_MARKERS)


def write_agents(root: Path, content: str, dry_run: bool) -> None:
    path = root / AGENTS_PATH
    if path.exists() and path.read_text(encoding="utf-8", errors="replace") == content:
        return
    if not can_replace_agents(path):
        raise SystemExit(f"Refusing to overwrite non-managed {path}")
    if dry_run:
        print(f"[dry-run] write {path}")
        return
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def ensure_symlink(root: Path, link: Path, target: str, dry_run: bool, directory: bool = False) -> None:
    path = root / link
    if path.is_symlink():
        if str(path.readlink()) == target:
            return
        if dry_run:
            print(f"[dry-run] replace symlink {path} -> {target}")
            return
        path.unlink()
    elif path.exists():
        if path.is_file() and can_replace_agents(path):
            if dry_run:
                print(f"[dry-run] remove managed file {path}")
                print(f"[dry-run] symlink {path} -> {target}")
                return
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            if dry_run:
                print(f"[dry-run] remove empty directory {path}")
                print(f"[dry-run] symlink {path} -> {target}")
                return
            path.rmdir()
        else:
            raise SystemExit(f"Refusing to replace existing non-symlink path: {path}")
    else:
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"[dry-run] symlink {path} -> {target}")
        return
    path.symlink_to(target, target_is_directory=directory)
    print(f"symlink {path} -> {target}")


def ensure_real_directory(root: Path, directory: Path, dry_run: bool) -> None:
    path = root / directory
    if path.is_symlink():
        if dry_run:
            print(f"[dry-run] remove legacy symlink {path}")
            print(f"[dry-run] mkdir {path}")
            return
        path.unlink()
        print(f"removed legacy symlink {path}")
    elif path.exists() and not path.is_dir():
        raise SystemExit(f"Refusing to replace existing non-directory path: {path}")
    elif path.exists():
        return

    if dry_run:
        print(f"[dry-run] mkdir {path}")
        return
    path.mkdir(parents=True, exist_ok=True)
    print(f"mkdir {path}")


def ensure_agent_paths(root: Path, dry_run: bool) -> None:
    skills_source = root / "_master/agents/skills"
    for directory in [
        root / "_master/agents/skills",
        root / "_master/agents/skill-packs",
        root / "_master/agents/skills/manual",
        root / "_master/agents/skills-dump",
        root / ".agents",
        root / ".claude",
    ]:
        if directory.exists():
            continue
        if dry_run:
            print(f"[dry-run] mkdir {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"mkdir {directory}")
    if not skills_source.exists() and not dry_run:
        skills_source.mkdir(parents=True, exist_ok=True)

    ensure_symlink(root, Path("CLAUDE.md"), "AGENTS.md", dry_run)
    ensure_real_directory(root, Path(".agents/skills"), dry_run)
    ensure_symlink(root, Path(".claude/skills"), "../.agents/skills", dry_run, directory=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate root AGENTS.md and agent paths.")
    parser.add_argument("--root", default=".", help="Vault root.")
    parser.add_argument("--date", default=None, help="Generated timestamp override.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    generated_at = args.date or dt.datetime.now().isoformat(timespec="seconds")
    content = render(root, generated_at)
    write_agents(root, content, args.dry_run)
    ensure_agent_paths(root, args.dry_run)


if __name__ == "__main__":
    main()
