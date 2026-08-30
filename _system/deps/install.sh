#!/usr/bin/env bash
set -euo pipefail

DEPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  if [[ "$(uname -s)" != "Darwin" ]] || ! command -v brew >/dev/null 2>&1; then
    echo "Python 3 is required to read the structured Vault dependency manifest." >&2
    exit 1
  fi
  if [[ " ${*} " == *" --dry-run "* ]]; then
    echo "DRY RUN: brew install python@3.12"
    exit 0
  fi
  brew install python@3.12
fi
exec python3 "${DEPS_DIR}/install.py" "$@"
