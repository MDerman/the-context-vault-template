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
exist, runs the vault bootstrap, ensures agent symlinks, installs the `vault`
command, then optionally moves the real Git directory outside iCloud.

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
VAULT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
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
    BLOG_CONTEXT_FOLDERS="personal-brand,business"
    SOCIAL_CONTENT_CONTEXT_FOLDERS="personal-brand,business"
    NEWSLETTER_CONTEXT_FOLDERS="personal-brand,business"
    CONTENT_SCHEDULE_CONTEXT_FOLDERS="personal-brand,business"
    FOLDER_TEMPLATES="personal-brand:personal-brand,business:business"
    DEFAULT_CONTEXT_FOLDER="personal"
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
blog = [item["name"] for item in items if "blog" in item.get("capabilities", [])]
social = [item["name"] for item in items if "social-content" in item.get("capabilities", [])]
newsletters = [item["name"] for item in items if "newsletters" in item.get("capabilities", [])]
schedules = [item["name"] for item in items if item.get("content_schedules")]
defaults = [item["name"] for item in items if item.get("default_capture")]
default = defaults[0] if defaults else (active[0] if active else (names[0] if names else "personal"))
templates = [f'{item["name"]}:{item["folder_template"]}' for item in items if item.get("folder_template")]
values = {
    "CONTEXT_FOLDERS": ",".join(names),
    "ACTIVE_CONTEXT_FOLDERS": ",".join(active),
    "BLOG_CONTEXT_FOLDERS": ",".join(blog),
    "SOCIAL_CONTENT_CONTEXT_FOLDERS": ",".join(social),
    "NEWSLETTER_CONTEXT_FOLDERS": ",".join(newsletters),
    "CONTENT_SCHEDULE_CONTEXT_FOLDERS": ",".join(schedules),
    "FOLDER_TEMPLATES": ",".join(templates),
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
  local blog_csv="$3"
  local social_csv="$4"
  local newsletter_csv="$5"
  local schedules_csv="$6"
  local default_context="$7"
  local templates_csv="$8"

  CONTEXT_FOLDERS_CSV="$context_csv" \
    ACTIVE_CONTEXT_FOLDERS_CSV="$active_csv" \
    BLOG_CONTEXT_FOLDERS_CSV="$blog_csv" \
    SOCIAL_CONTENT_CONTEXT_FOLDERS_CSV="$social_csv" \
    NEWSLETTER_CONTEXT_FOLDERS_CSV="$newsletter_csv" \
    CONTENT_SCHEDULE_CONTEXT_FOLDERS_CSV="$schedules_csv" \
    DEFAULT_CONTEXT_FOLDER_VALUE="$default_context" \
    FOLDER_TEMPLATES_CSV="$templates_csv" \
    DRY_RUN_VALUE="$DRY_RUN" \
    "${PYTHON_BIN}" - "${CONFIG_PATH}" <<'PY'
import json
import os
import sys

path = sys.argv[1]
names = [item for item in os.environ["CONTEXT_FOLDERS_CSV"].split(",") if item]
active = {item for item in os.environ["ACTIVE_CONTEXT_FOLDERS_CSV"].split(",") if item}
blog = {item for item in os.environ["BLOG_CONTEXT_FOLDERS_CSV"].split(",") if item}
social = {item for item in os.environ["SOCIAL_CONTENT_CONTEXT_FOLDERS_CSV"].split(",") if item}
newsletters = {item for item in os.environ["NEWSLETTER_CONTEXT_FOLDERS_CSV"].split(",") if item}
schedules = {item for item in os.environ["CONTENT_SCHEDULE_CONTEXT_FOLDERS_CSV"].split(",") if item}
default = os.environ["DEFAULT_CONTEXT_FOLDER_VALUE"]
templates = {}
for item in os.environ["FOLDER_TEMPLATES_CSV"].split(","):
    if not item:
        continue
    name, template = item.split(":", 1)
    templates[name] = template
data = {
    "context_folders": [
        {
            "name": name,
            "status": "active" if name in active else "archived",
            "capabilities": [feature for feature, enabled in [
                ("blog", name in blog),
                ("social-content", name in social),
                ("newsletters", name in newsletters),
            ] if enabled],
            "content_schedules": name in schedules,
            **({"folder_template": templates[name]} if name in templates else {}),
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
  BLOG_CONTEXT_FOLDERS="$(join_by_comma "${brand_context}" "${business_context}")"
  SOCIAL_CONTENT_CONTEXT_FOLDERS="$(join_by_comma "${brand_context}" "${business_context}")"
  NEWSLETTER_CONTEXT_FOLDERS="$(join_by_comma "${brand_context}" "${business_context}")"
  CONTENT_SCHEDULE_CONTEXT_FOLDERS="$(join_by_comma "${brand_context}" "${business_context}")"
  FOLDER_TEMPLATES="$(join_by_comma "${brand_context}:personal-brand" "${business_context}:business")"
  DEFAULT_CONTEXT_FOLDER="${personal_context}"

  cat <<EOF

Setup choices:

  Context folders: ${CONTEXT_FOLDERS}
  Active folders:  ${ACTIVE_CONTEXT_FOLDERS}
  Blog:            ${BLOG_CONTEXT_FOLDERS}
  Social content:  ${SOCIAL_CONTENT_CONTEXT_FOLDERS}
  Newsletters:     ${NEWSLETTER_CONTEXT_FOLDERS}
  Schedules:       ${CONTENT_SCHEDULE_CONTEXT_FOLDERS}
  Default capture: ${DEFAULT_CONTEXT_FOLDER}
  Folder templates:${FOLDER_TEMPLATES}

EOF

  save_config "${CONTEXT_FOLDERS}" "${ACTIVE_CONTEXT_FOLDERS}" "${BLOG_CONTEXT_FOLDERS}" "${SOCIAL_CONTENT_CONTEXT_FOLDERS}" "${NEWSLETTER_CONTEXT_FOLDERS}" "${CONTENT_SCHEDULE_CONTEXT_FOLDERS}" "${DEFAULT_CONTEXT_FOLDER}" "${FOLDER_TEMPLATES}"
}

remap_starter_context_folders() {
  local configured=()
  local personal_target brand_target business_target
  IFS=',' read -r -a configured <<<"${CONTEXT_FOLDERS}"
  personal_target="${configured[0]:-personal}"
  brand_target="${configured[1]:-personal-brand}"
  business_target="${configured[2]:-business}"

  rename_starter_context_folder "personal" "${personal_target}"
  rename_starter_context_folder "personal-brand" "${brand_target}"
  rename_starter_context_folder "business" "${business_target}"
}

rename_starter_context_folder() {
  local source="$1"
  local target="$2"
  if [[ "${source}" == "${target}" ]]; then
    return 0
  fi
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/commands/context_folder_rename.py" \
      --root "${VAULT_ROOT}" \
      --dry-run \
      --missing-ok \
      "${source}" \
      "${target}"
  else
    run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/commands/context_folder_rename.py" \
      --root "${VAULT_ROOT}" \
      --missing-ok \
      "${source}" \
      "${target}"
  fi
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

  if [[ -z "${git_dir}" ]]; then
    if [[ -e "${LOCAL_GIT_DIR}" ]]; then
      die "local Git dir already exists: ${LOCAL_GIT_DIR}"
    fi
    run mkdir -p "${LOCAL_GIT_ROOT}"
    run git -C "${VAULT_ROOT}" init --separate-git-dir="${LOCAL_GIT_DIR}"
    run git --git-dir="${LOCAL_GIT_DIR}" config core.worktree "${VAULT_ROOT}"
    return 0
  fi

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

  # Fresh installs initialize directly into machine-local storage. Existing
  # in-vault repositories are moved before hooks or index changes are made.
  move_git_dir_out_of_icloud
  run git -C "${VAULT_ROOT}" lfs install
  write_gitattributes
  run git -C "${VAULT_ROOT}" config core.autocrlf false
  run git -C "${VAULT_ROOT}" add --renormalize .
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
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    run_dry_capable "${PYTHON_BIN}" "${SCRIPT_DIR}/install_plugins.py" --root "${VAULT_ROOT}" --dry-run
  else
    run_dry_capable "${PYTHON_BIN}" "${SCRIPT_DIR}/install_plugins.py" --root "${VAULT_ROOT}" --apply
  fi
  collect_config
  remap_starter_context_folders

  run_with_optional_dry_run "${PYTHON_BIN}" "${SCRIPT_DIR}/bootstrap_vault.py" \
    --root "${VAULT_ROOT}" \
    --context-folders "${CONTEXT_FOLDERS}" \
    --active-context-folders "${ACTIVE_CONTEXT_FOLDERS}" \
    --blog-context-folders "${BLOG_CONTEXT_FOLDERS}" \
    --social-content-context-folders "${SOCIAL_CONTENT_CONTEXT_FOLDERS}" \
    --newsletter-context-folders "${NEWSLETTER_CONTEXT_FOLDERS}" \
    --content-schedule-context-folders "${CONTENT_SCHEDULE_CONTEXT_FOLDERS}" \
    --folder-templates "${FOLDER_TEMPLATES}" \
    --default-context-folder "${DEFAULT_CONTEXT_FOLDER}" \
    --skip-install-vault-command \
    --skip-agent-symlinks

  local template_pair template_context template_name
  IFS=',' read -r -a template_pairs <<<"${FOLDER_TEMPLATES}"
  for template_pair in "${template_pairs[@]}"; do
    [[ -n "${template_pair}" ]] || continue
    template_context="${template_pair%%:*}"
    template_name="${template_pair#*:}"
    [[ "${template_name}" == "business" ]] || continue
    if [[ "${DRY_RUN}" -eq 1 ]]; then
      run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/commands/business_toolkit.py" sync --root "${VAULT_ROOT}" --context-folders "${template_context}"
    else
      run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/commands/business_toolkit.py" sync --root "${VAULT_ROOT}" --context-folders "${template_context}" --apply
    fi
  done

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/commands/deps.py" sync --root "${VAULT_ROOT}" --dry-run
  else
    run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/commands/deps.py" sync --root "${VAULT_ROOT}" --apply
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/agents/sync_skills.py" sync --root "${VAULT_ROOT}" --dry-run
  else
    run_dry_capable "${PYTHON_BIN}" "${VAULT_ROOT}/_system/agents/sync_skills.py" sync --root "${VAULT_ROOT}" --apply
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
