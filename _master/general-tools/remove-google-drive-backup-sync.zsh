#!/usr/bin/env zsh
set -euo pipefail
setopt NULL_GLOB

SCRIPT_NAME="${0:t}"
APPLY=0
YES=0
REMOVE_SHARED_GOOGLE_UPDATER=0
SKIP_LEFTOVERS=0

usage() {
  cat <<'EOF'
Completely remove Google Drive for desktop from macOS.

Targets current Drive for desktop / DriveFS / File Provider installs, including:
  - Google Drive.app
  - DriveFS support data, caches, logs, prefs, app scripts, containers
  - macOS File Provider CloudStorage folders
  - old "$HOME/Google Drive" local folder

Usage:
  remove-google-drive-backup-sync.zsh [options]

Options:
  --apply                         Delete files. Default is dry-run.
  -y, --yes                       Skip confirmation prompt when using --apply.
  --remove-shared-google-updater  Also delete shared Google updater/Keystone files.
                                  Use only if no Chrome/Google apps should remain.
  --skip-leftovers-check          Skip Spotlight leftovers search.
  -h, --help                      Show help.

Examples:
  remove-google-drive-backup-sync.zsh
  remove-google-drive-backup-sync.zsh --apply
  remove-google-drive-backup-sync.zsh --apply -y --remove-shared-google-updater

Notes:
  - Full cleanup deletes local/offline Google Drive copies.
  - Check Drive sync status before running --apply.
  - Reboot after cleanup.
EOF
}

log() {
  print -- "$@"
}

warn() {
  print -u2 -- "$@"
}

run() {
  if (( APPLY )); then
    "$@"
  else
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  fi
}

run_sudo_rm_rf() {
  local path
  for path in "$@"; do
    [[ -e "$path" || -L "$path" ]] || continue
    if (( APPLY )); then
      sudo rm -rf -- "$path"
    else
      printf '[dry-run] sudo rm -rf -- %q\n' "$path"
    fi
  done
}

run_rm_rf_globs() {
  local path
  for path in "$@"; do
    [[ -e "$path" || -L "$path" ]] || continue
    run rm -rf -- "$path"
  done
}

confirm_or_exit() {
  (( APPLY )) || return 0
  (( YES )) && return 0

  cat <<'EOF'
About to delete Google Drive for desktop app, caches, config, File Provider data,
CloudStorage folders, and old local Google Drive folder.

This can remove local/offline copies. Unsynced files may be lost.
EOF
  printf "Continue? [y/N] "
  read -r reply
  case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *) log "Aborted."; exit 1 ;;
  esac
}

while (( $# > 0 )); do
  case "$1" in
    --apply)
      APPLY=1
      ;;
    -y|--yes)
      YES=1
      ;;
    --remove-shared-google-updater)
      REMOVE_SHARED_GOOGLE_UPDATER=1
      ;;
    --skip-leftovers-check)
      SKIP_LEFTOVERS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      warn "Unknown option: $1"
      usage
      exit 2
      ;;
  esac
  shift
done

cat <<EOF
Google Drive cleanup plan:
  mode: $([[ "$APPLY" == 1 ]] && print "apply/delete" || print "dry-run")
  app: /Applications/Google Drive.app
  data: DriveFS app support, caches, logs, prefs, containers, app scripts
  local copies: ~/Library/CloudStorage/GoogleDrive-* and ~/Google Drive
  shared updater: $([[ "$REMOVE_SHARED_GOOGLE_UPDATER" == 1 ]] && print "delete" || print "keep")
EOF

confirm_or_exit

log
log "Stopping Google Drive..."
if (( APPLY )); then
  osascript -e 'quit app "Google Drive"' >/dev/null 2>&1 || true
fi
run pkill -x "Google Drive" || true
run pkill -f "[G]oogle Drive" || true
run pkill -f "[D]riveFS" || true
run pkill -f "[d]rivefs" || true
run pkill -f "[G]oogleDriveFS" || true
sleep 1

log
log "Deleting app and system DriveFS files..."
run_sudo_rm_rf \
  "/Applications/Google Drive.app" \
  "/Library/Google/DriveFS" \
  "/Library/Application Support/Google/DriveFS" \
  "/Library/Application Support/Google/Drive" \
  "/Library/Application Support/Google/Google Drive" \
  "/Library/Logs/Google/DriveFS" \
  "/Library/LaunchAgents/com.google.drivefs.plist" \
  "/Library/LaunchAgents/com.google.drivefs.finderhelper.plist" \
  "/Library/LaunchDaemons/com.google.drivefs.plist"

log
log "Deleting user DriveFS data, caches, prefs, scripts..."
run_rm_rf_globs \
  "$HOME/Library/Application Support/Google/DriveFS" \
  "$HOME/Library/Application Support/Google/Drive" \
  "$HOME/Library/Application Support/Google/Google Drive" \
  "$HOME/Library/Application Scripts/com.google.drivefs" \
  "$HOME/Library/Application Scripts/com.google.drivefs.fpext" \
  "$HOME/Library/Application Scripts/com.google.drivefs.finderhelper" \
  "$HOME/Library/Application Scripts/com.google.drivefs.finderhelper.findersync" \
  "$HOME/Library/Application Scripts/EQHXZ8M8AV.group.com.google.drivefs" \
  "$HOME/Library/Containers/com.google.drivefs" \
  "$HOME/Library/Containers/com.google.drivefs.fpext" \
  "$HOME/Library/Containers/com.google.drivefs.finderhelper" \
  "$HOME/Library/Group Containers/EQHXZ8M8AV.group.com.google.drivefs" \
  "$HOME/Library/Caches/com.google.drivefs"* \
  "$HOME/Library/Caches/com.google.GoogleDrive"* \
  "$HOME/Library/Caches/Google/DriveFS" \
  "$HOME/Library/HTTPStorages/com.google.drivefs"* \
  "$HOME/Library/Preferences/com.google.drivefs"* \
  "$HOME/Library/Preferences/com.google.GoogleDrive"* \
  "$HOME/Library/Logs/Google/DriveFS" \
  "$HOME/Library/Saved Application State/com.google.drivefs.savedState"

log
log "Deleting local/offline Drive folders..."
run_rm_rf_globs \
  "$HOME/Google Drive" \
  "$HOME/Library/CloudStorage/GoogleDrive-"*

if (( REMOVE_SHARED_GOOGLE_UPDATER )); then
  log
  log "Deleting shared Google updater/Keystone files..."
  run_sudo_rm_rf \
    "/Library/Google/GoogleSoftwareUpdate" \
    "/Library/Google/GoogleUpdater" \
    "/Library/LaunchAgents/com.google.keystone.agent.plist" \
    "/Library/LaunchAgents/com.google.keystone.xpcservice.plist" \
    "/Library/LaunchDaemons/com.google.keystone.daemon.plist" \
    "/Library/LaunchDaemons/com.google.GoogleUpdater.wake.system.plist" \
    "/Library/PrivilegedHelperTools/com.google.GoogleSoftwareUpdate.daemon" \
    "/Library/PrivilegedHelperTools/com.google.GoogleUpdater.wake.system"

  run_rm_rf_globs \
    "$HOME/Library/Google/GoogleSoftwareUpdate" \
    "$HOME/Library/Application Support/Google/GoogleUpdater" \
    "$HOME/Library/Caches/com.google.Keystone"* \
    "$HOME/Library/Caches/com.google.GoogleUpdater"*
fi

if (( ! SKIP_LEFTOVERS )); then
  log
  log "Leftovers check:"
  if (( APPLY )); then
    mdfind 'kMDItemFSName == "*Google Drive*" || kMDItemFSName == "*GoogleDrive*" || kMDItemFSName == "*DriveFS*" || kMDItemFSName == "*drivefs*"' || true
  else
    log '[dry-run] mdfind '\''kMDItemFSName == "*Google Drive*" || kMDItemFSName == "*GoogleDrive*" || kMDItemFSName == "*DriveFS*" || kMDItemFSName == "*drivefs*"'\'''
  fi
fi

log
if (( APPLY )); then
  log "Done. Reboot Mac, then empty Trash if Finder moved anything there."
else
  log "Dry-run done. Run with --apply to delete."
fi
