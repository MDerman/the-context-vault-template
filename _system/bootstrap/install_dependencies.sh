#!/usr/bin/env bash
set -euo pipefail

# Bootstrap owns sequencing only. Dependency intent and installation live in
# _system/deps so the same contract works outside this bootstrap directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/../deps/install.sh" "$@"
