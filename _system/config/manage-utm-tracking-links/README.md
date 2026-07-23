# Manage UTM Tracking Links Config

Private instance config for `manage-utm-tracking-links`.

`private/config.json` defines provider adapter, logical repository ID, env loader, Shlink variable names, allowed short domains, management host, and protected permanent slugs. Values remain owned by K3s repository env; this config stores key names only.

Repository path resolves through `_system/config/code-folder-and-computer-topology/private/repositories.json`. Override config for testing with `UTM_LINKS_CONFIG` or `--config`.

