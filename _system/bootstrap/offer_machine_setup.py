#!/usr/bin/env python3
"""Offer the optional additional-machine wizard after primary Vault bootstrap."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Callable, TextIO


Runner = Callable[[list[str]], int]


def default_runner(command: list[str]) -> int:
    return subprocess.run(command).returncode


def offer_machine_setup(
    *,
    vault_command: str,
    input_stream: TextIO,
    output_stream: TextIO,
    non_interactive: bool,
    dry_run: bool,
    runner: Runner = default_runner,
) -> int:
    if non_interactive:
        print("Additional-machine setup skipped in non-interactive mode.", file=output_stream)
        print("Run `vault machine setup` later.", file=output_stream)
        return 0
    print("", file=output_stream)
    print("Do you want to prepare an additional machine now? [y/N] ", end="", file=output_stream)
    output_stream.flush()
    answer = input_stream.readline()
    if not answer or answer.strip().casefold() not in {"y", "yes"}:
        print("Run `vault machine setup` later if you want to add a worker.", file=output_stream)
        return 0
    command = [vault_command, "machine", "setup"]
    if dry_run:
        print("DRY RUN: " + " ".join(command), file=output_stream)
        return 0
    return runner(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-command", default="vault")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return offer_machine_setup(
        vault_command=str(Path(args.vault_command).expanduser()),
        input_stream=sys.stdin,
        output_stream=sys.stdout,
        non_interactive=args.non_interactive,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
