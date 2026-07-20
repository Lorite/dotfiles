#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/setup-morning-briefing-server.sh
# Idempotent bootstrap for running the lorite-morning-briefing on the HOME SERVER
# (headless, Syncthing vault, no Obsidian GUI) at 03:00 daily. Safe to re-run.
#
# It sets up everything EXCEPT Claude Code auth (that needs you):
#   1. a read-only side clone of the vault (git audit source — Syncthing excludes .git/)
#   2. the host env file pointing the briefing at that clone
#   3. the systemd user service + timer, with a 03:00 drop-in override
#   4. enables the timer ONLY when OpenCode or Claude Code is installed (OpenCode first,
#      Claude fallback — the briefing uses tools/lorite/lorite-llm.sh)
#
# Run on the server:  ssh <server> 'bash ~/git/dotfiles/tools/lorite/setup-morning-briefing-server.sh'
set -euo pipefail

VAULT="$HOME/git/lorite-obsidian-notes"                       # Syncthing content copy
CLONE="$HOME/git/lorite-obsidian-notes-audit"                 # git-history side clone
REMOTE="git@github.com:Lorite/lorite-obsidian-notes.git"
DOTFILES="$HOME/git/dotfiles"
UNIT_DIR="$HOME/.config/systemd/user"
ENV_DIR="$HOME/.config/lorite"

say() { printf '\033[0;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup] WARN:\033[0m %s\n' "$*"; }

# 0. Sanity: vault present (Syncthing) + dotfiles present
[ -d "$VAULT" ] || { warn "vault not found at $VAULT — is Syncthing syncing it here?"; exit 1; }
[ -d "$DOTFILES/.git" ] || { warn "dotfiles not a git repo at $DOTFILES"; exit 1; }
say "pulling latest dotfiles"
git -C "$DOTFILES" pull --ff-only --quiet || warn "dotfiles pull failed (using current checkout)"

# Sync the Claude agents this briefing delegates to (lorite-concept-note-writer).
# ~/.claude/skills is symlinked to dotfiles (live), but agents are COPIED with a
# Copilot→Claude tool-name translation, so reuse install.sh's own sync function.
if [ -d "$HOME/.claude/agents" ] || [ -L "$HOME/.claude/skills" ]; then
    FNS="$(mktemp)"
    awk '/^(print_info|print_success|print_warning|print_error|backup_path|normalize_frontmatter_for_claude|sync_copilot_to_claude)\(\)/,/^}/' \
        "$DOTFILES/install.sh" > "$FNS" 2>/dev/null || true
    if grep -q sync_copilot_to_claude "$FNS"; then
        ( GREEN=""; YELLOW=""; RED=""; BLUE=""; NC=""; DOTFILES_DIR="$DOTFILES"
          # shellcheck disable=SC1090
          source "$FNS"
          sync_copilot_to_claude "$DOTFILES/.copilot/agents" "$HOME/.claude/agents" "Copilot agents" ) \
          && say "synced Claude agents (~/.claude/agents)" || warn "agent sync failed (concept notes will be skipped — non-blocking)"
    fi
    rm -f "$FNS"
fi

# 1. Read-only side clone for the commit audit (Syncthing does NOT sync .git/)
if [ ! -d "$CLONE/.git" ]; then
    say "cloning vault history → $CLONE"
    git clone --quiet "$REMOTE" "$CLONE"
else
    say "side clone exists — fetching"
    git -C "$CLONE" fetch --quiet origin || warn "fetch failed"
fi

# 2. Host env file: point the briefing's git audit at the side clone
mkdir -p "$ENV_DIR"
cat > "$ENV_DIR/morning-briefing.env" <<EOF
# Home-server overrides for lorite-morning-briefing (read by the systemd service).
# The vault content root ($VAULT) is the Syncthing copy; its git history is here:
LORITE_VAULT_GIT=$CLONE
OBSIDIAN_GUI=0
EOF
say "wrote $ENV_DIR/morning-briefing.env (LORITE_VAULT_GIT=$CLONE, OBSIDIAN_GUI=0)"

# 3. Install the service + timer + a 03:00 drop-in (overrides the laptop's 06:00)
mkdir -p "$UNIT_DIR" "$UNIT_DIR/lorite-morning-briefing.timer.d"
cp "$DOTFILES/tools/lorite/lorite-morning-briefing.service" \
   "$DOTFILES/tools/lorite/lorite-morning-briefing.timer" "$UNIT_DIR/"
cat > "$UNIT_DIR/lorite-morning-briefing.timer.d/override.conf" <<'EOF'
# Home server runs at 03:00 (empty OnCalendar= first clears the shipped 06:00).
[Timer]
OnCalendar=
OnCalendar=*-*-* 03:00:00
EOF
systemctl --user daemon-reload
say "installed service + timer + 03:00 drop-in"

# 4. Enable only when OpenCode or Claude Code is available (the briefing uses lorite-llm.sh
# which prefers opencode, falls back to claude). Check ~/.local/bin explicitly — a non-login
# shell often lacks it on PATH, and the service itself sets PATH=%h/.local/bin:...
has_llm=0
if command -v opencode >/dev/null 2>&1 || [ -x "$HOME/.opencode/bin/opencode" ]; then
    has_llm=1
elif command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ]; then
    has_llm=1
fi
if [[ $has_llm -eq 1 ]]; then
    systemctl --user enable --now lorite-morning-briefing.timer
    say "ENABLED lorite-morning-briefing.timer — next run:"
    systemctl --user list-timers lorite-morning-briefing.timer --no-pager || true
    say "test now:  systemctl --user start lorite-morning-briefing.service"
else
    warn "No LLM client found (opencode preferred, claude fallback) — timer NOT enabled."
    warn "Install OpenCode (preferred):  curl -fsSL https://opencode.ai/install | bash"
    warn "Or install Claude Code:         curl -fsSL https://claude.ai/install.sh | bash"
    warn "Then re-run: bash ~/git/dotfiles/tools/lorite/setup-morning-briefing-server.sh"
fi
