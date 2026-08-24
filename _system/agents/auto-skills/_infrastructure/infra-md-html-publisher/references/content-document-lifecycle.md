# Content document lifecycle

`ctx9-content` is the sole command. Configuration uses the Content API, rendered, and public-file origins; authenticate with `ctx9-content login --token-stdin`.

Discover documents with `ctx9-content list --kind document --json`, then inspect one with `ctx9-content read <id> --json` or `ctx9-content metadata <id> --json`. Download canonical source with `ctx9-content download <id> --version <n> --output <path>`.

Publish uses Content `document` with rendered presentation. Use `unlisted` by default for shareable internal documents and `public` only when the request clearly authorizes public listing. Stable Content identity comes from the returned ID, not a local path mapping.

Create a new version with the current ETag to keep the same content identity. Use `ctx9-content delete <id> --etag <etag> --yes` only for exact, explicitly requested tombstoning. Historical URLs in dated records remain evidence, not active compatibility routes.
