#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CONFIG_PATH="${CONFIG_PATH:-${SCRIPT_DIR}/config.json}"
eval "$("${SCRIPT_DIR}/load_config_env.py")"

APP_PATH="${1:-${APP_PATH}}"

if [[ $# -gt 0 ]]; then
  shift
fi

if [[ ! -d "${APP_PATH}" ]]; then
  cat >&2 <<EOF
App bundle not found:
  ${APP_PATH}

Usage:
  $0 /Applications/MyApp.app
EOF
  exit 1
fi

INFO_PLIST="${APP_PATH}/Contents/Info.plist"
EXECUTABLE_NAME="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${INFO_PLIST}")"
EXECUTABLE_PATH="${APP_PATH}/Contents/MacOS/${EXECUTABLE_NAME}"

if [[ ! -x "${EXECUTABLE_PATH}" ]]; then
  echo "Could not find executable at ${EXECUTABLE_PATH}" >&2
  exit 1
fi

export HTTP_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
export HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
export http_proxy="${HTTP_PROXY}"
export https_proxy="${HTTPS_PROXY}"
export ALL_PROXY="${HTTP_PROXY}"
export all_proxy="${HTTP_PROXY}"
export NO_PROXY=""
export no_proxy=""

cat <<EOF
Launching through local proxy:
  ${APP_PATH}

Proxy:
  ${HTTP_PROXY}
EOF

exec "${EXECUTABLE_PATH}" "$@"
