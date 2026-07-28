#!/usr/bin/env python3
"""Print public install next steps from config."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_RELATIVE_CONFIG = "_system/bootstrap/post-install-next-steps.json"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config root must be object")
    return data


def print_steps(config: dict[str, Any], *, vault_root: Path) -> None:
    title = str(config.get("title") or "Optional next steps")
    steps = config.get("steps") or []
    if not isinstance(steps, list):
        raise ValueError("steps must be list")

    print("")
    print("=" * 72)
    print(title)
    print("=" * 72)
    print("")

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        step_title = str(step.get("title") or f"Step {index}")
        description = str(step.get("description") or "")
        url = str(step.get("url") or "")
        commands = step.get("commands") or []

        print(f"{index}. {step_title}")
        if description:
            print(f"   {description}")
        if url:
            print(f"   Link: {url}")
        if commands:
            print("   Commands:")
            for command in commands:
                print(f"     {command}")
        print("")

    print(f"Vault: {vault_root}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Installed vault root.")
    parser.add_argument("--config", default=DEFAULT_RELATIVE_CONFIG, help="Config path, relative to root unless absolute.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = root / config_path

    try:
      config = load_config(config_path)
      print_steps(config, vault_root=root)
    except Exception as exc:
      print(f"Warning: could not print post-install next steps: {exc}", file=sys.stderr)
      return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
