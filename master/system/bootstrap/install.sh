#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/MDerman/the-context-vault-template.git"
DEFAULT_TARGET_RELATIVE="Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault"

INSTALL_USER="$(id -un)"
if [[ "${EUID}" -eq 0 && -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
  INSTALL_USER="${SUDO_USER}"
fi

resolve_user_home() {
  local user="$1"
  local home_dir=""
  if command -v dscl >/dev/null 2>&1; then
    home_dir="$(dscl . -read "/Users/${user}" NFSHomeDirectory 2>/dev/null | awk '{print $2; exit}')"
  fi
  if [[ -z "${home_dir}" ]]; then
    home_dir="$(eval "printf '%s' ~${user}")"
  fi
  printf '%s' "${home_dir}"
}

run_as_install_user() {
  if [[ "${EUID}" -eq 0 && "${INSTALL_USER}" != "root" ]]; then
    sudo -u "${INSTALL_USER}" "$@"
  else
    "$@"
  fi
}

INSTALL_HOME="$(resolve_user_home "${INSTALL_USER}")"
if [[ -z "${INSTALL_HOME}" || ! -d "${INSTALL_HOME}" ]]; then
  echo "Could not resolve home directory for install user: ${INSTALL_USER}" >&2
  exit 1
fi

TARGET="${1:-${INSTALL_HOME}/${DEFAULT_TARGET_RELATIVE}}"
STATE_BASE="${INSTALL_HOME}/Library/Application Support/context-nine-vault-bootstrap"

if ! command -v brew >/dev/null 2>&1; then
  echo "Installing Homebrew..."
  run_as_install_user /bin/bash -c '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
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
  run_as_install_user "$(command -v brew)" install git
fi

GIT_BIN="$(command -v git)"

if [[ -e "${TARGET}" ]] && [[ ! -d "${TARGET}" ]]; then
  echo "Target path exists and is not a directory: ${TARGET}" >&2
  exit 1
fi

if [[ -d "${TARGET}" ]] && [[ -n "$(find "${TARGET}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "Target vault folder already exists and is not empty: ${TARGET}" >&2
  exit 1
fi

run_as_install_user mkdir -p "${TARGET}"

install_id="$(date -u +%Y%m%dT%H%M%SZ)-$(uuidgen | tr '[:upper:]' '[:lower:]')"
STATE_DIR="${STATE_BASE}/${install_id}"
UPSTREAM_GIT="${STATE_DIR}/upstream.git"

run_as_install_user mkdir -p "${STATE_DIR}"
run_as_install_user "${GIT_BIN}" clone --separate-git-dir "${UPSTREAM_GIT}" "${REPO_URL}" "${TARGET}"
installed_commit="$(run_as_install_user "${GIT_BIN}" --git-dir "${UPSTREAM_GIT}" --work-tree "${TARGET}" rev-parse HEAD)"
installed_version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/.vault-bootstrap/release.json" | head -1)"

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "${value}"
}

run_as_install_user mkdir -p "${TARGET}/.vault-bootstrap"
install_json="$(cat <<EOF
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
)"

printf '%s\n' "${install_json}" | run_as_install_user tee "${TARGET}/.vault-bootstrap/install.json" >/dev/null

run_as_install_user rm -f "${TARGET}/.git"
cd "${TARGET}"
run_as_install_user /bin/bash master/system/bootstrap/init_vault.sh --no-git
