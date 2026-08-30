## Terminal

Daily-use keybindings for fzf, tmux, cmux, and btop are consolidated in [[terminal-keybindings]].

Fleet architecture and maintenance:

- [[cmux-tmux-terminal-workspaces|Warp, cmux, and tmux Terminal Workspaces]]: canonical deployment, verification, persistence, and rollback.
- [[README-warp-cmux-execution-chain|Warp and cmux Execution Chain]]: machine and frontend boundaries.
- [[README-ssh-development-previews|SSH Development Previews]]: worker-originated reverse forwarding to Mattbook localhost.
- [[README-workmux-notifications|Workmux Agent Notifications]]: retired notification system and disabled-state verification.

The public Vault dependency manifest is `_system/deps/packages.yaml`. Use its installer for `fzf` and other approved public tools:

```bash
_system/deps/install.sh --dry-run
_system/deps/install.sh
_system/deps/install.sh --verify
```

Fleet tmux, btop, Starship, workmux, Warp, and cmux configuration is owned by `$infra-manage-fleet-terminal-workspaces`.

## Useful commands

| Command | Action |
| --- | --- |
| `cd ~` | Go to the current user's home directory. |
| `networkquality` | Run the built-in macOS network quality test. |
| `killall Spotify` | Stop all Spotify processes. |
