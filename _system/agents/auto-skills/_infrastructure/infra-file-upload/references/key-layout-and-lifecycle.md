# Key layout and lifecycle

Every key stays below the configured root prefix:

```text
<root>/pr/<repository>/<pr-or-branch>/<filename>
<root>/public/<project>/<group>/<filename>
<root>/lead-magnets/<project>/<offer-slug>/<filename>
```

Use lower-kebab path segments. Keep the original extension and choose a clear filename. Reject absolute paths, empty or dot segments, traversal, separators embedded in a segment, and keys outside the configured root.

Prefer immutable versioned names such as `guide-v2.pdf`, a release identifier, or a content hash when content may change. Public and lead-magnet assets receive immutable cache headers only when their filenames are recognizably versioned. PR evidence receives shorter caching unless versioned.

The CLI refuses existing keys by default. `--replace` is for deliberate exact replacement, not routine publishing. Listing remains scoped to the configured root and supplied category/project/group filters. Deletion accepts one exact in-root key and requires `--yes`; prefix and bulk deletion are not supported.

The public URL grants no secrecy. Email confirmation records and proves the email before delivery, but a public R2 URL can still be shared or guessed. Protected delivery needs a separate signed-URL or authenticated design.
