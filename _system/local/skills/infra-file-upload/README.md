# Infra File Upload local configuration

This folder records instance ownership for `$infra-file-upload`. The installed `ctx9-content` command and its Content configuration own the API, rendered, and public-file origins. Authentication is stored through `ctx9-content login --token-stdin` or supplied by Secret Bindings.

Do not duplicate repository paths, bucket values, domains, or credentials here. Content owns object storage and delivery policy; the skill owns only the intent-specific safety defaults.
