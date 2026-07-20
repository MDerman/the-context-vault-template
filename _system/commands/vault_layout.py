"""Canonical vault-relative paths and stable generated-file ownership IDs."""

from pathlib import Path


VAULT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_DIR = Path("_system")
COMMANDS_DIR = SYSTEM_DIR / "commands"
BOOTSTRAP_DIR = SYSTEM_DIR / "bootstrap"
CONFIG_DIR = SYSTEM_DIR / "config"
DOCS_DIR = SYSTEM_DIR / "docs"
INBOX_DIR = SYSTEM_DIR / "inbox"
MIGRATIONS_DIR = SYSTEM_DIR / "migrations"
STATE_DIR = SYSTEM_DIR / "state"
SYSTEM_OBSIDIAN_DIR = SYSTEM_DIR / "_obsidian"
VAULT_PERIODIC_DIR = SYSTEM_OBSIDIAN_DIR / "periodic"
AGENTS_DIR = SYSTEM_DIR / "agents"
SYNC_DIR = SYSTEM_DIR / "sync"
TOOLS_DIR = SYSTEM_DIR / "tools"

DASHBOARD_PATH = Path("Dashboard.md")
VAULT_CONFIG_PATH = CONFIG_DIR / "vault.json"
DASHBOARD_ACTION_LINKS_PATH = CONFIG_DIR / "dashboard-action-links.md"
DEPENDENCY_CONFIG_PATH = CONFIG_DIR / "deps.json"
DEPENDENCY_LOCK_PATH = CONFIG_DIR / "dependencies.lock.json"
CALENDAR_CONFIG_PATH = CONFIG_DIR / "calendar.json"

BOOTSTRAP_POLICY_PATH = BOOTSTRAP_DIR / "upgrade-policy.json"
RELEASE_PATH = BOOTSTRAP_DIR / "release.json"
INSTALL_STATE_PATH = STATE_DIR / "install.json"
UPGRADE_REPORTS_DIR = STATE_DIR / "upgrade-reports"
EXPORT_MANIFEST_PATH = STATE_DIR / "export-manifest.json"

MANAGED_DASHBOARD = "vault.dashboard"
MANAGED_PERIODIC = "vault.periodic"
MANAGED_CONTENT = "vault.content"
MANAGED_BOOTSTRAP = "vault.bootstrap"
MANAGED_TASK_CONTEXT_VIEWS = "vault.bootstrap.task-context-views"
MANAGED_EPIC_VIEWS = "vault.epic-views"
