Terminal shortcuts are consolidated here. Setup, architecture, recovery, and daily commands remain in [[_system/docs/terminal/README|Terminal]].

## fzf

`fzf` turns a list from standard input into an interactive fuzzy picker. The Vault dependency installer provides the binary on macOS and Linux.

Verify it:

```bash
fzf --version
```

### Shell integration

The binary works immediately. Shell keybindings and fuzzy completion need shell integration.

For the current zsh session:

```zsh
source <(fzf --zsh)
```

To enable it for future zsh sessions, add that line to `~/.zshrc`. For bash, use `eval "$(fzf --bash)"` in `~/.bashrc`.

| Shortcut | Action |
| --- | --- |
| `Ctrl+R` | Search shell command history and place the chosen command on the prompt. |
| `Ctrl+T` | Search files and directories and paste the selection at the cursor. |
| `Alt+C` | Search directories below the current directory and change into the selection. |

On macOS, `Alt` is the Option key. The terminal must send Option as Meta/Esc for `Alt+C` to reach the shell.

### Picker controls

| Key | Action |
| --- | --- |
| `Up`, `Down` | Move through results. |
| `Ctrl+K`, `Ctrl+J` | Move up or down without leaving the home row. |
| `Enter` | Accept the current selection. |
| `Tab`, `Shift+Tab` | Toggle a result in multi-select mode and move down or up. |
| `Esc`, `Ctrl+C` | Cancel without selecting. |

### Search syntax

| Query | Match behavior |
| --- | --- |
| `foo bar` | Match both terms in any order. |
| `'foo\ bar` | Exact phrase match; the backslash keeps the space inside one term. |
| `^foo` | Match at the beginning. |
| `bar$` | Match at the end. |
| `!draft` | Exclude matches containing the term. |
| `foo | bar` | Match either term. |

### Useful patterns

Pick a Vault file:

```bash
rg --files | fzf
```

Preview text while selecting:

```bash
rg --files | fzf --preview 'sed -n "1,160p" {}'
```

Pick a Git branch:

```bash
git branch --all --format='%(refname:short)' | fzf
```

Fuzzy completion is triggered by `**` followed by `Tab` after shell integration is loaded. Common examples are `cd **<Tab>`, `vim **<Tab>`, and `ssh **<Tab>`.

Use `FZF_DEFAULT_OPTS` only for preferences that should affect every picker. Put command-specific options on the command itself so unrelated pickers stay predictable.

## tmux keybindings

Managed terminal workspaces keep tmux's default prefix: press `Ctrl+b`, release it, then press the command key.

### Managed windows and persistence

| Shortcut | Action |
| --- | --- |
| `Ctrl+b 0` | Open managed `0:btop`. |
| `Ctrl+b 1` | Open managed `1:shell`. |
| `Ctrl+b c` | Create a window; its name follows the foreground process. |
| `Ctrl+b n` | Select the next window. |
| `Ctrl+b p` | Select the previous window. |
| `Ctrl+b l` | Return to the last selected window. |
| `Ctrl+b ,` | Rename the current window. |
| `Ctrl+b w` | Open the interactive window/session tree. |
| `Ctrl+b &` | Confirm and close the current window. |
| `Ctrl+b r` | Reload `~/.tmux.conf`. |
| `Ctrl+b Ctrl+s` | Save a tmux-resurrect snapshot now. |
| `Ctrl+b Ctrl+r` | Restore the latest tmux-resurrect snapshot. |
| `Ctrl+b d` | Detach this client while the session and its programs continue. |

### Panes and copy mode

| Shortcut | Action |
| --- | --- |
| `Ctrl+b %` | Split the current tmux pane left/right. |
| `Ctrl+b "` | Split the current tmux pane top/bottom. |
| `Ctrl+b Arrow` | Move focus to the pane in that direction. |
| `Ctrl+b o` | Move to the next pane. |
| `Ctrl+b z` | Zoom or unzoom the current pane. |
| `Ctrl+b x` | Confirm and close the current pane. |
| `Ctrl+b [` | Enter copy mode for scrollback and selection. |
| `Ctrl+b ]` | Paste the most recently copied tmux buffer. |
| `Ctrl+b ?` | Show all active tmux keybindings. |
| `Ctrl+b :` | Open the tmux command prompt. |

The managed initial layout uses windows rather than tmux splits. cmux splits are a separate outer layer; see [[terminal-keybindings#cmux keybindings|cmux keybindings]].

### Sessions and recovery

Use `workmux <machine-id>` to validate, repair, and attach the managed session for a machine. `tmux ls` lists sessions without attaching.

Closing Warp, cmux, or SSH removes only the tmux client. The tmux server and programs continue while the owning machine and tmux server remain running. A reboot can restore saved layout and working directories, but it cannot restore process memory, unsaved editor state, or live Codex, Claude, and development processes.

Full architecture and recovery: [[cmux-tmux-terminal-workspaces|Warp, cmux, and tmux Terminal Workspaces]].

## cmux keybindings

cmux is the outer macOS workspace and terminal UI. Managed workspaces run tmux inside it, so `Cmd` shortcuts act on cmux and `Ctrl+b` shortcuts act on tmux.

| Shortcut | Action |
| --- | --- |
| `Cmd+T` | Create a surface/tab in the current cmux workspace. |
| `Cmd+D` | Split the cmux pane to the right. |
| `Cmd+Shift+D` | Split the cmux pane downward. |
| `Cmd+Shift+P` | Open the command palette and search current commands and bindings. |
| `Cmd+Shift+,` | Reload cmux and Ghostty configuration. |

Use [[terminal-keybindings#tmux keybindings|tmux keybindings]] for windows and panes inside the managed session. After a cmux relaunch leaves a remote workspace at a plain shell, open the command palette and run `Reconnect machine tmux`.

cmux uses Ghostty's rendering and configuration engine but owns its own windows, workspaces, surfaces, splits, and SSH lifecycle. Full terminology and recovery: [[cmux-tmux-terminal-workspaces|Warp, cmux, and tmux Terminal Workspaces]].

## btop keybindings

Managed workmux sessions keep the resource monitor in tmux window `0:btop`. Press `F1`, `?`, or `h` inside btop for its complete built-in reference.

| Shortcut | Action |
| --- | --- |
| `q`, `Ctrl+C` | Quit btop. |
| `Esc`, `m` | Open or close the main menu. |
| `F1`, `?`, `h` | Show help. |
| `Up`, `Down` | Select a process. |
| `Enter` | Show details for the selected process. |
| `f`, `/` | Filter processes; start with `!` for a regular expression. |
| `Delete` | Clear the process filter. |
| `e` | Toggle the process tree. |
| `Left`, `Right` | Select the previous or next process sort column. |
| `r` | Reverse process sort order. |
| `t` | Send `SIGTERM` to the selected process. |
| `k` | Send `SIGKILL` to the selected process; use carefully. |
| `1` | Show or hide the CPU panel. |
| `2` | Show or hide the memory panel. |
| `3` | Show or hide the network panel. |
| `4` | Show or hide the process panel. |

The managed tmux profile pauses hidden btop work and starts it fresh when `0:btop` is selected. See [[terminal-keybindings#tmux keybindings|tmux keybindings]] for window navigation.

