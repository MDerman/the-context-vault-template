# Vault Git Coordination

GitHub `origin/master` is the durable coordination point. Primary uses a full checkout; workers use partial sparse clones containing root files, `.agents`, `_system`, and versioned `.githooks`.

Repository `AGENTS.md` defines the required interactive workflow: fetch and compare before editing, preserve unrelated dirty work, then stage the completed unit, commit, fetch and merge concurrent remote work, and push explicitly.

```sh
vault git-preflight
vault worker-sync install-hooks --apply
vault worker-sync bootstrap WORKER_ID --apply
vault worker-sync bootstrap WORKER_ID --provision-disabled --apply
```

Normal worker bootstrap rejects disabled machines. The explicit `--provision-disabled` form exists only for new-machine onboarding, allowing the sparse clone and its local verification to be completed before fleet enablement. It refuses an already enabled target.

Versioned hooks live in `.githooks`:

- `post-commit`: run the required Git LFS post-commit hook only.
- `post-checkout`, `post-merge`, `post-rewrite`: refresh dependency-backed auto-skill projections and global skill links.
- `pre-push`: enforce the pointer-only media guard when configured; ordinary Git LFS otherwise.

No hook, service, timer, or fleet command automatically commits, pushes, stashes, rebases, resets, or creates merge commits. The daily refresh may fetch `origin` and attempt a strict fast-forward of `master`; Git preserves unrelated dirty files and aborts before updating when incoming paths overlap local work. A blocked update becomes a warning so local generated views still refresh. `vault worker-sync` is retained only for explicit hook installation and sparse worker bootstrap.

Dirty or divergent state is never stashed, reset, rebased, overwritten, or silently included. When `origin/master` advances after a task commit, merge it explicitly; stop and report if unrelated work blocks the merge or conflict intent is unclear.
