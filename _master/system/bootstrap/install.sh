#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/MDerman/the-context-vault-template.git"
DEFAULT_TARGET_RELATIVE="Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault"
BOOTSTRAP_STATE_RELATIVE="_master/system/bootstrap/state"

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

resolve_target_path() {
  local target="$1"
  if [[ "${target}" == "~" ]]; then
    target="${INSTALL_HOME}"
  elif [[ "${target}" == "~/"* ]]; then
    target="${INSTALL_HOME}/${target:2}"
  elif [[ "${target}" =~ ^~([^/]+)(/.*)?$ ]]; then
    local target_user="${BASH_REMATCH[1]}"
    local suffix="${BASH_REMATCH[2]:-}"
    local target_home=""
    target_home="$(resolve_user_home "${target_user}")"
    if [[ -z "${target_home}" || "${target_home}" == "~${target_user}" || ! -d "${target_home}" ]]; then
      echo "Could not resolve home directory for target path user: ${target_user}" >&2
      exit 1
    fi
    target="${target_home}${suffix}"
  fi

  if [[ "${target}" != /* ]]; then
    target="$(pwd -P)/${target}"
  fi

  printf '%s' "${target}"
}

INSTALL_HOME="$(resolve_user_home "${INSTALL_USER}")"
if [[ -z "${INSTALL_HOME}" || ! -d "${INSTALL_HOME}" ]]; then
  echo "Could not resolve home directory for install user: ${INSTALL_USER}" >&2
  exit 1
fi

TARGET="$(resolve_target_path "${1:-${INSTALL_HOME}/${DEFAULT_TARGET_RELATIVE}}")"
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
installed_version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/${BOOTSTRAP_STATE_RELATIVE}/release.json" | head -1)"
installed_tag="$(sed -n 's/.*"tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/${BOOTSTRAP_STATE_RELATIVE}/release.json" | head -1)"
dependency_lock_sha256="$(sed -n 's/.*"dependency_lock_sha256"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/${BOOTSTRAP_STATE_RELATIVE}/release.json" | head -1)"

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "${value}"
}

run_as_install_user mkdir -p "${TARGET}/${BOOTSTRAP_STATE_RELATIVE}"
install_json="$(cat <<EOF
{
  "schema_version": 1,
  "repo_url": "$(json_escape "${REPO_URL}")",
  "install_id": "$(json_escape "${install_id}")",
  "state_dir": "$(json_escape "${STATE_DIR}")",
  "upstream_git_dir": "$(json_escape "${UPSTREAM_GIT}")",
  "installed_commit": "$(json_escape "${installed_commit}")",
  "installed_version": "$(json_escape "${installed_version:-unknown}")",
  "installed_tag": "$(json_escape "${installed_tag:-unknown}")",
  "dependency_lock_sha256": "$(json_escape "${dependency_lock_sha256:-unknown}")"
}
EOF
)"

printf '%s\n' "${install_json}" | run_as_install_user tee "${TARGET}/${BOOTSTRAP_STATE_RELATIVE}/install.json" >/dev/null

run_as_install_user rm -f "${TARGET}/.git"
run_as_install_user rm -rf "${TARGET}/.vault-bootstrap" "${TARGET}/.vault-upgrade"
run_as_install_user rm -f "${TARGET}/.bootstrap-export-manifest.json"
cd "${TARGET}"
run_as_install_user /bin/bash _master/system/bootstrap/init_vault.sh

PYTHON_BIN="$(command -v python3)"
if [[ "$(uname -s)" == "Darwin" ]]; then
  if run_as_install_user "${PYTHON_BIN}" "${TARGET}/_master/system/scripts/refresh_schedule.py" --root "${TARGET}" register; then
    echo "Registered daily vault refresh schedule."
  else
    echo "Warning: Could not register daily vault refresh schedule." >&2
    echo "Run manually later: vault refresh-schedule register" >&2
  fi
else
  echo "Daily vault refresh schedule skipped: requires macOS launchd."
fi

if [[ "${EUID}" -eq 0 ]]; then
  mkdir -p /usr/local/bin
  "${PYTHON_BIN}" "${TARGET}/_master/system/bootstrap/install_vault_command.py" \
    --root "${TARGET}" \
    --bin-dir /usr/local/bin \
    --force \
    --no-shell-path
  echo "Installed global vault command: /usr/local/bin/vault"
else
  echo "Global vault command skipped because installer is not running as root."
fi

echo ""
echo "Install complete."
echo "Vault: ${TARGET}"
if ! run_as_install_user "${PYTHON_BIN}" "${TARGET}/_master/system/bootstrap/print_post_install_next_steps.py" --root "${TARGET}"; then
  echo "Warning: Could not print optional post-install next steps." >&2
fi
