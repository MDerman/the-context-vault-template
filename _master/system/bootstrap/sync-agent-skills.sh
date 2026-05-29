#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: sync-agent-skills.sh [--dry-run|--apply]

Sync local agent skill directories to the vault skill source.

Default mode is --dry-run. Use --apply to copy existing target-only skills into
the vault source, back up replaced paths, and symlink each target skills
directory to _master/agents/skills.
USAGE
}

mode="dry-run"

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      mode="dry-run"
      ;;
    --apply)
      mode="apply"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vault_root="$(cd "$script_dir/../../.." && pwd)"
agents_dir="$vault_root/_master/agents"
source_dir="$agents_dir/skills"
backup_root="$agents_dir/backups/skill-sync"
timestamp="$(date +%Y%m%d-%H%M%S)"

log() {
  printf '%s\n' "$*"
}

run() {
  if [[ "$mode" == "apply" ]]; then
    "$@"
  else
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  fi
}

resolved_path() {
  local path="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath "$path" 2>/dev/null && return 0
  fi
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$path"
}

same_path() {
  local left="$1"
  local right="$2"
  [[ "$(resolved_path "$left")" == "$(resolved_path "$right")" ]]
}

ensure_source() {
  if [[ -e "$source_dir" && ! -d "$source_dir" ]]; then
    echo "Source exists but is not a directory: $source_dir" >&2
    exit 1
  fi

  if [[ ! -d "$source_dir" ]]; then
    log "Create vault skills source: $source_dir"
    run mkdir -p "$source_dir"
  fi
}

backup_path() {
  local path="$1"
  local label="$2"
  local backup_dir="$backup_root/$timestamp"
  local backup_path="$backup_dir/$label"

  log "Back up $path -> $backup_path"
  run mkdir -p "$backup_dir"
  run mv "$path" "$backup_path"
}

copy_target_only_skills() {
  local target="$1"
  local label="$2"

  [[ -d "$target" && ! -L "$target" ]] || return 0

  shopt -s nullglob dotglob
  local item
  for item in "$target"/*; do
    local name
    name="$(basename "$item")"

    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" ]]; then
      continue
    fi

    if [[ -e "$source_dir/$name" || -L "$source_dir/$name" ]]; then
      backup_path "$item" "${label}-${name}-target-conflict"
    else
      log "Copy target-only skill $item -> $source_dir/$name"
      run cp -a "$item" "$source_dir/$name"
    fi
  done
  shopt -u nullglob dotglob
}

sync_target() {
  local label="$1"
  local target="$2"
  local parent
  parent="$(dirname "$target")"

  log ""
  log "Target: $label -> $target"

  if [[ -L "$target" ]]; then
    local current
    current="$(readlink "$target")"
    if [[ "$current" == "$source_dir" ]] || same_path "$target" "$source_dir"; then
      log "Already linked to vault skills source."
      return 0
    fi

    backup_path "$target" "${label}-skills-symlink"
  elif [[ -d "$target" ]]; then
    copy_target_only_skills "$target" "$label"
    backup_path "$target" "${label}-skills-dir"
  elif [[ -e "$target" ]]; then
    backup_path "$target" "${label}-skills-path"
  fi

  log "Ensure parent directory: $parent"
  run mkdir -p "$parent"
  log "Link $target -> $source_dir"
  run ln -s "$source_dir" "$target"
}

ensure_source

log "Mode: $mode"
log "Vault skills source: $source_dir"

sync_target "codex" "$HOME/.codex/skills"
sync_target "claude" "$HOME/.claude/skills"
sync_target "kilo" "$HOME/.kilo/skills"

if [[ -d "$HOME/.kilocode" ]]; then
  sync_target "kilocode" "$HOME/.kilocode/skills"
else
  log ""
  log "Skip kilocode compatibility target because $HOME/.kilocode does not exist."
fi

log ""
if [[ "$mode" == "apply" ]]; then
  log "Done."
else
  log "Dry run complete. Re-run with --apply to make these changes."
fi
