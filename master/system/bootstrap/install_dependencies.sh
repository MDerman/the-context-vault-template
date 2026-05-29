#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: install_dependencies.sh [--dry-run]

Installs/checks local command-line dependencies for this vault bootstrap.

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

install_or_upgrade_formula() {
  local formula="$1"
  if brew list --formula "$formula" >/dev/null 2>&1; then
    echo "$formula already installed"
    run brew upgrade "$formula" || true
  else
    run brew install "$formula"
  fi
}

need_command_line_tools
need_homebrew

install_or_upgrade_formula git
install_or_upgrade_formula git-lfs
install_or_upgrade_formula python@3.12
install_or_upgrade_formula ripgrep

echo "Dependency check complete."
python3 --version || true
git --version || true
git lfs version || true
rg --version | head -1 || true
