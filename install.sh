#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/MDerman/the-context-vault-template.git"
TARGET="${1:-${HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault}"
STATE_BASE="${HOME}/Library/Application Support/context-nine-vault-bootstrap"

if ! command -v brew >/dev/null 2>&1; then
  echo "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew install finished, but brew is not on PATH. Open a new terminal and rerun this script." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  brew install git
fi

if [[ -e "${TARGET}" ]] && [[ ! -d "${TARGET}" ]]; then
  echo "Target path exists and is not a directory: ${TARGET}" >&2
  exit 1
fi

if [[ -d "${TARGET}" ]] && [[ -n "$(find "${TARGET}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "Target vault folder already exists and is not empty: ${TARGET}" >&2
  exit 1
fi

mkdir -p "${TARGET}"

install_id="$(date -u +%Y%m%dT%H%M%SZ)-$(uuidgen | tr '[:upper:]' '[:lower:]')"
STATE_DIR="${STATE_BASE}/${install_id}"
UPSTREAM_GIT="${STATE_DIR}/upstream.git"

mkdir -p "${STATE_DIR}"
git clone --separate-git-dir "${UPSTREAM_GIT}" "${REPO_URL}" "${TARGET}"
installed_commit="$(git --git-dir "${UPSTREAM_GIT}" --work-tree "${TARGET}" rev-parse HEAD)"
installed_version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/.vault-bootstrap/release.json" | head -1)"

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "${value}"
}

mkdir -p "${TARGET}/.vault-bootstrap"
cat > "${TARGET}/.vault-bootstrap/install.json" <<EOF
{
  "schema_version": 1,
  "repo_url": "$(json_escape "${REPO_URL}")",
  "install_id": "$(json_escape "${install_id}")",
  "state_dir": "$(json_escape "${STATE_DIR}")",
  "upstream_git_dir": "$(json_escape "${UPSTREAM_GIT}")",
  "installed_commit": "$(json_escape "${installed_commit}")",
  "installed_version": "$(json_escape "${installed_version:-unknown}")"
}
EOF

rm -f "${TARGET}/.git"
cd "${TARGET}"
master/system/bootstrap/init_vault.sh --no-git
