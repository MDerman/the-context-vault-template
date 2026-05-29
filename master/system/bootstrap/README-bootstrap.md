# Context9 Obsidian Vault Setup

The goal of this vault is to have one Obsidian vault where everything related to your personal life, businesses, and other fields of life can live together while staying isolated. It is set up so agents, skills, and workflows have enough context to help schedule, evolve, update, code, and act as personal assistants for you and your business.

This is made possible by a custom plugin called Context Nine and by the Relay plugin and many others. Relay lets team members collaborate on selected folders into their vault. This assumes everyone on your team will be using this vault setup.

## Where To Learn The Vault

After setup, start here:

- `master/00-StartHere.md`: first read and daily operating flow.
- `master/01-Context.md`: folder model, context folders, private/user-owned content, tasks, projects, epics, content, dashboards, and Relay collaboration.
- `master/system/context/OBSIDIAN-PROFILE.md`: Obsidian plugins, settings, templates, UI, and profile details.
- `master/system/context/SCRIPTS.md`: `vault` commands and normal workflows.
- `master/system/bootstrap/bootstrapdocs.md`: bootstrap/export internals.

For Relay collaboration, read `master/01-Context.md` after setup.

## Install On New Mac

Paste this from any terminal directory:

```bash
set -euo pipefail

REPO_URL="https://github.com/MDerman/the-context-vault-template.git"
ICLOUD_DOCS="${HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents"
TARGET="${ICLOUD_DOCS}/Obsidian/Vault"
STATE_BASE="${HOME}/Library/Application Support/matt-vault-bootstrap"

if ! command -v brew >/dev/null 2>&1; then
  echo "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew install finished, but brew is not on PATH. Open a new terminal and rerun this script." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  brew install git
fi

if [[ ! -d "${ICLOUD_DOCS}" ]]; then
  echo "iCloud Obsidian folder missing: ${ICLOUD_DOCS}" >&2
  echo "Install/open Obsidian with iCloud enabled, then rerun this script." >&2
  exit 1
fi

if [[ -e "${TARGET}" ]] && [[ -n "$(find "${TARGET}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "Target vault folder already exists and is not empty: ${TARGET}" >&2
  exit 1
fi

mkdir -p "$(dirname "${TARGET}")"

install_id="$(date -u +%Y%m%dT%H%M%SZ)-$(uuidgen | tr '[:upper:]' '[:lower:]')"
STATE_DIR="${STATE_BASE}/${install_id}"
UPSTREAM_GIT="${STATE_DIR}/upstream.git"

mkdir -p "${STATE_DIR}"
git clone --separate-git-dir "${UPSTREAM_GIT}" "${REPO_URL}" "${TARGET}"
installed_commit="$(git --git-dir "${UPSTREAM_GIT}" --work-tree "${TARGET}" rev-parse HEAD)"
installed_version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET}/.vault-bootstrap/release.json" | head -1)"

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "${value}"
}

mkdir -p "${TARGET}/.vault-bootstrap"
cat > "${TARGET}/.vault-bootstrap/install.json" <<EOF
{
  "schema_version": 1,
  "repo_url": "$(json_escape "${REPO_URL}")",
  "install_id": "$(json_escape "${install_id}")",
  "state_dir": "$(json_escape "${STATE_DIR}")",
  "upstream_git_dir": "$(json_escape "${UPSTREAM_GIT}")",
  "installed_commit": "$(json_escape "${installed_commit}")",
  "installed_version": "$(json_escape "${installed_version:-unknown}")"
}
EOF

rm -f "${TARGET}/.git"
cd "${TARGET}"
master/system/bootstrap/init_vault.sh --no-git
```

Result:

- Vault lives at `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Vault`.
- Public upstream Git state lives outside iCloud under `~/Library/Application Support/matt-vault-bootstrap/`.
- Vault folder has no public-repo `.git` pointer after install.
- `init_vault.sh` installs/checks command dependencies, asks context-folder questions, generates agent files, and installs `vault`.
- Run `master/system/bootstrap/init_vault.sh --enable-git` later only if you want optional personal Git/LFS for your own vault.

Export includes plugin metadata/styles and non-sensitive settings, ships source bundles only for Context Nine and Relay, and excludes known sensitive/local plugin config. Install third-party plugin code locally after setup.

## Upgrade Installed Vault

Preview future public updates:

```bash
vault upgrade --dry-run
```

Apply public setup updates:

```bash
vault upgrade --apply
```

Repair/inspect upgrade state:

```bash
vault upgrade status
vault upgrade doctor
vault upgrade repair-prompt
```
