#!/usr/bin/env python3
"""Create, register, or rename context folders in the master Obsidian workspace."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

from script_utils import context_folder_note_path, resolve_vault_root
from context_folder_rename import rename_context_folder, validate_slug


VALID_STATUSES = {"active", "archived", "none"}
VALID_CONTEXT_TYPES = {"personal", "personal-brand", "business"}


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


def read_content_enabled(path: Path) -> bool:
    if not path.exists():
        return False
    value = parse_frontmatter(path.read_text(encoding="utf-8")).get("content_enabled", "")
    return value.strip().lower() in {"true", "yes", "1"}


def read_context_type(path: Path) -> str:
    if not path.exists():
        return "business"
    value = parse_frontmatter(path.read_text(encoding="utf-8")).get("context_type", "")
    return value.strip().lower() or "business"


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


def write_context_folder_note(path: Path, status: str, context_type: str, content_enabled: bool) -> None:
    value = "" if status == "none" else status
    content_value = "true" if content_enabled else "false"
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
                        if key == "content_enabled":
                            out.append(f"content_enabled: {content_value}")
                            seen.add(key)
                            continue
                        if key == "context_type":
                            out.append(f"context_type: {context_type}")
                            seen.add(key)
                            continue
                        if key == "context_registered":
                            out.append("context_registered: true")
                            seen.add(key)
                            continue
                    out.append(line)
                if "status" not in seen:
                    out.append(f"status: {value}")
                if "context_type" not in seen:
                    out.append(f"context_type: {context_type}")
                if "content_enabled" not in seen:
                    out.append(f"content_enabled: {content_value}")
                if "context_registered" not in seen:
                    out.append("context_registered: true")
                path.write_text("---\n" + "\n".join(out) + "\n---\n" + body, encoding="utf-8")
                return
    path.write_text(f"---\nstatus: {value}\ncontext_type: {context_type}\ncontent_enabled: {content_value}\ncontext_registered: true\n---\n", encoding="utf-8")


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


def discover_coding_agents(root: Path) -> list[str]:
    agents = []
    if (root / ".agents").exists() or (root / "AGENTS.md").exists():
        agents.append("codex")
    if (root / ".claude").exists() or (root / "CLAUDE.md").exists():
        agents.append("claude")
    return agents or ["codex"]


def load_bootstrap(root: Path):
    path = root / "_master/system/bootstrap/bootstrap_vault.py"
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
    parser = argparse.ArgumentParser(description="Create or register a context folder in the master workspace.")
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
    parser.add_argument("--content-enabled", action="store_true", default=None if register_mode else False, help="Create/register this context folder with content_enabled: true.")
    parser.add_argument("--context-type", choices=sorted(VALID_CONTEXT_TYPES), default=None if register_mode else "business", help="Context folder type. Register mode defaults to folder-note context_type, then business.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if register_mode:
        args.name = args.name_flag or args.name
        if not args.name:
            parser.error("register requires a context folder name")
    return args


def create_main(argv: list[str], *, register_mode: bool = False) -> None:
    args = parse_create_args(argv, register_mode=register_mode)

    root = resolve_vault_root(args.root, __file__)
    name = validate_slug(args.name, "context folder name")

    entity_root = root / name
    if entity_root.exists() and not entity_root.is_dir():
        raise SystemExit(f"Context folder path exists and is not a directory: {entity_root}")

    entity_note = context_folder_note_path(entity_root)
    existing_status = read_status(entity_note)
    existing_context_type = read_context_type(entity_note)
    existing_content_enabled = read_content_enabled(entity_note)
    status = args.status or existing_status or "active"
    context_type = args.context_type or existing_context_type or "business"
    content_enabled = args.content_enabled if args.content_enabled is not None else existing_content_enabled

    if args.dry_run:
        print(f"[dry-run] write {entity_note}")
    else:
        write_context_folder_note(entity_note, status, context_type, content_enabled)

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
    content_entities = [
        entity
        for entity in entities
        if read_content_enabled(context_folder_note_path(root / entity))
    ]
    if content_enabled and name not in content_entities:
        content_entities.append(name)
        content_entities.sort()
    context_types = {
        entity: read_context_type(context_folder_note_path(root / entity))
        for entity in entities
    }
    context_types[name] = context_type

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
        context_types=context_types,
        coding_agents=discover_coding_agents(root),
        content_entities=content_entities,
        install_vault_command_enabled=True,
        generate_agents_enabled=True,
        dry_run=args.dry_run,
        run_date=bootstrap_module.parse_date(None),
    )
    bootstrap.run()


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
    content_entities = [
        entity
        for entity in entities
        if read_content_enabled(context_folder_note_path(root / entity))
    ]
    context_types = {
        entity: read_context_type(context_folder_note_path(root / entity))
        for entity in entities
    }
    bootstrap = bootstrap_module.Bootstrap(
        root=root,
        entities=entities,
        active_entities=active_entities,
        default_entity=default_context_folder(root, entities),
        context_types=context_types,
        coding_agents=discover_coding_agents(root),
        content_entities=content_entities,
        install_vault_command_enabled=True,
        generate_agents_enabled=True,
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
    parser = argparse.ArgumentParser(description="Remove a context folder from disk and regenerate vault context wiring.")
    parser.add_argument("name", help="Context folder slug.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--apply", action="store_true", help="Actually delete the folder. Without this, only prints planned changes.")
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
