#!/usr/bin/env python3
"""Compatibility entrypoint for the shared global agent reconciler."""

from __future__ import annotations

from pathlib import Path
import sys


AGENTS_DIRECTORY = Path(__file__).resolve().parents[4]
if str(AGENTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIRECTORY))

from global_agent_configuration import main, reconcile_payload as reconcile


if __name__ == "__main__":
    raise SystemExit(main())
