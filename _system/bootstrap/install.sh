#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/MDerman/the-context-vault-template.git"
DEFAULT_TARGET_RELATIVE="Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault"
RELEASE_METADATA_RELATIVE="_system/bootstrap/release.json"
INSTALL_STATE_RELATIVE="_system/local/state/install.json"

TARGET_ARGUMENT=""
AGENT_PACKAGE_SOURCE="${CTX9_AGENT_PACKAGE_SOURCE:-}"
AGENT_GLOBAL_INSTRUCTIONS=0
AGENT_CLAUDE_ALIAS=0
AGENT_DISCOVERY_ALIASES=0
NON_INTERACTIVE=0
INSTALL_LAUNCH_DIR="$(pwd -P)"

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --agent-package-source)
      AGENT_PACKAGE_SOURCE="${2:?--agent-package-source requires a URL or path}"
      shift 2
      ;;
    --agent-global-instructions)
      AGENT_GLOBAL_INSTRUCTIONS=1
      shift
      ;;
    --agent-claude-alias)
      AGENT_CLAUDE_ALIAS=1
      shift
      ;;
    --agent-discovery-aliases)
      AGENT_DISCOVERY_ALIASES=1
      shift
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
      shift
      ;;
    --*)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
    *)
      if [[ -n "${TARGET_ARGUMENT}" ]]; then
        echo "Only one Vault target path may be supplied." >&2
        exit 2
      fi
      TARGET_ARGUMENT="$1"
      shift
      ;;
  esac
done

if [[ -z "${AGENT_PACKAGE_SOURCE}" ]] && (( AGENT_GLOBAL_INSTRUCTIONS || AGENT_CLAUDE_ALIAS || AGENT_DISCOVERY_ALIASES )); then
  echo "Agent instruction and alias flags require --agent-package-source." >&2
  exit 2
fi
if (( AGENT_CLAUDE_ALIAS && ! AGENT_GLOBAL_INSTRUCTIONS )); then
  echo "--agent-claude-alias requires --agent-global-instructions." >&2
  exit 2
fi

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
    target="${INSTALL_LAUNCH_DIR}/${target}"
  fi

  printf '%s' "${target}"
}

INSTALL_HOME="$(resolve_user_home "${INSTALL_USER}")"
if [[ -z "${INSTALL_HOME}" || ! -d "${INSTALL_HOME}" ]]; then
  echo "Could not resolve home directory for install user: ${INSTALL_USER}" >&2
  exit 1
fi

TARGET="$(resolve_target_path "${TARGET_ARGUMENT:-${INSTALL_HOME}/${DEFAULT_TARGET_RELATIVE}}")"
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
installed_version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/${RELEASE_METADATA_RELATIVE}" | head -1)"
installed_tag="$(sed -n 's/.*"tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/${RELEASE_METADATA_RELATIVE}" | head -1)"
dependency_lock_sha256="$(sed -n 's/.*"dependency_lock_sha256"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/${RELEASE_METADATA_RELATIVE}" | head -1)"

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "${value}"
}

run_as_install_user mkdir -p "$(dirname "${TARGET}/${INSTALL_STATE_RELATIVE}")"
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

printf '%s\n' "${install_json}" | run_as_install_user tee "${TARGET}/${INSTALL_STATE_RELATIVE}" >/dev/null

run_as_install_user rm -f "${TARGET}/.git"
cd "${TARGET}"
run_as_install_user /bin/bash _system/bootstrap/init_vault.sh --enable-git

prompt_agent_package() {
  if [[ "${NON_INTERACTIVE}" -eq 1 || -n "${AGENT_PACKAGE_SOURCE}" || ! -r /dev/tty ]]; then
    return
  fi
  local answer=""
  printf 'Install the optional standalone agent package now? [y/N] ' >/dev/tty
  IFS= read -r answer </dev/tty || answer=""
  case "${answer}" in
    y|Y|yes|YES)
      printf 'Agent package repository URL or local export path: ' >/dev/tty
      IFS= read -r AGENT_PACKAGE_SOURCE </dev/tty || AGENT_PACKAGE_SOURCE=""
      if [[ -n "${AGENT_PACKAGE_SOURCE}" ]]; then
        printf 'Generate managed global Codex instructions? [y/N] ' >/dev/tty
        IFS= read -r answer </dev/tty || answer=""
        [[ "${answer}" =~ ^([yY]|yes|YES)$ ]] && AGENT_GLOBAL_INSTRUCTIONS=1
        if [[ "${AGENT_GLOBAL_INSTRUCTIONS}" -eq 1 ]]; then
          printf 'Create the managed Claude instruction alias? [y/N] ' >/dev/tty
          IFS= read -r answer </dev/tty || answer=""
          [[ "${answer}" =~ ^([yY]|yes|YES)$ ]] && AGENT_CLAUDE_ALIAS=1
        fi
        printf 'Create managed skill discovery aliases? [y/N] ' >/dev/tty
        IFS= read -r answer </dev/tty || answer=""
        [[ "${answer}" =~ ^([yY]|yes|YES)$ ]] && AGENT_DISCOVERY_ALIASES=1
      fi
      ;;
  esac
}

install_optional_agent_package() {
  prompt_agent_package
  if [[ -z "${AGENT_PACKAGE_SOURCE}" ]]; then
    return
  fi
  local package_dir="${AGENT_PACKAGE_SOURCE}"
  if [[ "${AGENT_PACKAGE_SOURCE}" == http://* || "${AGENT_PACKAGE_SOURCE}" == https://* || "${AGENT_PACKAGE_SOURCE}" == git@* ]]; then
    package_dir="${STATE_DIR}/agent-package-source"
    if ! run_as_install_user "${GIT_BIN}" clone "${AGENT_PACKAGE_SOURCE}" "${package_dir}"; then
      echo "Warning: optional agent package could not be cloned; the Vault install remains complete." >&2
      return
    fi
  else
    package_dir="$(resolve_target_path "${AGENT_PACKAGE_SOURCE}")"
  fi
  if [[ ! -f "${package_dir}/src/agents.py" ]]; then
    echo "Warning: optional source is not an exported ctx9-agents package; the Vault install remains complete: ${package_dir}" >&2
    return
  fi
  local agent_args=(
    "${package_dir}/src/agents.py"
    install
    --source "${package_dir}"
    --home "${INSTALL_HOME}"
    --apply
  )
  if [[ "${AGENT_GLOBAL_INSTRUCTIONS}" -eq 1 ]]; then agent_args+=(--global-instructions); fi
  if [[ "${AGENT_CLAUDE_ALIAS}" -eq 1 ]]; then agent_args+=(--claude-alias); fi
  if [[ "${AGENT_DISCOVERY_ALIASES}" -eq 1 ]]; then agent_args+=(--discovery-aliases); fi
  if ! run_as_install_user "${PYTHON_BIN}" "${agent_args[@]}"; then
    echo "Warning: optional agent-package install failed; the Vault install remains complete." >&2
    return
  fi
  run_as_install_user mkdir -p "${TARGET}/_system/local/state"
  printf '{"schema_version":1,"installed":true,"global_instructions":%s,"claude_alias":%s,"discovery_aliases":%s}\n' \
    "$([[ "${AGENT_GLOBAL_INSTRUCTIONS}" -eq 1 ]] && printf true || printf false)" \
    "$([[ "${AGENT_CLAUDE_ALIAS}" -eq 1 ]] && printf true || printf false)" \
    "$([[ "${AGENT_DISCOVERY_ALIASES}" -eq 1 ]] && printf true || printf false)" \
    | run_as_install_user tee "${TARGET}/_system/local/state/agent-package-install.json" >/dev/null
}

PYTHON_BIN="$(command -v python3)"
install_optional_agent_package

if [[ "$(uname -s)" == "Darwin" ]]; then
  if run_as_install_user "${PYTHON_BIN}" "${TARGET}/_system/commands/refresh_schedule.py" --root "${TARGET}" register; then
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
  "${PYTHON_BIN}" "${TARGET}/_system/bootstrap/install_vault_command.py" \
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
if ! run_as_install_user "${PYTHON_BIN}" "${TARGET}/_system/bootstrap/print_post_install_next_steps.py" --root "${TARGET}"; then
  echo "Warning: Could not print optional post-install next steps." >&2
fi
