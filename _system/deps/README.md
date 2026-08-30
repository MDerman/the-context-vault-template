## Vault dependencies

`packages.yaml` is the complete approved package set required to install and operate the public Vault. It uses JSON-compatible YAML so the installer has no parser dependency before installation.

```bash
_system/deps/install.sh --dry-run
_system/deps/install.sh
_system/deps/install.sh --verify
```

`install.sh` bootstraps Python only when macOS lacks it, then invokes the structured Python installer. Bootstrap calls this entrypoint; it does not own package definitions or install behavior. Agent and skill runtime packages live separately in `_system/agents/_package/defaults/dependencies.json`. Tools installed from managed Code workspaces live in `_system/agents/_package/instance/dependencies/selections.json`.

The Vault and agent manifests are intentionally independent. Each must declare its complete requirements and must not inherit, deduplicate against, or assume prior installation by the other. A package needed by both belongs in both manifests. This deliberate duplication keeps public Vault bootstrap and the private agent package independently installable.

Adding a package is approval for default-apply installation on its listed platforms. Recipes are structured and may use only supported package managers. Successful verification is merged into `_system/local/dependencies.lock.json`; desired or failed packages are never recorded as installed.
