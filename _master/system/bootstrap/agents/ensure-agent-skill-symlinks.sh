#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ensure-agent-skill-symlinks.sh [--dry-run|--apply]

Sync local coding-agent global skill directories to the vault active skill source
and expose manual-only and GitHub-managed skills as direct per-skill symlinks.

Default mode is --dry-run. Use --apply to reset existing symlinks, copy
existing target-only skills from non-symlink directories into the vault source,
back up replaced non-symlink paths, symlink each target skills directory to
_master/agents/skills, and create one symlink in _master/agents/skills for each
child skill in _master/agents/manual-skills and _master/agents/gh-skills.
Manual skills rely on their agents/openai.yaml policy metadata to block
implicit invocation. GitHub-managed skills are installed with `gh skill --dir`.
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
vault_root="$(cd "$script_dir/../../../.." && pwd)"
agents_dir="$vault_root/_master/agents"
source_dir="$agents_dir/skills"
manual_skills_dir="$agents_dir/manual-skills"
gh_skills_dir="$agents_dir/gh-skills"
legacy_manual_dir="$source_dir/manual"
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
  ensure_dir_path "$manual_skills_dir" "vault manual skills source"
  ensure_dir_path "$gh_skills_dir" "vault gh-managed skills source"
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

remove_legacy_plain_symlink() {
  local label="$1"
  local target="$2"

  if [[ -L "$target" ]]; then
    log ""
    log "Remove legacy target: $label -> $target"
    reset_symlink "$target"
  fi
}

cleanup_legacy_manual_dir() {
  if [[ ! -e "$legacy_manual_dir" && ! -L "$legacy_manual_dir" ]]; then
    return
  fi

  if [[ -L "$legacy_manual_dir" ]]; then
    log ""
    log "Remove legacy manual skills symlink directory: $legacy_manual_dir"
    reset_symlink "$legacy_manual_dir"
    return
  fi

  if [[ -d "$legacy_manual_dir" ]]; then
    shopt -s nullglob dotglob
    local item only_managed=1
    for item in "$legacy_manual_dir"/*; do
      local name
      name="$(basename "$item")"
      if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
        continue
      fi
      if [[ ! -L "$item" ]]; then
        only_managed=0
        break
      fi
    done
    shopt -u nullglob dotglob

    if [[ "$only_managed" == "1" ]]; then
      log ""
      log "Remove legacy manual skills directory: $legacy_manual_dir"
      run rm -rf "$legacy_manual_dir"
    else
      backup_path "$legacy_manual_dir" "legacy-manual-skills-dir"
    fi
  fi
}

sync_manual_skill_links() {
  log ""
  log "Manual skill symlinks: $source_dir -> $manual_skills_dir"

  shopt -s nullglob dotglob
  local link
  for link in "$source_dir"/*; do
    local name
    name="$(basename "$link")"
    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
      continue
    fi
    if [[ -d "$link" && -f "$link/.manual-skill-wrapper.json" ]]; then
      log "Remove legacy manual skill wrapper from active skills: $link"
      run rm -rf "$link"
    fi
  done

  local skill
  for skill in "$manual_skills_dir"/*; do
    local name metadata target rel_target
    name="$(basename "$skill")"
    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
      continue
    fi
    if [[ ! -d "$skill" ]]; then
      log "Skip non-directory manual skill child: $skill"
      continue
    fi
    if [[ ! -f "$skill/SKILL.md" ]]; then
      log "Skip manual skill child without SKILL.md: $skill"
      continue
    fi

    metadata="$skill/agents/openai.yaml"
    if [[ ! -f "$metadata" ]]; then
      log "WARNING: manual skill missing agents/openai.yaml: $skill"
    elif ! grep -Eq 'allow_implicit_invocation:[[:space:]]*false' "$metadata"; then
      log "WARNING: manual skill should set policy.allow_implicit_invocation: false: $metadata"
    fi

    target="$source_dir/$name"
    rel_target="../manual-skills/$name"

    if [[ -L "$target" ]]; then
      if [[ "$(readlink "$target")" == "$rel_target" ]]; then
        log "Manual skill symlink current: $target -> $rel_target"
        continue
      fi
      reset_symlink "$target"
    elif [[ -d "$target" && -f "$target/.manual-skill-wrapper.json" ]]; then
      log "Remove legacy manual skill wrapper from active skills: $target"
      run rm -rf "$target"
    elif [[ -e "$target" ]]; then
      backup_path "$target" "manual-${name}-conflict"
    fi

    log "Link manual skill $target -> $rel_target"
    run ln -s "$rel_target" "$target"
  done
  shopt -u nullglob dotglob
}

sync_gh_skill_links() {
  log ""
  log "GitHub-managed skill symlinks: $source_dir -> $gh_skills_dir"

  shopt -s nullglob dotglob
  local link
  for link in "$source_dir"/*; do
    local name rel gh_target
    name="$(basename "$link")"
    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
      continue
    fi
    if [[ ! -L "$link" ]]; then
      continue
    fi
    rel="$(readlink "$link")"
    if [[ "$rel" != ../gh-skills/* ]]; then
      continue
    fi
    gh_target="$gh_skills_dir/${rel#../gh-skills/}"
    if [[ ! -d "$gh_target" || ! -f "$gh_target/SKILL.md" ]]; then
      log "Remove stale GitHub-managed skill symlink: $link -> $rel"
      reset_symlink "$link"
    fi
  done

  local skill
  for skill in "$gh_skills_dir"/*; do
    local name target rel_target current
    name="$(basename "$skill")"
    if [[ "$name" == "." || "$name" == ".." || "$name" == ".DS_Store" || "$name" == ".gitkeep" ]]; then
      continue
    fi
    if [[ ! -d "$skill" ]]; then
      log "Skip non-directory GitHub-managed skill child: $skill"
      continue
    fi
    if [[ ! -f "$skill/SKILL.md" ]]; then
      log "Skip GitHub-managed skill child without SKILL.md: $skill"
      continue
    fi

    target="$source_dir/$name"
    rel_target="../gh-skills/$name"

    if [[ -L "$target" ]]; then
      current="$(readlink "$target")"
      if [[ "$current" == "$rel_target" ]]; then
        log "GitHub-managed skill symlink current: $target -> $rel_target"
        continue
      fi
      log "Skip GitHub-managed skill because active target exists: $target -> $current"
      continue
    elif [[ -e "$target" ]]; then
      log "Skip GitHub-managed skill because active target exists: $target"
      continue
    fi

    log "Link GitHub-managed skill $target -> $rel_target"
    run ln -s "$rel_target" "$target"
  done
  shopt -u nullglob dotglob
}

ensure_source

log "Mode: $mode"
log "Vault skills source: $source_dir"
log "Vault manual skills source: $manual_skills_dir"
log "Vault gh-managed skills source: $gh_skills_dir"

sync_target "codex" "$HOME/.codex/skills"
remove_legacy_plain_symlink "codex-manual-skills" "$HOME/.codex/manual-skills"
remove_legacy_plain_symlink "codex-skill-packs" "$HOME/.codex/skill-packs"
sync_target "claude" "$HOME/.claude/skills"
remove_legacy_plain_symlink "claude-manual-skills" "$HOME/.claude/manual-skills"
remove_legacy_plain_symlink "claude-skill-packs" "$HOME/.claude/skill-packs"
sync_target "kilo" "$HOME/.kilo/skills"
remove_legacy_plain_symlink "kilo-manual-skills" "$HOME/.kilo/manual-skills"
remove_legacy_plain_symlink "kilo-skill-packs" "$HOME/.kilo/skill-packs"

if [[ -d "$HOME/.kilocode" ]]; then
  sync_target "kilocode" "$HOME/.kilocode/skills"
  remove_legacy_plain_symlink "kilocode-manual-skills" "$HOME/.kilocode/manual-skills"
  remove_legacy_plain_symlink "kilocode-skill-packs" "$HOME/.kilocode/skill-packs"
else
  log ""
  log "Skip kilocode compatibility target because $HOME/.kilocode does not exist."
fi

cleanup_legacy_manual_dir
sync_manual_skill_links
sync_gh_skill_links

log ""
if [[ "$mode" == "apply" ]]; then
  log "Done."
else
  log "Dry run complete. Re-run with --apply to make these changes."
fi
