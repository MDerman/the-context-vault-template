#!/usr/bin/env python3
"""Create, register, or rename context folders in the root Obsidian vault."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

from script_utils import context_folder_note_path, resolve_vault_root
from context_folder_rename import rename_context_folder, validate_slug
from business_toolkit import (
    install_scaffold as install_business_scaffold,
    sync_context as sync_business_toolkit,
)


VALID_STATUSES = {"active", "archived", "none"}
VALID_FOLDER_TEMPLATES = {"business", "personal-brand"}
FEATURE_DIRECTORIES = {
    "blog": (
        "_obsidian/content/items/blog-posts",
        "_obsidian/content/publications/blogs",
    ),
    "social-content": (
        "_obsidian/content/items/social-posts",
        "_obsidian/content/items/youtube-videos",
        "_obsidian/content/publications/youtube",
        "_obsidian/content/ideas",
        "_obsidian/content/archive",
    ),
    "newsletters": (
        "_obsidian/content/items/newsletter-issues",
        "_obsidian/content/publications/newsletters",
    ),
}


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line.startswith("  "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def read_status(path: Path) -> str:
    if not path.exists():
        return ""
    return parse_frontmatter(path.read_text(encoding="utf-8")).get("status", "").strip().lower()


def read_content_schedules_enabled(path: Path) -> bool:
    if not path.exists():
        return False
    value = parse_frontmatter(path.read_text(encoding="utf-8")).get("content_schedules_enabled", "")
    return value.strip().lower() in {"true", "yes", "1"}


def detect_context_features(context_root: Path) -> set[str]:
    return {
        feature
        for feature, directories in FEATURE_DIRECTORIES.items()
        if any((context_root / directory).is_dir() for directory in directories)
    }


def has_content_structure(context_root: Path) -> bool:
    """Return whether filesystem-inferred content capabilities exist."""
    return bool(detect_context_features(context_root))


def read_context_registered(path: Path) -> bool:
    if not path.exists():
        return True
    value = parse_frontmatter(path.read_text(encoding="utf-8")).get("context_registered", "true")
    return value.strip().lower() not in {"false", "no", "0"}


def set_frontmatter_value(path: Path, key: str, value: str, dry_run: bool) -> None:
    if not path.exists():
        raise SystemExit(f"Missing context folder note: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        rendered = f"---\n{key}: {value}\n---\n{text}"
    else:
        end = text.find("\n---", 4)
        if end == -1:
            rendered = f"---\n{key}: {value}\n---\n{text}"
        else:
            body_start = end + len("\n---")
            body = text[body_start + 1 :] if body_start < len(text) and text[body_start] == "\n" else text[body_start:]
            lines = text[4:end].splitlines()
            out: list[str] = []
            seen = False
            for line in lines:
                if ":" in line and not line.startswith(" "):
                    existing_key = line.split(":", 1)[0].strip()
                    if existing_key == key:
                        out.append(f"{key}: {value}")
                        seen = True
                        continue
                out.append(line)
            if not seen:
                out.append(f"{key}: {value}")
            rendered = "---\n" + "\n".join(out) + "\n---\n" + body
    if dry_run:
        print(f"[dry-run] set {key}: {value} in {path}")
    else:
        path.write_text(rendered, encoding="utf-8")


def write_context_folder_note(path: Path, status: str, content_schedules_enabled: bool) -> None:
    value = "" if status == "none" else status
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            end = text.find("\n---", 4)
            if end != -1:
                body_start = end + len("\n---")
                body = text[body_start + 1 :] if body_start < len(text) and text[body_start] == "\n" else text[body_start:]
                lines = text[4:end].splitlines()
                out: list[str] = []
                seen: set[str] = set()
                for line in lines:
                    if ":" in line and not line.startswith(" "):
                        key = line.split(":", 1)[0].strip()
                        if key == "status":
                            out.append(f"status: {value}")
                            seen.add(key)
                            continue
                        if key in {"content_enabled", "context_type", "content_schedules_enabled"}:
                            if key == "content_schedules_enabled" and content_schedules_enabled:
                                out.append("content_schedules_enabled: true")
                                seen.add(key)
                            continue
                        if key == "context_registered":
                            out.append("context_registered: true")
                            seen.add(key)
                            continue
                    out.append(line)
                if "status" not in seen:
                    out.append(f"status: {value}")
                if content_schedules_enabled and "content_schedules_enabled" not in seen:
                    out.append("content_schedules_enabled: true")
                if "context_registered" not in seen:
                    out.append("context_registered: true")
                path.write_text("---\n" + "\n".join(out) + "\n---\n" + body, encoding="utf-8")
                return
    schedules = "content_schedules_enabled: true\n" if content_schedules_enabled else ""
    path.write_text(f"---\nstatus: {value}\n{schedules}context_registered: true\n---\n", encoding="utf-8")


def install_personal_brand_template(root: Path, context: str, *, apply: bool) -> int:
    source_root = root / "_system/bootstrap/templates/context-folders/personal-brand"
    if not source_root.is_dir():
        raise SystemExit(f"Missing personal-brand folder template: {source_root}")
    target_root = root / context
    changed = 0
    for source in sorted(source_root.rglob("*")):
        target = target_root / source.relative_to(source_root)
        if source.is_dir():
            if target.exists():
                continue
            print(f"{'mkdir' if apply else '[dry-run] mkdir'} {target.relative_to(root)}")
            if apply:
                target.mkdir(parents=True, exist_ok=True)
            changed += 1
        elif not target.exists():
            print(f"{'copy' if apply else '[dry-run] copy'} {target.relative_to(root)}")
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            changed += 1
    return changed


def discover_entities(root: Path, excluded: set[str] | None = None) -> list[str]:
    excluded = excluded or set()
    entities = []
    for path in sorted(root.iterdir()):
        if path.name in excluded:
            continue
        if not path.is_dir() or path.name.startswith("."):
            continue
        if path.name.startswith("_"):
            continue
        note = context_folder_note_path(path)
        if note.exists() and read_context_registered(note):
            entities.append(path.name)
    return entities


def load_bootstrap(root: Path):
    path = root / "_system/bootstrap/bootstrap_vault.py"
    if not path.exists():
        raise SystemExit(f"Missing bootstrap script: {path}")
    spec = importlib.util.spec_from_file_location("bootstrap_vault", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rename_main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Rename a context folder and rewrite structured references.")
    parser.add_argument("old_slug", help="Existing context folder slug.")
    parser.add_argument("new_slug", help="New context folder slug.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    rename_context_folder(root, args.old_slug, args.new_slug, args.dry_run)


def parse_create_args(argv: list[str], *, register_mode: bool) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or register a context folder in the root vault workspace.")
    if register_mode:
        parser.add_argument("name", nargs="?", help="Existing shared context folder name.")
        parser.add_argument("-n", "--name", dest="name_flag", help="Existing shared context folder name.")
    else:
        parser.add_argument("-n", "--name", required=True, help="Context folder name, for example new-context-folder.")
    parser.add_argument(
        "-s",
        "--status",
        required=not register_mode,
        choices=sorted(VALID_STATUSES),
        help="Context folder status. Register mode defaults to folder-note status, then active.",
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--default-context-folder", dest="default_entity", metavar="CONTEXT_FOLDER", default=None, help="Default capture context folder. Defaults to current root TaskNotes setting or personal.")
    parser.add_argument("--default-sub-vault", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--default-entity", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--blog", action="store_true", help="Create blog item and publication folders.")
    parser.add_argument("--social-content", action="store_true", help="Create social, YouTube, ideas, and archive folders.")
    parser.add_argument("--newsletters", action="store_true", help="Create newsletter item and publication folders.")
    parser.add_argument("--content-schedules", action="store_true", help="Enable cadence and schedule generation for this context folder.")
    parser.add_argument("--folder-template", choices=sorted(VALID_FOLDER_TEMPLATES), help="Apply one physical folder pack when creating a new context folder.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if register_mode:
        args.name = args.name_flag or args.name
        if not args.name:
            parser.error("register requires a context folder name")
        if args.folder_template:
            parser.error("--folder-template is creation-only; register the folder first, then manage its physical folders directly")
    return args


def create_main(argv: list[str], *, register_mode: bool = False) -> None:
    args = parse_create_args(argv, register_mode=register_mode)

    root = resolve_vault_root(args.root, __file__)
    name = validate_slug(args.name, "context folder name")

    entity_root = root / name
    if entity_root.exists() and not entity_root.is_dir():
        raise SystemExit(f"Context folder path exists and is not a directory: {entity_root}")

    entity_note = context_folder_note_path(entity_root)
    is_new_context = not entity_root.exists() and not entity_note.exists()
    if args.folder_template and not is_new_context:
        raise SystemExit("--folder-template is only supported when creating a new context folder")
    existing_status = read_status(entity_note)
    status = args.status or existing_status or "active"
    content_schedules_enabled = read_content_schedules_enabled(entity_note) or args.content_schedules

    if args.dry_run:
        print(f"[dry-run] write {entity_note}")
    else:
        write_context_folder_note(entity_note, status, content_schedules_enabled)

    if args.folder_template == "business":
        install_business_scaffold(root, name, apply=not args.dry_run)
    elif args.folder_template == "personal-brand":
        install_personal_brand_template(root, name, apply=not args.dry_run)

    bootstrap_module = load_bootstrap(root)
    entities = discover_entities(root)
    if name not in entities:
        entities.append(name)
        entities.sort()

    active_entities = [
        entity
        for entity in entities
        if read_status(context_folder_note_path(root / entity)) == "active"
    ]
    if status == "active" and name not in active_entities:
        active_entities.append(name)
        active_entities.sort()
    context_features = {entity: detect_context_features(root / entity) for entity in entities}
    selected_features = {
        feature
        for feature, enabled in {
            "blog": args.blog,
            "social-content": args.social_content,
            "newsletters": args.newsletters,
        }.items()
        if enabled
    }
    context_features.setdefault(name, set()).update(selected_features)
    content_schedule_entities = [
        entity for entity in entities
        if read_content_schedules_enabled(context_folder_note_path(root / entity))
    ]
    if content_schedules_enabled and name not in content_schedule_entities:
        content_schedule_entities.append(name)
        content_schedule_entities.sort()

    default_entity = args.default_entity or "personal"
    tasknotes = root / ".obsidian/plugins/tasknotes/data.json"
    if args.default_entity is None and tasknotes.exists():
        import json

        data = json.loads(tasknotes.read_text(encoding="utf-8"))
        default_entity = data.get("taskCreationDefaults", {}).get("defaultContexts") or default_entity

    if default_entity not in entities:
        raise SystemExit(f"default context folder {default_entity!r} is not in configured context folders: {entities}")

    bootstrap = bootstrap_module.Bootstrap(
        root=root,
        entities=entities,
        active_entities=active_entities,
        default_entity=default_entity,
        context_features=context_features,
        content_schedule_entities=content_schedule_entities,
        install_vault_command_enabled=True,
        dry_run=args.dry_run,
        run_date=bootstrap_module.parse_date(None),
    )
    bootstrap.run()
    if args.folder_template == "business":
        sync_business_toolkit(
            root,
            name,
            apply=not args.dry_run,
            use_saved=False,
        )


def default_context_folder(root: Path, entities: list[str]) -> str:
    default_entity = "personal"
    tasknotes = root / ".obsidian/plugins/tasknotes/data.json"
    if tasknotes.exists():
        import json

        data = json.loads(tasknotes.read_text(encoding="utf-8"))
        default_entity = data.get("taskCreationDefaults", {}).get("defaultContexts") or default_entity
    if default_entity in entities:
        return default_entity
    if "personal" in entities:
        return "personal"
    if entities:
        return entities[0]
    raise SystemExit("No registered context folders remain.")


def rerun_bootstrap(root: Path, dry_run: bool, excluded: set[str] | None = None) -> None:
    bootstrap_module = load_bootstrap(root)
    entities = discover_entities(root, excluded=excluded)
    active_entities = [
        entity
        for entity in entities
        if read_status(context_folder_note_path(root / entity)) == "active"
    ]
    context_features = {entity: detect_context_features(root / entity) for entity in entities}
    content_schedule_entities = [
        entity for entity in entities
        if read_content_schedules_enabled(context_folder_note_path(root / entity))
    ]
    bootstrap = bootstrap_module.Bootstrap(
        root=root,
        entities=entities,
        active_entities=active_entities,
        default_entity=default_context_folder(root, entities),
        context_features=context_features,
        content_schedule_entities=content_schedule_entities,
        install_vault_command_enabled=True,
        dry_run=dry_run,
        run_date=bootstrap_module.parse_date(None),
    )
    bootstrap.run()


def unregister_main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Unregister a context folder while keeping its files.")
    parser.add_argument("name", help="Context folder slug.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    name = validate_slug(args.name, "context folder name")
    context_root = root / name
    note = context_folder_note_path(context_root)
    if not context_root.is_dir() or not note.exists():
        raise SystemExit(f"Context folder not found: {name}")
    set_frontmatter_value(note, "context_registered", "false", args.dry_run)
    rerun_bootstrap(root, args.dry_run, excluded={name} if args.dry_run else None)


def remove_main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Remove a context folder from disk and regenerate vault views.")
    parser.add_argument("name", help="Context folder slug.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--apply", action="store_true", help="Compatibility flag; `vault folder remove` already applies by default.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without deleting files.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    name = validate_slug(args.name, "context folder name")
    context_root = root / name
    if not context_root.exists():
        raise SystemExit(f"Context folder not found: {name}")
    if not context_root.is_dir() or context_root.is_symlink():
        raise SystemExit(f"Context folder path is not a normal directory: {context_root}")

    dry_run = args.dry_run or not args.apply
    if dry_run:
        print(f"[dry-run] remove {context_root}")
    else:
        shutil.rmtree(context_root)
        print(f"removed {context_root}")
    rerun_bootstrap(root, dry_run, excluded={name} if dry_run else None)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    removed = [flag for flag in ("--context-type", "--content-enabled") if flag in args]
    if removed:
        replacements = "--blog, --social-content, --newsletters, --content-schedules, and --folder-template"
        raise SystemExit(f"{', '.join(removed)} has been removed; use the independent capability flags instead: {replacements}")
    if args and args[0] == "rename":
        rename_main(args[1:])
        return
    if args and args[0] == "unregister":
        unregister_main(args[1:])
        return
    if args and args[0] in {"remove", "delete"}:
        remove_main(args[1:])
        return
    register_mode = bool(args and args[0] == "register")
    if args and args[0] in {"create", "register"}:
        args = args[1:]
    create_main(args, register_mode=register_mode)


if __name__ == "__main__":
    main()
