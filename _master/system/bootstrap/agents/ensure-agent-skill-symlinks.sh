#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vault_root="$(cd "$script_dir/../../../.." && pwd)"

exec python3 "$vault_root/_master/agents/sync_skills.py" sync --root "$vault_root" "$@"
