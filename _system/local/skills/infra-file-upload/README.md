# Infra File Upload local configuration

This folder records instance ownership for `$infra-file-upload`. The private topology registry must contain logical repository ID `file-upload`; that repository's `.env.base` owns bucket name, root prefix, and public base URL. Bucket-scoped `R2_FILE_UPLOAD_ACCESS_KEY_ID` and `R2_FILE_UPLOAD_SECRET_ACCESS_KEY` credentials and the optional Cloudflare provisioning token remain owned by the registered k3s env loader.

Do not duplicate repository paths, bucket values, domains, or credentials here. Update topology when the checkout moves and update the uploader repository's env workflow when its public storage configuration changes.
