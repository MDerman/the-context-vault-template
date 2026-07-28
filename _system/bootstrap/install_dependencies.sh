#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    sudo_home=""
    if command -v dscl >/dev/null 2>&1; then
      sudo_home="$(dscl . -read "/Users/${SUDO_USER}" NFSHomeDirectory 2>/dev/null | awk '{print $2; exit}' || true)"
    fi
    if [[ -z "${sudo_home}" ]]; then
      sudo_home="$(eval "printf '%s' ~${SUDO_USER}")"
    fi
    exec sudo -u "${SUDO_USER}" env HOME="${sudo_home}" /bin/bash "$0" "$@"
  fi
  echo "Do not run install_dependencies.sh as root. Run it as your user, or use sudo from your user so it can drop privileges." >&2
  exit 1
fi

DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: install_dependencies.sh [--dry-run]

Installs/checks local command-line dependencies for this vault bootstrap from
_system/bootstrap/Brewfile.

Requires Homebrew. If Homebrew is missing, install it with:
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
EOF
}

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY RUN:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

ensure_gh_skill() {
  if ! command -v gh >/dev/null 2>&1; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "DRY RUN: gh will be installed from Brewfile and checked for gh skill support."
      return 0
    fi
    echo "GitHub CLI missing after brew bundle install." >&2
    exit 1
  fi

  if gh skill --help >/dev/null 2>&1; then
    return 0
  fi

  echo "GitHub CLI found, but gh skill is unavailable. Upgrading gh with Homebrew..."
  run brew upgrade gh

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY RUN: gh skill availability will be checked after applying dependency changes."
    return 0
  fi

  if ! gh skill --help >/dev/null 2>&1; then
    echo "gh skill still unavailable after upgrading gh. Install GitHub CLI 2.90.0 or newer." >&2
    gh --version >&2 || true
    exit 1
  fi
}

need_command_line_tools() {
  if ! xcode-select --print-path >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Xcode Command Line Tools missing.
Install with:
  xcode-select --install
Then rerun this script.
EOF
    exit 1
  fi
}

need_homebrew() {
  if ! command -v brew >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Homebrew missing.
Install Homebrew with:
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
Then rerun this script.
EOF
    exit 1
  fi
}

need_command_line_tools
need_homebrew

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BREWFILE="${SCRIPT_DIR}/Brewfile"

if [[ ! -f "${BREWFILE}" ]]; then
  echo "Missing Brewfile: ${BREWFILE}" >&2
  exit 1
fi

run brew bundle install --file "${BREWFILE}"
ensure_gh_skill

echo "Dependency check complete."
python3 --version || true
git --version || true
git lfs version || true
if command -v gh >/dev/null 2>&1; then
  gh --version || true
  if gh skill --help >/dev/null 2>&1; then
    echo "gh skill available"
  fi
fi
jq --version || true
rg --version | head -1 || true
rclone version | head -1 || true
if command -v gws >/dev/null 2>&1; then
  gws --version || true
fi
if [[ -d /Library/Filesystems/macfuse.fs ]]; then
  echo "macFUSE installed"
fi
