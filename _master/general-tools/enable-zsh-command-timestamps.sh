#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
START_MARKER="# >>> cursor-zsh-command-timestamps >>>"
END_MARKER="# <<< cursor-zsh-command-timestamps <<<"

if [[ ! -f "$ZSHRC" ]]; then
  touch "$ZSHRC"
fi

existing_content="$(<"$ZSHRC")"
if [[ "$existing_content" == *"$START_MARKER"* ]]; then
  echo "Timestamp config already exists in $ZSHRC"
  echo "Reload with: source \"$ZSHRC\""
  exit 0
fi

cat >> "$ZSHRC" <<'EOF'

# >>> cursor-zsh-command-timestamps >>>
setopt EXTENDED_HISTORY
HISTFILE="${HISTFILE:-$HOME/.zsh_history}"
HISTSIZE=100000
SAVEHIST=100000
if [[ -n "${PROMPT:-}" ]]; then
  PROMPT='[%D{%Y-%m-%d %H:%M:%S}] '"$PROMPT"
else
  PROMPT='[%D{%Y-%m-%d %H:%M:%S}] %n@%m %1~ %# '
fi
# <<< cursor-zsh-command-timestamps <<<
EOF

echo "Added timestamp config to $ZSHRC"
echo "Open a new terminal or run: source \"$ZSHRC\""
