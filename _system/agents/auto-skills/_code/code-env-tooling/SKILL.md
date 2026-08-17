---
name: code-env-tooling
description: Use when adding, changing, loading, syncing, encrypting, decrypting, or troubleshooting environment variables; covers .env.base workflow, the ctx2 CLI and env-tooling compatibility alias, k3s env scripts, cicd env scripts, and run-after-updating-env.sh.
---

# Code · Env Tooling

## Critical Rule

Always add new environment variables to `.env.base` first in the repo that owns those variables. If repo has no `.env.base`, ask user what env workflow to use before adding variables.

Do not add new keys only to `.env`, encrypted env files, generated final env files, app-local env overlays, or CI settings unless user explicitly asks for that target too.

## Repo Patterns

### K3s Preset Repos

Use this pattern in repos that keep project-level `.env.base` and `.env` files
and use the `k3s` ctx2 compatibility preset:

1. Add new keys to `.env.base`.
2. Run:

```bash
./sync-env-files.sh
```

3. If `load-env.sh` reads encrypted final env or deploy scripts need fresh encrypted values, run:

```bash
./encrypt-env-files.sh
```

These wrappers call ctx2 with the `k3s` preset. `sync k3s` syncs `.env` from `.env.base`. `encrypt k3s` layers non-empty `.env` overrides on top of `.env.base`, writes `.env.final.tmp`, and encrypts `.env.final.sops`.

### CICD Preset Repos

Use this pattern in repos that keep environment files inside a `cicd/`
directory and use the `cicd` ctx2 compatibility preset:

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

`run-after-updating-env.sh` calls `ctx2 post-update cicd --dir "$SCRIPT_DIR"`. It syncs env files, encrypts SOPS envs, decrypts generated envs, and refreshes filtered Next.js env files for staging/prod when relevant.

## Ctx2 compatibility CLI

Locate ctx2 from the current repo wrapper or `CTX2_BIN`; use `ENV_TOOLING_BIN` only as the temporary compatibility override.
Core commands:

```bash
ctx2 load cicd --dir /path/to/cicd --environment dev1 --emit-shell
ctx2 post-update cicd --dir /path/to/cicd dev1
ctx2 sync cicd --dir /path/to/cicd
ctx2 encrypt cicd --dir /path/to/cicd dev1
ctx2 decrypt cicd --dir /path/to/cicd dev1
ctx2 create-next cicd --dir /path/to/cicd production
ctx2 load k3s --dir /path/to/k3s-env-dir --emit-shell
ctx2 sync k3s --dir /path/to/k3s-env-dir
ctx2 encrypt k3s --dir /path/to/k3s-env-dir
ctx2 load default --dir /path/to/shared-env-dir --emit-shell
```

Repo wrappers should stay thin: resolve the repo-local directory, locate `CTX2_BIN` with the temporary `ENV_TOOLING_BIN` fallback, call this CLI, and source emitted shell when needed. Env merge, SOPS decrypt/encrypt, sync, and post-update behavior belong in ctx2.

## Portable Binary Resolution

Wrappers such as `load-env.sh`, `sync-env-files.sh`, and `encrypt-env-files.sh` should resolve ctx2 in this order:

1. `CTX2_BIN` if set.
2. `ENV_TOOLING_BIN` while the compatibility window remains open.
3. Logical repository ID `ctx2` from the private topology registry when the vault is available.
4. Sibling checkout `../ctx2/bin/ctx2`, or a documented project fallback when the wrapper must also work without the vault.

This keeps the skill generic, lets the fleet registry own the current checkout path, and preserves standalone repo wrappers without personal absolute paths.

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
