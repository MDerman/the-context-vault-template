#!/usr/bin/env python3
"""Compatibility CLI for the shared Vault agent-path reconciler."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def load_shared(root: Path):
    agents = root / "_system/agents"
    if str(agents) not in sys.path:
        sys.path.insert(0, str(agents))
    import global_agent_configuration

    return global_agent_configuration


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ensure root agent symlinks and local skill folders.")
    parser.add_argument("--root", default=".", help="Vault root.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    report = load_shared(root).ensure_agent_paths(root, dry_run=args.dry_run)
    for item in report["results"]:
        if item["status"] != "match":
            prefix = "[dry-run] " if args.dry_run else ""
            print(f"{prefix}{item['detail']}: {item['path']}")


if __name__ == "__main__":
    main()
