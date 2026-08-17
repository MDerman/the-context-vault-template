---
name: infra-file-upload
description: Use this skill whenever you need to upload a video or file when requested for PRs or for requested public or lead magnet resources.
---

# Infra · File Upload

Upload intentionally public files through the standalone `file-upload` CLI. Read `_system/local/skills/infra-file-upload/README.md`, [[references/environment-and-bucket|Environment and Bucket]], and [[references/key-layout-and-lifecycle|Key Layout and Lifecycle]] before the first upload in a task.

## Workflow

1. Classify the request as `pr`, `public`, or `lead-magnets`.
2. Inspect the local file name, type, and relevant contents for credentials, private data, hidden metadata, or material the user did not intend to publish. Stop on a meaningful risk; do not silently redact.
3. Resolve logical repository ID `file-upload` through the topology registry. Do not hardcode a checkout path.
4. Run `file-upload doctor` before the first mutation in a task.
5. Choose the narrowest lower-kebab `project` and `group`. For PR evidence, use the repository and exact `pr-<number>` or branch slug.
6. Upload without `--replace` unless the user explicitly intends to overwrite the exact existing key. Prefer a versioned filename for replacement.
7. Return the stable public URL, exact R2 object key, bucket, byte size, and MIME type. Preserve the local source unless the user asks to remove it.

```bash
file-upload upload ./evidence.mp4 --category pr --project repo --group pr-123
file-upload upload ./guide.pdf --category public --project project --group guides --json
file-upload upload ./resource.pdf --category lead-magnets --project project --group offer-slug
```

## Safety

- Public upload is an external mutation. The request must clearly authorize publishing the file.
- Never upload env files, credentials, private keys, authentication exports, cookies, database dumps, or unreviewed archives.
- Replacement and deletion require an exact key and explicit intent. Delete one object only with `file-upload delete <exact-key> --yes`; never infer a prefix deletion.
- Do not create a bucket, enable public access, or bind a custom domain as part of an ordinary upload. Those are separate infrastructure rollout actions.
- Use `$marketing-lead-magnets` when the asset belongs to a signup, confirmation, download, or VSL flow.

If `doctor` fails, report the missing variable names or connectivity boundary without printing values. Do not create plaintext secret copies or switch buckets silently.
