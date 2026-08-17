# Environment and bucket

The standalone repository owns generic CLI behavior and these non-secret configuration names in its `.env.base`:

```text
R2_FILE_UPLOAD_BUCKET_NAME
R2_FILE_UPLOAD_ROOT_PREFIX
R2_FILE_UPLOAD_PUBLIC_BASE_URL
```

It loads shared credentials from the registered k3s environment rather than copying them:

```text
CLOUDFLARE_DEFAULT_ACCOUNT_ID
R2_FILE_UPLOAD_ACCESS_KEY_ID
R2_FILE_UPLOAD_SECRET_ACCESS_KEY
```

The R2 credentials must belong to an Object Read & Write token scoped only to the configured file-upload bucket. The loader may source the broader shared environment to activate encrypted values, but the uploader process must receive only an explicit allowlist of its account, R2 credential, bucket, prefix, public-origin, and basic runtime variables.

`CLOUDFLARE_API_TOKEN` is required only by the explicit bucket-provisioning script. Never print values or open plaintext env files. Run `file-upload doctor` to validate configuration, S3-compatible R2 connectivity, bucket access, and public-base configuration by name.

Bucket existence and public custom-domain attachment are separate boundaries. `scripts/ensure-bucket.sh` may verify or create only the exact configured bucket when explicitly approved; it never enables public access or attaches a domain. Ordinary CLI tests use mocks and do not upload to R2.

If the logical repository ID or env loader is missing, stop with setup guidance from the local config instead of inventing a checkout or secret source.
