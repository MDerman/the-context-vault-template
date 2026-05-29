#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export CONFIG_PATH="${CONFIG_PATH:-${SCRIPT_DIR}/config.json}"
eval "$("${SCRIPT_DIR}/load_config_env.py")"

if ! command -v mitmproxy >/dev/null 2>&1; then
  echo "mitmproxy is not installed. Install it with: brew install mitmproxy" >&2
  exit 1
fi

cat <<EOF
Starting per-app API redirect proxy

  app proxy:  http://${PROXY_HOST}:${PROXY_PORT}
  rewrite:    ${TARGET_SCHEME}://${TARGET_HOST}/... -> ${LOCAL_SCHEME}://${LOCAL_HOST}:${LOCAL_PORT}/...

Leave this running while you launch the target app with launch_myapp_with_proxy.sh.
EOF

exec mitmproxy \
  --listen-host "${PROXY_HOST}" \
  --listen-port "${PROXY_PORT}" \
  -s "${SCRIPT_DIR}/redirect_host.py"
