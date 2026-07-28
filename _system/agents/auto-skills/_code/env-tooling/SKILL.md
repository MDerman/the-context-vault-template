---
name: env-tooling
description: Use when adding, changing, loading, syncing, encrypting, decrypting, or troubleshooting environment variables; covers .env.base workflow, env-tooling CLI, k3s env scripts, cicd env scripts, and run-after-updating-env.sh.
---

# Env Tooling

## Critical Rule

Always add new environment variables to `.env.base` first in the repo that owns those variables. If repo has no `.env.base`, ask user what env workflow to use before adding variables.

Do not add new keys only to `.env`, encrypted env files, generated final env files, app-local env overlays, or CI settings unless user explicitly asks for that target too.

## Repo Patterns

### K3s Preset Repos

Use this pattern in repos that keep project-level `.env.base` and `.env` files
and use the `k3s` env-tooling preset:

1. Add new keys to `.env.base`.
2. Run:

```bash
./sync-env-files.sh
```

3. If `load-env.sh` reads encrypted final env or deploy scripts need fresh encrypted values, run:

```bash
./encrypt-env-files.sh
```

These wrappers call env-tooling with the `k3s` preset. `sync k3s` syncs `.env` from `.env.base`. `encrypt k3s` layers non-empty `.env` overrides on top of `.env.base`, writes `.env.final.tmp`, and encrypts `.env.final.sops`.

### CICD Preset Repos

Use this pattern in repos that keep environment files inside a `cicd/`
directory and use the `cicd` env-tooling preset:

1. Add new keys to `cicd/.env.base`.
2. Run:

```bash
cd /path/to/repo/cicd
./run-after-updating-env.sh
```

For one environment only:

```bash
./run-after-updating-env.sh dev1
```

`run-after-updating-env.sh` calls `env-tooling post-update cicd --dir "$SCRIPT_DIR"`. It syncs env files, encrypts SOPS envs, decrypts generated envs, and refreshes filtered Next.js env files for staging/prod when relevant.

## Env-Tooling CLI

Locate env-tooling from the current repo wrapper or from `ENV_TOOLING_BIN`.
Core commands:

```bash
env-tooling load cicd --dir /path/to/cicd --environment dev1 --emit-shell
env-tooling post-update cicd --dir /path/to/cicd dev1
env-tooling sync cicd --dir /path/to/cicd
env-tooling encrypt cicd --dir /path/to/cicd dev1
env-tooling decrypt cicd --dir /path/to/cicd dev1
env-tooling create-next cicd --dir /path/to/cicd production
env-tooling load k3s --dir /path/to/k3s-env-dir --emit-shell
env-tooling sync k3s --dir /path/to/k3s-env-dir
env-tooling encrypt k3s --dir /path/to/k3s-env-dir
env-tooling load default --dir /path/to/shared-env-dir --emit-shell
```

Repo wrappers should stay thin: resolve repo-local directory, locate `ENV_TOOLING_BIN`, call this CLI, and source emitted shell when needed. Env merge, SOPS decrypt/encrypt, sync, and post-update behavior belong in env-tooling repo.

## Portable Binary Resolution

Wrappers such as `load-env.sh`, `sync-env-files.sh`, and `encrypt-env-files.sh` should resolve env-tooling in this order:

1. `ENV_TOOLING_BIN` if set.
2. Sibling checkout: `../env-tooling/bin/env-tooling`.
3. Project-specific fallback only if the repo documents one.

This keeps sibling repo checkouts portable without hardcoded edits.

## Command Behavior

Use `sync` after adding or removing keys in `.env.base`. It updates target env files to match template structure, keeps comments aligned, fills new keys, and reports orphaned keys that no longer appear in `.env.base`.

Use `encrypt` when generated SOPS files need refreshed encrypted values. For `cicd`, shared `.env` overrides combine with environment overlays. For `k3s`, non-empty `.env` values layer over `.env.base`.

Use `decrypt` for `cicd` when generated decrypted files are needed by follow-on scripts. Treat decrypted files as secret-bearing generated artifacts.

Use `load --emit-shell` when wrapper scripts need to source env values into the current shell. The CLI prints shell code; wrappers should source or eval that output.

Use `post-update cicd` after changing CICD env keys. It runs sync, encrypt, decrypt, and filtered Next.js env generation for the selected environment or all defaults.

Use `create-next cicd` when staging or production Next.js env files need to be regenerated from decrypted CICD env files.

## Markers And Merge Behavior

`.env.base` is structure source. Sync preserves existing target values unless base value must sync.

Markers used by env-tooling:

- `#K!`: force base value into non-shared targets, but not `.env`.
- `#P!`: force base value into non-dev targets.

For k3s, `.env` values override `.env.base` only when non-empty during encryption. For cicd, `.env` shared overrides combine with `.env.<environment>` overlay overrides during encryption.
