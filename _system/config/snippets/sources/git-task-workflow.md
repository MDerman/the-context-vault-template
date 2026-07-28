## Git Coordination

Before making task-related file changes:

1. Run `git fetch origin --prune`.
2. Confirm the current branch is the repository's expected working branch, then compare `HEAD` with its configured upstream.
3. If the checkout is clean and behind, fast-forward to the upstream branch.
4. Unrelated dirty or newly appearing files are expected in a shared checkout. Continue when they do not overlap the task's files, and never stage, overwrite, or revert them.
5. If the current branch is ahead, divergent, or cannot be updated safely, identify and reconcile the Git state without discarding other work before editing.

After completing a user-requested unit of work:

1. Stage only that unit's files and commit them, even when unrelated changes remain or appear concurrently. A dirty tree elsewhere is not a reason to skip the commit.
2. If unrelated paths are already staged, keep them staged but exclude them from the unit's commit by committing only the task's paths.
3. Run `git fetch origin --prune` again.
4. If the upstream branch advanced, integrate it into the current branch; resolve conflicts only when they are task-scoped and the intended result is clear.
5. If unrelated dirty work blocks integration, or conflict intent is unclear, preserve all work and report the blocker without overwriting, stashing, resetting, or including unrelated changes.
6. Push the current branch to its configured upstream. If the push is rejected because the upstream advanced again, fetch, integrate, and retry without forcing.
