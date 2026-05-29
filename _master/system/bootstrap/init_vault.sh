#!/usr/bin/env bash
set -eo pipefail

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
  echo "Do not run init_vault.sh as root. Run it as your user, or use sudo from your user so it can drop privileges." >&2
  exit 1
fi

ENABLE_GIT=0
DRY_RUN=0
NON_INTERACTIVE=0
LOCAL_GIT_ROOT="${HOME}/.local/share/vault-git"
LOCAL_GIT_NAME=""
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Usage: init_vault.sh [options]

Initialize a fresh/exported vault after placing it in iCloud.

The script installs/checks dependencies, asks which context folders should
exist, runs the vault bootstrap, generates AGENTS.md, syncs agent skills,
installs the `vault` command, then optionally moves the real Git directory
outside iCloud.

Options:
  --non-interactive        Use init-vault-config.json if present, otherwise defaults.
  --enable-git             Enable optional user Git/LFS setup.
  --no-git                 Skip user Git setup. Default.
  --local-git-root PATH    Directory for real Git dirs. Default: ~/.local/share/vault-git
  --local-git-name NAME    Real Git dir name. Default: current vault folder + .git
  --dry-run                Print or run dry-run-safe actions without changing files.
  -h, --help               Show this help.
EOF
}

die() {
  echo "$*" >&2
  exit 1
}

run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf 'DRY RUN:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

run_dry_capable() {
  "$@"
}

join_by_comma() {
  local IFS=,
  echo "$*"
}

while [[ "$#" -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --enable-git)
      ENABLE_GIT=1
      shift
      ;;
    --no-git|--disable-git)
      ENABLE_GIT=0
      shift
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
      shift
      ;;
    --local-git-root=*)
      LOCAL_GIT_ROOT="${arg#*=}"
      shift
      ;;
    --local-git-name=*)
      LOCAL_GIT_NAME="${arg#*=}"
      shift
      ;;
    --local-git-root)
      [[ "$#" -ge 2 ]] || die "${arg} requires a value"
      LOCAL_GIT_ROOT="$2"
      shift 2
      ;;
    --local-git-name)
      [[ "$#" -ge 2 ]] || die "${arg} requires a value"
      LOCAL_GIT_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: ${arg}"
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
VAULT_NAME="$(basename "${VAULT_ROOT}")"
CONFIG_PATH="${SCRIPT_DIR}/init-vault-config.json"

if [[ -z "${LOCAL_GIT_NAME}" ]]; then
  LOCAL_GIT_NAME="${VAULT_NAME}.git"
fi
LOCAL_GIT_DIR="${LOCAL_GIT_ROOT}/${LOCAL_GIT_NAME}"

is_context_slug() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]]
}

print_context_intro() {
  cat <<'EOF'

###############################################################################
#                                                                             #
#                             SETUP YOUR VAULT                                 #
#                                                                             #
###############################################################################

We first need to choose which entities you want to operate.
These are also known as context folders.

This starter vault creates three context folders:

  personal         personal life, admin, health, relationships
  personal-brand   your public voice, writing, media, audience
  business         company or client work

You can delete, add, or rename context folders later. For setup, keep three.

Input rules:

  - Press Enter to keep the value shown in brackets.
  - If you type a value, type the exact folder slug.
  - Do not include square brackets.
  - Do not type comma-separated lists.
  - Use lowercase letters, numbers, and hyphens.
  - Start with a letter or number.

Examples:

  personal
  jane-smith
  acme-studio

EOF
}

prompt_context_slug() {
  local label="$1"
  local default="$2"
  local answer
  while true; do
    read -r -p "${label} [${default}]: " answer
    answer="${answer:-$default}"
    if is_context_slug "${answer}"; then
      echo "${answer}"
      return 0
    fi
    echo "Use lowercase slug format, without brackets. Example: ${default}" >&2
  done
}

load_config() {
  if [[ ! -f "${CONFIG_PATH}" ]]; then
    CONTEXT_FOLDERS="personal,personal-brand,business"
    ACTIVE_CONTEXT_FOLDERS="${CONTEXT_FOLDERS}"
    CONTENT_CONTEXT_FOLDERS="personal-brand,business"
    DEFAULT_CONTEXT_FOLDER="personal"
    CONTEXT_TYPES="personal:personal,personal-brand:personal-brand,business:business"
    return 0
  fi
  eval "$("${PYTHON_BIN}" - "${CONFIG_PATH}" <<'PY'
import json
import shlex
import sys

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
items = data.get("context_folders") or []
names = [item["name"] for item in items]
active = [item["name"] for item in items if item.get("status") == "active"]
content = [item["name"] for item in items if item.get("content_enabled")]
defaults = [item["name"] for item in items if item.get("default_capture")]
default = defaults[0] if defaults else (active[0] if active else (names[0] if names else "personal"))
types = [f'{item["name"]}:{item.get("context_type") or "business"}' for item in items]
values = {
    "CONTEXT_FOLDERS": ",".join(names),
    "ACTIVE_CONTEXT_FOLDERS": ",".join(active),
    "CONTENT_CONTEXT_FOLDERS": ",".join(content),
    "DEFAULT_CONTEXT_FOLDER": default,
    "CONTEXT_TYPES": ",".join(types),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"
}

save_config() {
  local context_csv="$1"
  local active_csv="$2"
  local content_csv="$3"
  local default_context="$4"
  local context_types_csv="$5"

  CONTEXT_FOLDERS_CSV="$context_csv" \
    ACTIVE_CONTEXT_FOLDERS_CSV="$active_csv" \
    CONTENT_CONTEXT_FOLDERS_CSV="$content_csv" \
    DEFAULT_CONTEXT_FOLDER_VALUE="$default_context" \
    CONTEXT_TYPES_CSV="$context_types_csv" \
    DRY_RUN_VALUE="$DRY_RUN" \
    "${PYTHON_BIN}" - "${CONFIG_PATH}" <<'PY'
import json
import os
import sys

path = sys.argv[1]
names = [item for item in os.environ["CONTEXT_FOLDERS_CSV"].split(",") if item]
active = {item for item in os.environ["ACTIVE_CONTEXT_FOLDERS_CSV"].split(",") if item}
content = {item for item in os.environ["CONTENT_CONTEXT_FOLDERS_CSV"].split(",") if item}
default = os.environ["DEFAULT_CONTEXT_FOLDER_VALUE"]
types = {}
for item in os.environ["CONTEXT_TYPES_CSV"].split(","):
    if not item:
        continue
    name, context_type = item.split(":", 1)
    types[name] = context_type
data = {
    "context_folders": [
        {
            "name": name,
            "status": "active" if name in active else "archived",
            "context_type": types.get(name, "business"),
            "content_enabled": name in content,
            "default_capture": name == default,
        }
        for name in names
    ]
}
rendered = json.dumps(data, indent=2) + "\n"
if os.environ["DRY_RUN_VALUE"] == "1":
    print(f"[dry-run] write {path}")
    print(rendered, end="")
else:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    print(f"wrote {path}")
PY
}

collect_config() {
  load_config
  if [[ "${NON_INTERACTIVE}" -eq 1 ]]; then
    return 0
  fi

  local existing_array=()
  IFS=',' read -r -a existing_array <<<"${CONTEXT_FOLDERS}"

  local personal_default="${existing_array[0]:-personal}"
  local brand_default="${existing_array[1]:-personal-brand}"
  local business_default="${existing_array[2]:-business}"

  is_context_slug "${personal_default}" || personal_default="personal"
  is_context_slug "${brand_default}" || brand_default="personal-brand"
  is_context_slug "${business_default}" || business_default="business"

  print_context_intro

  local personal_context brand_context business_context
  personal_context="$(prompt_context_slug "Rename personal? Personal context folder" "${personal_default}")"
  brand_context="$(prompt_context_slug "Rename personal-brand? Example: your-name" "${brand_default}")"
  business_context="$(prompt_context_slug "Rename business? Example: kpmg" "${business_default}")"

  if [[ "${personal_context}" == "${brand_context}" || "${personal_context}" == "${business_context}" || "${brand_context}" == "${business_context}" ]]; then
    die "Context folder slugs must be unique."
  fi

  CONTEXT_FOLDERS="$(join_by_comma "${personal_context}" "${brand_context}" "${business_context}")"
  ACTIVE_CONTEXT_FOLDERS="${CONTEXT_FOLDERS}"
  CONTENT_CONTEXT_FOLDERS="$(join_by_comma "${brand_context}" "${business_context}")"
  DEFAULT_CONTEXT_FOLDER="${personal_context}"
  CONTEXT_TYPES="$(join_by_comma "${personal_context}:personal" "${brand_context}:personal-brand" "${business_context}:business")"

  cat <<EOF

Setup choices:

  Context folders: ${CONTEXT_FOLDERS}
  Active folders:  ${ACTIVE_CONTEXT_FOLDERS}
  Content system:  ${CONTENT_CONTEXT_FOLDERS}
  Default capture: ${DEFAULT_CONTEXT_FOLDER}
  Types:           ${CONTEXT_TYPES}

EOF

  save_config "${CONTEXT_FOLDERS}" "${ACTIVE_CONTEXT_FOLDERS}" "${CONTENT_CONTEXT_FOLDERS}" "${DEFAULT_CONTEXT_FOLDER}" "${CONTEXT_TYPES}"
}

require_command() {
  local command_name="$1"
  local install_hint="$2"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    die "${command_name} missing. ${install_hint}"
  fi
}

git_patterns() {
  cat <<'EOF'
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.gif filter=lfs diff=lfs merge=lfs -text
*.webp filter=lfs diff=lfs merge=lfs -text
*.heic filter=lfs diff=lfs merge=lfs -text
*.heif filter=lfs diff=lfs merge=lfs -text
*.tif filter=lfs diff=lfs merge=lfs -text
*.tiff filter=lfs diff=lfs merge=lfs -text
*.bmp filter=lfs diff=lfs merge=lfs -text
*.ico filter=lfs diff=lfs merge=lfs -text
*.raw filter=lfs diff=lfs merge=lfs -text
*.arw filter=lfs diff=lfs merge=lfs -text
*.cr2 filter=lfs diff=lfs merge=lfs -text
*.cr3 filter=lfs diff=lfs merge=lfs -text
*.nef filter=lfs diff=lfs merge=lfs -text
*.dng filter=lfs diff=lfs merge=lfs -text
*.raf filter=lfs diff=lfs merge=lfs -text
*.orf filter=lfs diff=lfs merge=lfs -text
*.rw2 filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text
*.m4v filter=lfs diff=lfs merge=lfs -text
*.avi filter=lfs diff=lfs merge=lfs -text
*.mkv filter=lfs diff=lfs merge=lfs -text
*.webm filter=lfs diff=lfs merge=lfs -text
*.m4s filter=lfs diff=lfs merge=lfs -text
*.m3u8 filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.m4a filter=lfs diff=lfs merge=lfs -text
*.aac filter=lfs diff=lfs merge=lfs -text
*.flac filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text
*.ai filter=lfs diff=lfs merge=lfs -text
*.eps filter=lfs diff=lfs merge=lfs -text
*.kra filter=lfs diff=lfs merge=lfs -text
*.bmpr filter=lfs diff=lfs merge=lfs -text
*.sketch filter=lfs diff=lfs merge=lfs -text
*.fig filter=lfs diff=lfs merge=lfs -text
*.pxd filter=lfs diff=lfs merge=lfs -text
*.jam filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
*.pptx filter=lfs diff=lfs merge=lfs -text
*.ppt filter=lfs diff=lfs merge=lfs -text
*.zip filter=lfs diff=lfs merge=lfs -text
*.7z filter=lfs diff=lfs merge=lfs -text
*.rar filter=lfs diff=lfs merge=lfs -text
EOF
}

write_gitattributes() {
  local attributes_path="${VAULT_ROOT}/.gitattributes"
  if [[ -f "${attributes_path}" ]] && grep -q 'filter=lfs' "${attributes_path}"; then
    echo ".gitattributes already contains Git LFS rules"
    return 0
  fi
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "DRY RUN: write Git LFS rules to ${attributes_path}"
    return 0
  fi
  git_patterns >>"${attributes_path}"
}

move_git_dir_out_of_icloud() {
  local git_dir
  git_dir="$(git -C "${VAULT_ROOT}" rev-parse --git-dir 2>/dev/null || true)"

  if [[ "${git_dir}" != ".git" ]]; then
    echo "Git dir already external or unavailable: ${git_dir:-none}"
    return 0
  fi

  if [[ -e "${LOCAL_GIT_DIR}" ]]; then
    die "local Git dir already exists: ${LOCAL_GIT_DIR}"
  fi

  run mkdir -p "${LOCAL_GIT_ROOT}"
  run mv "${VAULT_ROOT}/.git" "${LOCAL_GIT_DIR}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "DRY RUN: write gitdir pointer to ${VAULT_ROOT}/.git"
  else
    printf 'gitdir: %s\n' "${LOCAL_GIT_DIR}" >"${VAULT_ROOT}/.git"
  fi

  run git --git-dir="${LOCAL_GIT_DIR}" config core.worktree "${VAULT_ROOT}"
}

setup_git() {
  require_command git "Install Git first, for example with ./install_dependencies.sh."
  require_command git-lfs "Install Git LFS first, for example with ./install_dependencies.sh."

  if [[ ! -e "${VAULT_ROOT}/.git" ]]; then
    run git -C "${VAULT_ROOT}" init
  fi

  run git -C "${VAULT_ROOT}" lfs install
  write_gitattributes
  run git -C "${VAULT_ROOT}" config core.autocrlf false
  run git -C "${VAULT_ROOT}" add --renormalize .
  move_git_dir_out_of_icloud
}

main() {
  run_with_optional_dry_run() {
    if [[ "${DRY_RUN}" -eq 1 ]]; then
      run_dry_capable "$@" --dry-run
    else
      run_dry_capable "$@"
    fi
  }

  run_with_optional_dry_run "${SCRIPT_DIR}/install_dependencies.sh"
  collect_config

  run_with_optional_dry_run "${PYTHON_BIN}" "${SCRIPT_DIR}/bootstrap_vault.py" \
    --root "${VAULT_ROOT}" \
    --context-folders "${CONTEXT_FOLDERS}" \
    --active-context-folders "${ACTIVE_CONTEXT_FOLDERS}" \
    --content-context-folders "${CONTENT_CONTEXT_FOLDERS}" \
    --context-types "${CONTEXT_TYPES}" \
    --default-context-folder "${DEFAULT_CONTEXT_FOLDER}" \
    --skip-install-vault-command \
    --skip-generate-agents

  run_with_optional_dry_run "${PYTHON_BIN}" "${SCRIPT_DIR}/generate_agents.py" --root "${VAULT_ROOT}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    run_dry_capable "${SCRIPT_DIR}/sync-agent-skills.sh" --dry-run
  else
    run_dry_capable "${SCRIPT_DIR}/sync-agent-skills.sh" --apply
  fi

  run_with_optional_dry_run "${PYTHON_BIN}" "${SCRIPT_DIR}/install_vault_command.py" --root "${VAULT_ROOT}"

  if [[ "${ENABLE_GIT}" -eq 1 ]]; then
    setup_git
  else
    echo "Git setup skipped."
  fi

  echo "Vault init complete."
}

main "$@"
