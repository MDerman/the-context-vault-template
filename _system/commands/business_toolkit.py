#!/usr/bin/env python3
"""Create and safely synchronize the canonical business-context scaffold."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from script_utils import context_folder_metadata, discover_context_folders, resolve_vault_root


PACK_RELATIVE = Path("_system/bootstrap/templates/business-context")
MANIFEST_NAME = ".business-toolkit.json"
STATE_RELATIVE = Path("_obsidian/business-toolkit.json")
TEMPLATER_RELATIVE = Path(".obsidian/plugins/templater-obsidian/data.json")
ICONIZE_RELATIVES = (
    Path(".obsidian/plugins/obsidian-icon-folder/data.json"),
    Path(".obsidian-mobile/plugins/obsidian-icon-folder/data.json"),
)
STATE_SCHEMA_VERSION = 2
MANIFEST_SCHEMA_VERSION = 2
MANAGED_ICON = "📋"


@dataclass(frozen=True)
class Component:
    id: str
    group: str
    label: str
    folder: Path
    source: Path
    destination: Path


@dataclass
class SyncResult:
    changed: int = 0
    conflicts: list[str] = field(default_factory=list)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_relative(value: str, field_name: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SystemExit(f"Unsafe {field_name} path in business toolkit manifest: {value!r}")
    return path


def load_pack(root: Path) -> tuple[int, list[Component]]:
    pack_root = root / PACK_RELATIVE
    data = load_json(pack_root / MANIFEST_NAME, None)
    if not isinstance(data, dict):
        raise SystemExit(f"Missing or invalid business toolkit manifest: {pack_root / MANIFEST_NAME}")
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise SystemExit(f"Unsupported business toolkit manifest schema: {data.get('schema_version')!r}")
    pack_version = data.get("pack_version")
    if not isinstance(pack_version, int) or pack_version < 1:
        raise SystemExit("Business toolkit pack_version must be a positive integer.")
    components: list[Component] = []
    seen: set[str] = set()
    for raw in data.get("components", []):
        if not isinstance(raw, dict):
            raise SystemExit("Business toolkit components must be JSON objects.")
        component_id = str(raw.get("id", "")).strip()
        if not component_id or component_id in seen:
            raise SystemExit(f"Missing or duplicate business toolkit component id: {component_id!r}")
        seen.add(component_id)
        component = Component(
            id=component_id,
            group=str(raw.get("group", "")).strip(),
            label=str(raw.get("label", component_id)).strip(),
            folder=safe_relative(str(raw.get("folder", "")), "folder"),
            source=safe_relative(str(raw.get("source", "")), "source"),
            destination=safe_relative(str(raw.get("destination", "")), "destination"),
        )
        if not component.group or not (pack_root / component.source).is_file():
            raise SystemExit(f"Invalid or missing canonical template for {component_id}")
        components.append(component)
    if not components:
        raise SystemExit("Business toolkit manifest contains no components.")
    return pack_version, components


def install_scaffold(root: Path, context: str, *, apply: bool) -> int:
    """Copy the complete ordinary scaffold into a newly created context only."""
    source_root = root / PACK_RELATIVE
    target_root = root / context
    changed = 0
    for source in sorted(source_root.rglob("*")):
        relative = source.relative_to(source_root)
        if relative == Path(MANIFEST_NAME) or relative == Path("_obsidian/templates/business-toolkit") or Path("_obsidian/templates/business-toolkit") in relative.parents:
            continue
        target = target_root / relative
        if source.is_dir():
            if not target.exists():
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


def business_contexts(root: Path) -> list[str]:
    return [
        name for name in discover_context_folders(root)
        if (context_folder_metadata(root / name).get("context_type") or "business").strip().lower() == "business"
    ]


def validate_context(root: Path, context: str) -> None:
    if context not in business_contexts(root):
        raise SystemExit(f"Not a registered business context folder: {context}")


def parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def select_components(components: list[Component], *, saved: list[str] | None, includes: list[str], excludes: list[str]) -> list[Component]:
    known = {item.id for item in components} | {item.group for item in components}
    unknown = sorted((set(includes) | set(excludes)) - known)
    if unknown:
        raise SystemExit(f"Unknown business toolkit component/group: {', '.join(unknown)}")
    if includes:
        selected = [item for item in components if item.id in includes or item.group in includes]
    elif saved is not None:
        selected = [item for item in components if item.id in set(saved)]
    else:
        selected = components[:]
    return [item for item in selected if item.id not in excludes and item.group not in excludes]


def state_path(root: Path, context: str) -> Path:
    return root / context / STATE_RELATIVE


def load_state(root: Path, context: str) -> dict[str, Any]:
    data = load_json(state_path(root, context), {})
    return data if isinstance(data, dict) else {}


def templater_rule(context: str, component: Component) -> dict[str, str]:
    return {"folder": f"{context}/{component.folder.as_posix()}", "template": f"{context}/{component.destination.as_posix()}"}


def selection(root: Path, context: str, components: list[Component], includes: list[str], excludes: list[str], use_saved: bool) -> tuple[dict[str, Any], list[Component]]:
    old_state = load_state(root, context)
    saved = old_state.get("components") if use_saved and not includes and not excludes else None
    if saved is not None and not isinstance(saved, list):
        saved = None
    return old_state, select_components(components, saved=saved, includes=includes, excludes=excludes)


def context_conflicts(root: Path, context: str, components: list[Component], selected: list[Component], old_state: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []
    selected_ids = {item.id for item in selected}
    by_id = {item.id: item for item in components}
    installed = old_state.get("installed", {}) if isinstance(old_state.get("installed", {}), dict) else {}
    old_icons = old_state.get("icons", {}) if isinstance(old_state.get("icons", {}), dict) else {}
    context_root = root / context
    for component in selected:
        destination = context_root / component.destination
        previous_hash = installed.get(component.destination.as_posix())
        source_hash = sha256_file(root / PACK_RELATIVE / component.source)
        if destination.exists() and not destination.is_file():
            conflicts.append(f"{context}: template destination is not a file: {component.destination}")
        elif destination.is_file():
            current_hash = sha256_file(destination)
            if current_hash != source_hash and (not previous_hash or current_hash != previous_hash):
                conflicts.append(f"{context}: local template differs: {component.destination}")
    for previous_id in old_state.get("components", []):
        component = by_id.get(previous_id)
        if not component or previous_id in selected_ids:
            continue
        destination = context_root / component.destination
        previous_hash = installed.get(component.destination.as_posix())
        if destination.exists() and (not destination.is_file() or not previous_hash or sha256_file(destination) != previous_hash):
            conflicts.append(f"{context}: locally changed excluded template: {component.destination}")
    desired_folders = {item.folder.as_posix() for item in selected if (context_root / item.folder).is_dir()}
    managed_folders = {item.folder.as_posix() for item in components}
    for relative in ICONIZE_RELATIVES:
        path = root / relative
        if not path.is_file():
            continue
        data = load_json(path, {})
        if not isinstance(data, dict):
            raise SystemExit(f"Invalid Iconize configuration: {path}")
        for folder in managed_folders:
            key = f"{context}/{folder}"
            current = data.get(key)
            previous = old_icons.get(folder)
            if folder in desired_folders:
                if current is not None and current != MANAGED_ICON and current != previous:
                    conflicts.append(f"{context}: changed managed icon in {relative}: {folder} ({current})")
            elif previous is not None and current is not None and current != previous:
                conflicts.append(f"{context}: changed excluded managed icon in {relative}: {folder} ({current})")
    return conflicts


def reconcile_templater_rules(root: Path, context: str, components: list[Component], selected: list[Component], *, apply: bool) -> bool:
    path = root / TEMPLATER_RELATIVE
    data = load_json(path, {})
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid Templater configuration: {path}")
    rules = data.get("folder_templates", [])
    ignored = data.get("ignore_folders_on_creation", [])
    if not isinstance(rules, list) or not isinstance(ignored, list):
        raise SystemExit(f"Invalid Templater folder configuration: {path}")
    managed = {f"{context}/{item.folder.as_posix()}" for item in components}
    replacement_rules = [templater_rule(context, item) for item in selected]
    desired_rules: list[Any] = []
    inserted = False
    for item in rules:
        if isinstance(item, dict) and item.get("folder") in managed:
            if not inserted:
                desired_rules.extend(replacement_rules)
                inserted = True
            continue
        desired_rules.append(item)
    if not inserted:
        desired_rules.extend(replacement_rules)
    template_root = f"{context}/_obsidian/templates/business-toolkit"
    desired_ignored: list[Any] = []
    inserted = False
    for item in ignored:
        if isinstance(item, dict) and item.get("folder") == template_root:
            if selected and not inserted:
                desired_ignored.append({"folder": template_root})
                inserted = True
            continue
        desired_ignored.append(item)
    if selected and not inserted:
        desired_ignored.append({"folder": template_root})
    if desired_rules == rules and desired_ignored == ignored:
        return False
    print(f"{'write' if apply else '[dry-run] write'} {path.relative_to(root)}")
    if apply:
        data["enable_folder_templates"] = True
        data["folder_templates"] = desired_rules
        data["ignore_folders_on_creation"] = desired_ignored
        write_json(path, data)
    return True


def reconcile_icons(root: Path, context: str, components: list[Component], selected: list[Component], old_state: dict[str, Any], *, apply: bool, force: bool) -> tuple[int, dict[str, str]]:
    selected_folders = {item.folder.as_posix() for item in selected if (root / context / item.folder).is_dir()}
    managed_folders = {item.folder.as_posix() for item in components}
    old_icons = old_state.get("icons", {}) if isinstance(old_state.get("icons", {}), dict) else {}
    changed = 0
    for relative in ICONIZE_RELATIVES:
        path = root / relative
        if not path.is_file():
            continue
        data = load_json(path, {})
        desired = dict(data)
        for folder in managed_folders:
            key = f"{context}/{folder}"
            current = desired.get(key)
            previous = old_icons.get(folder)
            if folder in selected_folders:
                if force or current is None or current == previous or current == MANAGED_ICON:
                    desired[key] = MANAGED_ICON
            elif current is not None and previous is not None and (force or current == previous):
                desired.pop(key, None)
        if desired != data:
            print(f"{'write' if apply else '[dry-run] write'} {path.relative_to(root)}")
            if apply:
                write_json(path, desired)
            changed += 1
    return changed, {folder: MANAGED_ICON for folder in sorted(selected_folders)}


def sync_context(root: Path, context: str, *, includes: list[str] | None = None, excludes: list[str] | None = None, apply: bool, force: bool = False, use_saved: bool = True, validate_business: bool = True) -> SyncResult:
    if validate_business:
        validate_context(root, context)
    pack_version, components = load_pack(root)
    old_state, selected = selection(root, context, components, includes or [], excludes or [], use_saved)
    conflicts = context_conflicts(root, context, components, selected, old_state)
    if conflicts and not force:
        return SyncResult(conflicts=conflicts)
    result = SyncResult()
    if reconcile_templater_rules(root, context, components, selected, apply=apply):
        result.changed += 1
    context_root = root / context
    selected_ids = {item.id for item in selected}
    by_id = {item.id: item for item in components}
    installed = old_state.get("installed", {}) if isinstance(old_state.get("installed", {}), dict) else {}
    next_installed: dict[str, str] = {}
    pending: list[tuple[Path, bytes]] = []
    templater_data = load_json(root / TEMPLATER_RELATIVE, {})
    trigger = bool(isinstance(templater_data, dict) and templater_data.get("trigger_on_file_creation"))
    for previous_id in old_state.get("components", []):
        component = by_id.get(previous_id)
        if not component or previous_id in selected_ids:
            continue
        destination = context_root / component.destination
        previous_hash = installed.get(component.destination.as_posix())
        if destination.is_file() and previous_hash and (force or sha256_file(destination) == previous_hash):
            print(f"{'remove' if apply else '[dry-run] remove'} {destination.relative_to(root)}")
            if apply:
                destination.unlink()
            result.changed += 1
    for component in selected:
        source = root / PACK_RELATIVE / component.source
        source_bytes = source.read_bytes()
        source_hash = sha256_bytes(source_bytes)
        destination = context_root / component.destination
        should_write = not destination.is_file() or sha256_file(destination) != source_hash
        if should_write:
            print(f"{'write' if apply else '[dry-run] write'} {destination.relative_to(root)}")
            if apply:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists() and trigger:
                    destination.write_text("<!-- business-toolkit installation in progress -->\n", encoding="utf-8")
                    pending.append((destination, source_bytes))
                else:
                    destination.write_bytes(source_bytes)
            result.changed += 1
        next_installed[component.destination.as_posix()] = source_hash
    if pending:
        time.sleep(0.5)
        for destination, source_bytes in pending:
            destination.write_bytes(source_bytes)
    icon_changes, next_icons = reconcile_icons(root, context, components, selected, old_state, apply=apply, force=force)
    result.changed += icon_changes
    next_state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "pack_version": pack_version,
        "components": [item.id for item in selected],
        "installed": next_installed,
        "icons": next_icons,
    }
    if next_state != old_state:
        path = state_path(root, context)
        print(f"{'write' if apply else '[dry-run] write'} {path.relative_to(root)}")
        if apply:
            write_json(path, next_state)
        result.changed += 1
    return result


def selected_contexts(root: Path, args: argparse.Namespace) -> list[str]:
    if getattr(args, "all_business", False):
        return business_contexts(root)
    if getattr(args, "configured", False):
        return [name for name in business_contexts(root) if state_path(root, name).is_file()]
    result = parse_csv(getattr(args, "context_folders", None))
    for context in result:
        validate_context(root, context)
    return result


def preflight(root: Path, contexts: list[str], includes: list[str], excludes: list[str], use_saved: bool) -> list[str]:
    _version, components = load_pack(root)
    conflicts: list[str] = []
    for context in contexts:
        old_state, selected = selection(root, context, components, includes, excludes, use_saved)
        conflicts.extend(context_conflicts(root, context, components, selected, old_state))
    return conflicts


def report_conflicts(conflicts: list[str]) -> None:
    if not conflicts:
        return
    print("Business toolkit conflicts:", file=sys.stderr)
    for conflict in conflicts:
        print(f"  - {conflict}", file=sys.stderr)


def run_sync(root: Path, contexts: list[str], *, includes: list[str], excludes: list[str], apply: bool, force: bool, use_saved: bool, allow_prompt: bool) -> int:
    conflicts = preflight(root, contexts, includes, excludes, use_saved)
    if conflicts and not force:
        report_conflicts(conflicts)
        if not apply:
            return 1
        if not allow_prompt or not sys.stdin.isatty():
            print("No changes were made. Rerun with --force to overwrite all conflicts.", file=sys.stderr)
            return 1
        if input("Overwrite all listed template and icon conflicts? [y/N]: ").strip().lower() not in {"y", "yes"}:
            print("Cancelled; no changes were made.")
            return 1
        force = True
    if not apply:
        for context in contexts:
            sync_context(root, context, includes=includes, excludes=excludes, apply=False, force=force, use_saved=use_saved)
        return 0
    for context in contexts:
        result = sync_context(root, context, includes=includes, excludes=excludes, apply=True, force=force, use_saved=use_saved)
        if result.conflicts:
            raise SystemExit("Business toolkit changed during apply; stopped before this context was mutated.")
    return 0


def status_context(root: Path, context: str) -> bool:
    pack_version, components = load_pack(root)
    state = load_state(root, context)
    saved = state.get("components", []) if isinstance(state.get("components", []), list) else []
    selected = [item for item in components if item.id in set(saved)]
    issues = [] if state else ["not configured"]
    if state and state.get("pack_version") != pack_version:
        issues.append(f"pack version {state.get('pack_version')} -> {pack_version}")
    issues.extend(context_conflicts(root, context, components, selected, state))
    rules_data = load_json(root / TEMPLATER_RELATIVE, {})
    pairs = {(item.get("folder"), item.get("template")) for item in rules_data.get("folder_templates", []) if isinstance(item, dict)} if isinstance(rules_data, dict) else set()
    installed = state.get("installed", {}) if isinstance(state.get("installed", {}), dict) else {}
    for component in selected:
        destination = root / context / component.destination
        if not destination.is_file():
            issues.append(f"missing {component.destination}")
        elif installed.get(component.destination.as_posix()) and sha256_file(destination) != installed[component.destination.as_posix()]:
            issues.append(f"locally changed {component.destination}")
        rule = templater_rule(context, component)
        if (rule["folder"], rule["template"]) not in pairs:
            issues.append(f"missing Templater rule for {component.folder}")
        if (root / context / component.folder).is_dir():
            icon_key = f"{context}/{component.folder.as_posix()}"
            for relative in ICONIZE_RELATIVES:
                icon_path = root / relative
                if icon_path.is_file() and load_json(icon_path, {}).get(icon_key) != MANAGED_ICON:
                    issues.append(f"missing Iconize marker in {relative} for {component.folder}")
    if issues:
        print(f"{context}: needs attention")
        for issue in dict.fromkeys(issues):
            print(f"  - {issue}")
        return False
    print(f"{context}: current ({len(selected)} components, pack {pack_version})")
    return True


def add_target_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--context-folders")
    group.add_argument("--all-business", action="store_true")
    group.add_argument("--configured", action="store_true")
    parser.add_argument("--root", default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install and synchronize the business-context toolkit.")
    subparsers = parser.add_subparsers(dest="command")
    sync = subparsers.add_parser("sync")
    add_target_args(sync)
    sync.add_argument("--include")
    sync.add_argument("--exclude")
    sync.add_argument("--apply", action="store_true")
    sync.add_argument("--force", action="store_true")
    status = subparsers.add_parser("status")
    add_target_args(status)
    return parser


def wizard(root: Path) -> int:
    contexts = business_contexts(root)
    if not contexts:
        print("No registered business context folders found.", file=sys.stderr)
        return 2
    _version, components = load_pack(root)
    print("Business Toolkit\n")
    for index, context in enumerate(contexts, 1):
        print(f"  {index}. {context}")
    answer = input("\nSelect contexts by number or name, comma-separated [all]: ").strip()
    selected: list[str] = []
    if not answer or answer.lower() == "all":
        selected = contexts
    else:
        for token in parse_csv(answer):
            name = contexts[int(token) - 1] if token.isdigit() and 1 <= int(token) <= len(contexts) else token
            validate_context(root, name)
            if name not in selected:
                selected.append(name)
    print("\nAvailable groups: " + ", ".join(sorted({item.group for item in components})))
    excludes = parse_csv(input("Exclude groups/components [none]: ").strip())
    conflicts = preflight(root, selected, [], excludes, False)
    if conflicts:
        report_conflicts(conflicts)
        prompt = "Apply and overwrite all listed conflicts? [y/N]: "
        force = True
    else:
        prompt = "Apply these changes? [y/N]: "
        force = False
    if input(prompt).strip().lower() not in {"y", "yes"}:
        print("Cancelled; no changes were made.")
        return 0
    return run_sync(root, selected, includes=[], excludes=excludes, apply=True, force=force, use_saved=False, allow_prompt=False)


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        root = resolve_vault_root(None, __file__)
        if not sys.stdin.isatty():
            print("Interactive wizard requires a terminal; use `vault business-toolkit sync ...`.", file=sys.stderr)
            return 2
        return wizard(root)
    parser = build_parser()
    args = parser.parse_args(args_list)
    if not args.command:
        parser.print_help()
        return 2
    root = resolve_vault_root(args.root, __file__)
    contexts = selected_contexts(root, args)
    if not contexts:
        parser.error("select --context-folders, --all-business, or --configured")
    if args.command == "status":
        return 0 if all(status_context(root, context) for context in contexts) else 1
    includes, excludes = parse_csv(args.include), parse_csv(args.exclude)
    return run_sync(root, contexts, includes=includes, excludes=excludes, apply=args.apply, force=args.force, use_saved=not includes and not excludes, allow_prompt=True)


if __name__ == "__main__":
    raise SystemExit(main())
