#!/usr/bin/env bash
set -eo pipefail

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

contains_item() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

prompt_line() {
  local label="$1"
  local default="$2"
  local answer
  read -r -p "${label} [${default}]: " answer
  echo "${answer:-$default}"
}

prompt_yes_no() {
  local label="$1"
  local default="$2"
  local answer suffix
  if [[ "$default" == "yes" ]]; then
    suffix="Y/n"
  else
    suffix="y/N"
  fi
  while true; do
    read -r -p "${label} [${suffix}]: " answer
    answer="${answer:-$default}"
    case "$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')" in
      y|yes|true|1) return 0 ;;
      n|no|false|0) return 1 ;;
      *) echo "Please answer yes or no." ;;
    esac
  done
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

normalize_names() {
  "${PYTHON_BIN}" - "$1" <<'PY'
import re
import sys

raw = sys.argv[1]
items = [item.strip() for item in raw.split(",") if item.strip()]
if not items:
    raise SystemExit("At least one context folder is required.")

def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^\d\d-", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        raise SystemExit(f"Could not slugify context folder name: {value!r}")
    return value

seen = set()
for index, item in enumerate(items, 1):
    if re.match(r"^\d\d-[a-z0-9][a-z0-9-]*$", item):
        name = item
    else:
        name = f"{index:02d}-{slugify(item)}"
    if name in seen:
        raise SystemExit(f"Duplicate context folder name: {name}")
    seen.add(name)
    print(name)
PY
}

load_config() {
  if [[ ! -f "${CONFIG_PATH}" ]]; then
    CONTEXT_FOLDERS="01-personal,02-personal-brand,03-business"
    ACTIVE_CONTEXT_FOLDERS="${CONTEXT_FOLDERS}"
    CONTENT_CONTEXT_FOLDERS="02-personal-brand,03-business"
    DEFAULT_CONTEXT_FOLDER="01-personal"
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
default = defaults[0] if defaults else (active[0] if active else (names[0] if names else "01-personal"))
values = {
    "CONTEXT_FOLDERS": ",".join(names),
    "ACTIVE_CONTEXT_FOLDERS": ",".join(active),
    "CONTENT_CONTEXT_FOLDERS": ",".join(content),
    "DEFAULT_CONTEXT_FOLDER": default,
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

  CONTEXT_FOLDERS_CSV="$context_csv" \
    ACTIVE_CONTEXT_FOLDERS_CSV="$active_csv" \
    CONTENT_CONTEXT_FOLDERS_CSV="$content_csv" \
    DEFAULT_CONTEXT_FOLDER_VALUE="$default_context" \
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
data = {
    "context_folders": [
        {
            "name": name,
            "status": "active" if name in active else "archived",
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

  cat <<'EOF'

Context folders are entity home directories inside this vault.
Use one for yourself, one for a personal brand, one for a business, or any
set of entities you want to operate separately.

Enter names as exact `NN-slug` folders or plain names. Plain names become
numbered folders, for example `business` becomes `03-business`.
EOF

  local names_input
  names_input="$(prompt_line "Context folders, comma-separated" "${CONTEXT_FOLDERS}")"
  local context_array=()
  while IFS= read -r normalized_name; do
    context_array+=("${normalized_name}")
  done < <(normalize_names "${names_input}")

  local active_array=()
  local content_array=()
  local name active_default content_default
  IFS=',' read -r -a existing_active <<<"${ACTIVE_CONTEXT_FOLDERS}"
  IFS=',' read -r -a existing_content <<<"${CONTENT_CONTEXT_FOLDERS}"

  echo ""
  echo "Active context folders appear in default dashboards, agent rollups, and routing."
  for name in "${context_array[@]}"; do
    active_default="no"
    contains_item "$name" "${existing_active[@]}" && active_default="yes"
    if prompt_yes_no "Make ${name} active?" "${active_default}"; then
      active_array+=("$name")
    fi
  done

  if [[ "${#active_array[@]}" -eq 0 ]]; then
    die "At least one active context folder is required."
  fi

  echo ""
  echo "Content-enabled folders get content items, publication definitions, schedules, and content views."
  for name in "${context_array[@]}"; do
    content_default="no"
    contains_item "$name" "${existing_content[@]}" && content_default="yes"
    if prompt_yes_no "Enable content system for ${name}?" "${content_default}"; then
      content_array+=("$name")
    fi
  done

  echo ""
  echo "Default capture folder receives unspecific tasks and periodic capture."
  local default_prompt default_choice valid_default
  default_prompt="${DEFAULT_CONTEXT_FOLDER}"
  contains_item "$default_prompt" "${active_array[@]}" || default_prompt="${active_array[0]}"
  while true; do
    default_choice="$(prompt_line "Default capture context folder" "${default_prompt}")"
    valid_default=0
    for name in "${active_array[@]}"; do
      if [[ "$default_choice" == "$name" ]]; then
        valid_default=1
        break
      fi
    done
    [[ "$valid_default" -eq 1 ]] && break
    echo "Choose one active context folder: $(join_by_comma "${active_array[@]}")"
  done

  CONTEXT_FOLDERS="$(join_by_comma "${context_array[@]}")"
  ACTIVE_CONTEXT_FOLDERS="$(join_by_comma "${active_array[@]}")"
  CONTENT_CONTEXT_FOLDERS="$(join_by_comma "${content_array[@]}")"
  DEFAULT_CONTEXT_FOLDER="${default_choice}"
  save_config "${CONTEXT_FOLDERS}" "${ACTIVE_CONTEXT_FOLDERS}" "${CONTENT_CONTEXT_FOLDERS}" "${DEFAULT_CONTEXT_FOLDER}"
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
