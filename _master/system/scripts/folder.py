#!/usr/bin/env python3
"""Create, register, or rename context folders in the master Obsidian workspace."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from script_utils import resolve_vault_root
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


def write_home(path: Path, status: str, context_type: str, content_enabled: bool) -> None:
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
                    out.append(line)
                if "status" not in seen:
                    out.append(f"status: {value}")
                if "context_type" not in seen:
                    out.append(f"context_type: {context_type}")
                if "content_enabled" not in seen:
                    out.append(f"content_enabled: {content_value}")
                path.write_text("---\n" + "\n".join(out) + "\n---\n" + body, encoding="utf-8")
                return
    path.write_text(f"---\nstatus: {value}\ncontext_type: {context_type}\ncontent_enabled: {content_value}\n---\n", encoding="utf-8")


def discover_entities(root: Path) -> list[str]:
    entities = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if path.name.startswith("_"):
            continue
        if (path / "HOME.md").exists():
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
        help="Context folder status. Register mode defaults to HOME.md status, then active.",
    )
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery from the current directory or script location.")
    parser.add_argument("--default-context-folder", dest="default_entity", metavar="CONTEXT_FOLDER", default=None, help="Default capture context folder. Defaults to current root TaskNotes setting or personal.")
    parser.add_argument("--default-sub-vault", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--default-entity", dest="default_entity", help=argparse.SUPPRESS)
    parser.add_argument("--content-enabled", action="store_true", default=None if register_mode else False, help="Create/register this context folder with content_enabled: true.")
    parser.add_argument("--context-type", choices=sorted(VALID_CONTEXT_TYPES), default=None if register_mode else "business", help="Context folder type. Register mode defaults to HOME.md context_type, then business.")
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

    existing_status = read_status(entity_root / "HOME.md")
    existing_context_type = read_context_type(entity_root / "HOME.md")
    existing_content_enabled = read_content_enabled(entity_root / "HOME.md")
    status = args.status or existing_status or "active"
    context_type = args.context_type or existing_context_type or "business"
    content_enabled = args.content_enabled if args.content_enabled is not None else existing_content_enabled

    if args.dry_run:
        print(f"[dry-run] write {entity_root / 'HOME.md'}")
    else:
        write_home(entity_root / "HOME.md", status, context_type, content_enabled)

    bootstrap_module = load_bootstrap(root)
    entities = discover_entities(root)
    if name not in entities:
        entities.append(name)
        entities.sort()

    active_entities = [
        entity
        for entity in entities
        if read_status(root / entity / "HOME.md") == "active"
    ]
    if status == "active" and name not in active_entities:
        active_entities.append(name)
        active_entities.sort()
    content_entities = [
        entity
        for entity in entities
        if read_content_enabled(root / entity / "HOME.md")
    ]
    if content_enabled and name not in content_entities:
        content_entities.append(name)
        content_entities.sort()
    context_types = {
        entity: read_context_type(root / entity / "HOME.md")
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


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "rename":
        rename_main(args[1:])
        return
    register_mode = bool(args and args[0] == "register")
    if args and args[0] in {"create", "register"}:
        args = args[1:]
    create_main(args, register_mode=register_mode)


if __name__ == "__main__":
    main()
