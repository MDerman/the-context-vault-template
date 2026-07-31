# Manage UTM Tracking Links Config

Private instance config for `marketing-manage-utm-tracking-links`.

`private/config.json` defines the provider adapter, logical repository ID, env
loader, Shlink variable names, allowed short domains, management host, and
optional protected slugs. Domain entries use this shape:

```json
{
  "domain_env": "SHLINK_DOMAIN_ENV_NAME",
  "protected_slugs": ["important-link"]
}
```

Values remain owned by K3s repository env; this config stores key names and
non-secret slug policy only. An empty `protected_slugs` list is valid.

Repository path resolves through `_system/config/infra-code-folder-and-computer-topology/private/repositories.json`. Override config for testing with `UTM_LINKS_CONFIG` or `--config`.
