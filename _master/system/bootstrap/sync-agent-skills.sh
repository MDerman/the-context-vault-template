#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: sync-agent-skills.sh [--dry-run|--apply]

Sync local coding-agent global skill directories to the vault skill source and
manual-only skill-pack source.

Default mode is --dry-run. Use --apply to reset existing symlinks, copy
existing target-only skills from non-symlink directories into the vault source,
back up replaced non-symlink paths, and symlink each target skills directory to
_master/agents/skills. Direct children of _master/agents/skill-packs that
contain SKILL.md are symlinked into _master/agents/skills/manual.
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
skill_packs_dir="$agents_dir/skill-packs"
manual_dir="$source_dir/manual"
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

ensure_dir_path() {
  local path="$1"
  local label="$2"

  if [[ -e "$path" && ! -d "$path" ]]; then
    echo "$label exists but is not a directory: $path" >&2
    exit 1
  fi

  if [[ ! -d "$path" ]]; then
    log "Create $label: $path"
    run mkdir -p "$path"
  fi
}

ensure_source() {
  ensure_dir_path "$source_dir" "vault skills source"
  ensure_dir_path "$skill_packs_dir" "vault skill packs source"
  ensure_dir_path "$manual_dir" "manual skills symlink directory"
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

reset_symlink() {
  local target="$1"

  log "Reset symlink: $target"
  run rm "$target"
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

    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
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
    reset_symlink "$target"
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

sync_plain_symlink() {
  local label="$1"
  local target="$2"
  local link_source="$3"
  local parent
  parent="$(dirname "$target")"

  log ""
  log "Target: $label -> $target"

  if [[ -L "$target" ]]; then
    reset_symlink "$target"
  elif [[ -e "$target" ]]; then
    backup_path "$target" "${label}-path"
  fi

  log "Ensure parent directory: $parent"
  run mkdir -p "$parent"
  log "Link $target -> $link_source"
  run ln -s "$link_source" "$target"
}

sync_manual_skill_links() {
  log ""
  log "Manual skill links: $manual_dir -> $skill_packs_dir"

  shopt -s nullglob dotglob
  local link
  for link in "$manual_dir"/*; do
    local name
    name="$(basename "$link")"
    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
      continue
    fi
    if [[ -L "$link" && ! -d "$skill_packs_dir/$name" ]]; then
      log "Remove stale manual skill link: $link"
      run rm "$link"
    fi
  done

  local skill
  for skill in "$skill_packs_dir"/*; do
    local name metadata target rel_target current
    name="$(basename "$skill")"
    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
      continue
    fi
    if [[ ! -d "$skill" ]]; then
      log "Skip non-directory skill-pack child: $skill"
      continue
    fi
    if [[ ! -f "$skill/SKILL.md" ]]; then
      log "Skip skill-pack child without SKILL.md: $skill"
      continue
    fi

    metadata="$skill/agents/openai.yaml"
    if [[ ! -f "$metadata" ]]; then
      log "WARNING: manual skill missing agents/openai.yaml: $skill"
    elif ! grep -Eq 'allow_implicit_invocation:[[:space:]]*false' "$metadata"; then
      log "WARNING: manual skill should set policy.allow_implicit_invocation: false: $metadata"
    fi

    target="$manual_dir/$name"
    rel_target="../../skill-packs/$name"

    if [[ -L "$target" ]]; then
      current="$(readlink "$target")"
      if [[ "$current" == "$rel_target" ]]; then
        log "Manual skill link already current: $target"
        continue
      fi
      reset_symlink "$target"
    elif [[ -e "$target" ]]; then
      backup_path "$target" "manual-${name}-conflict"
    fi

    log "Link manual skill $target -> $rel_target"
    run ln -s "$rel_target" "$target"
  done
  shopt -u nullglob dotglob
}

ensure_source

log "Mode: $mode"
log "Vault skills source: $source_dir"
log "Vault skill packs source: $skill_packs_dir"

sync_target "codex" "$HOME/.codex/skills"
sync_plain_symlink "codex-skill-packs" "$HOME/.codex/skill-packs" "$skill_packs_dir"
sync_target "claude" "$HOME/.claude/skills"
sync_plain_symlink "claude-skill-packs" "$HOME/.claude/skill-packs" "$skill_packs_dir"
sync_target "kilo" "$HOME/.kilo/skills"
sync_plain_symlink "kilo-skill-packs" "$HOME/.kilo/skill-packs" "$skill_packs_dir"

if [[ -d "$HOME/.kilocode" ]]; then
  sync_target "kilocode" "$HOME/.kilocode/skills"
  sync_plain_symlink "kilocode-skill-packs" "$HOME/.kilocode/skill-packs" "$skill_packs_dir"
else
  log ""
  log "Skip kilocode compatibility target because $HOME/.kilocode does not exist."
fi

sync_manual_skill_links

log ""
if [[ "$mode" == "apply" ]]; then
  log "Done."
else
  log "Dry run complete. Re-run with --apply to make these changes."
fi
