# Infra File Upload local configuration

This folder records instance ownership for `$infra-file-upload`. The installed `publish` command and its Publisher configuration own the API, rendered, and public-file origins. Authentication is stored through `publish login --token-stdin` or supplied through the Publisher environment workflow.

Do not duplicate repository paths, bucket values, domains, or credentials here. Publisher owns object storage and delivery policy; the skill owns only the intent-specific safety defaults.
