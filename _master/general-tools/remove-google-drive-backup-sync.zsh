#!/usr/bin/env zsh
set -euo pipefail
setopt NULL_GLOB

SCRIPT_NAME="${0:t}"
YES=0
REMOVE_LOCAL_FILES=0
REMOVE_GOOGLE_UPDATER=0
SHOW_LEFTOVERS=1

usage() {
  cat <<'EOF'
Remove Google Drive for desktop / old Backup and Sync from macOS.

Usage:
  remove-google-drive-backup-sync.zsh [options]

Options:
  -y, --yes                  Skip confirmation prompt.
  --remove-local-files       Also delete "$HOME/Google Drive" and "$HOME/Library/CloudStorage/GoogleDrive-*".
  --remove-google-updater    Also delete shared Google Software Update components. This affects Chrome auto-update.
  --no-leftovers-check       Skip mdfind leftovers check.
  -h, --help                 Show help.

Default keeps offline/local file copies and shared Google updater.
EOF
}

while (( $# > 0 )); do
  case "$1" in
    -y|--yes)
      YES=1
      ;;
    --remove-local-files)
      REMOVE_LOCAL_FILES=1
      ;;
    --remove-google-updater)
      REMOVE_GOOGLE_UPDATER=1
      ;;
    --no-leftovers-check)
      SHOW_LEFTOVERS=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      print -u2 "Unknown option: $1"
      usage
      exit 2
      ;;
  esac
  shift
done

print "Google Drive removal plan:"
print "  - Quit Google Drive and drivefs processes"
print "  - Delete /Applications/Google Drive.app"
print "  - Delete DriveFS app support, app scripts, cache, prefs, logs, saved state"

if (( REMOVE_LOCAL_FILES )); then
  print "  - Delete local/offline copies: ~/Google Drive and ~/Library/CloudStorage/GoogleDrive-*"
else
  print "  - Keep local/offline copies: ~/Google Drive and ~/Library/CloudStorage/GoogleDrive-*"
fi

if (( REMOVE_GOOGLE_UPDATER )); then
  print "  - Delete shared Google Software Update components with sudo"
else
  print "  - Keep shared Google Software Update components"
fi

if (( ! YES )); then
  print
  print "Caution: Google Drive local/offline folders can contain files not safely synced yet."
  printf "Continue? [y/N] "
  read -r reply
  case "$reply" in
    [yY]|[yY][eE][sS])
      ;;
    *)
      print "Aborted."
      exit 1
      ;;
  esac
fi

print "Quitting Google Drive..."
osascript -e 'quit app "Google Drive"' >/dev/null 2>&1 || true
pkill -f "Google Drive" >/dev/null 2>&1 || true
pkill -f drivefs >/dev/null 2>&1 || true

print "Deleting app..."
if [[ -d "/Applications/Google Drive.app" ]]; then
  if ! rm -rf "/Applications/Google Drive.app" 2>/dev/null; then
    if [[ -t 0 ]]; then
      sudo rm -rf "/Applications/Google Drive.app" || print "App still present. Remove with admin: sudo rm -rf '/Applications/Google Drive.app'"
    elif sudo -n true >/dev/null 2>&1; then
      sudo rm -rf "/Applications/Google Drive.app"
    else
      print "App still present. Admin password needed: sudo rm -rf '/Applications/Google Drive.app'"
    fi
  fi
fi

print "Deleting Drive cache/config..."
rm -rf \
  "$HOME/Library/Application Support/Google/DriveFS" \
  "$HOME/Library/Application Support/Google/Drive" \
  "$HOME/Library/Application Support/Google/Google Drive" \
  "$HOME/Library/Application Scripts/com.google.drivefs.fpext" \
  "$HOME/Library/Application Scripts/EQHXZ8M8AV.group.com.google.drivefs" \
  "$HOME/Library/Application Scripts/com.google.drivefs.finderhelper.findersync" \
  "$HOME/Library/Application Scripts/com.google.drivefs.finderhelper" \
  "$HOME/Library/Caches/com.google.drivefs"* \
  "$HOME/Library/Preferences/com.google.drivefs"* \
  "$HOME/Library/Logs/Google/DriveFS" \
  "$HOME/Library/Saved Application State/com.google.drivefs.savedState"

if (( REMOVE_LOCAL_FILES )); then
  print "Deleting local/offline Google Drive folders..."
  rm -rf \
    "$HOME/Google Drive" \
    "$HOME/Library/CloudStorage/GoogleDrive-"*
fi

if (( REMOVE_GOOGLE_UPDATER )); then
  print "Deleting shared Google Software Update components..."
  sudo rm -rf \
    "/Library/Google/GoogleSoftwareUpdate" \
    "/Library/LaunchAgents/com.google.keystone.agent.plist" \
    "/Library/LaunchDaemons/com.google.keystone.daemon.plist" \
    "/Library/PrivilegedHelperTools/com.google.GoogleSoftwareUpdate.daemon"
fi

if (( SHOW_LEFTOVERS )); then
  print
  print "Leftovers check:"
  mdfind 'kMDItemFSName == "*GoogleDrive*" || kMDItemFSName == "*drivefs*"' || true
fi

print
print "Done. Restart Mac to finish cleanup."
