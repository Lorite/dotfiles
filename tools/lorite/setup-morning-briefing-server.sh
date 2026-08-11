#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/setup-morning-briefing-server.sh
# Idempotent bootstrap for running the lorite-morning-briefing on the HOME SERVER
# (headless, Syncthing vault, no Obsidian GUI) as the last job of the 01:00
# lorite-nightly.target batch. Safe to re-run.
#
# It sets up everything EXCEPT Claude Code auth (that needs you):
#   1. pulls latest dotfiles and runs install.sh (installs opencode, lorite-llm, syncs agents)
#   2. a read-only side clone of the vault (git audit source — Syncthing excludes .git/)
#   3. the host env file pointing the briefing at that clone
#   4. the systemd user service + the lorite-nightly batch timer/target
#   5. enables the timer ONLY when OpenCode or Claude Code is installed (OpenCode first,
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

# 0b. Run install.sh to get OpenCode, lorite-llm, and synced agents on this machine.
# install.sh is idempotent and skips apt/nvm/starship/oh-my-zsh when already present,
# so it's safe to re-run on the server. The sudo apt-get at the top will no-op on a
# headless server with nothing to upgrade.
say "running install.sh (OpenCode + lorite-llm + agent sync)..."
bash "$DOTFILES/install.sh" 2>&1 | sed 's/^/  /' || warn "install.sh reported issues (non-fatal, continuing)"

# 1. Vault git history. Since 2026-08-12 the vault directory itself is a real clone of
# $REMOTE on this host (Syncthing excludes .git/, so the repo is local to the server),
# and vault-git-backup.service commits and pushes it nightly. The old read-only side
# clone at $CLONE is therefore redundant and is retired here: one copy of the history
# instead of two (it was 2.4 GB of duplicate objects).
if [ ! -d "$VAULT/.git" ]; then
    warn "$VAULT is not a git repo — the commit audit will be skipped."
    warn "Fix: clone $REMOTE elsewhere and move its .git into $VAULT, then 'git reset --mixed HEAD'."
else
    say "vault git history present in $VAULT — fetching"
    git -C "$VAULT" config core.filemode false   # Syncthing sets its own permission bits
    git -C "$VAULT" fetch --quiet origin || warn "fetch failed"
fi
if [ -d "$CLONE/.git" ]; then
    warn "legacy side clone still present at $CLONE — it is no longer used; remove it to reclaim disk."
fi

# 2. Host env file: point the briefing's git audit at the vault's own repo
mkdir -p "$ENV_DIR"
cat > "$ENV_DIR/morning-briefing.env" <<EOF
# Home-server overrides for lorite-morning-briefing (read by the systemd service).
# The vault content root ($VAULT) is the Syncthing copy, and since 2026-08-12 it is
# also a real clone of the GitHub remote, so content and history are the same path:
LORITE_VAULT_GIT=$VAULT
OBSIDIAN_GUI=0
EOF
say "wrote $ENV_DIR/morning-briefing.env (LORITE_VAULT_GIT=$VAULT, OBSIDIAN_GUI=0)"

# 3. Install the service + the nightly batch units. The briefing runs LAST in the
# lorite-nightly.target 01:00 batch (After=dotfiles-pull inside the service), so the
# standalone briefing timer and the old per-host time override are removed here.
mkdir -p "$UNIT_DIR"
cp "$DOTFILES/tools/lorite/lorite-morning-briefing.service" \
   "$DOTFILES/tools/home-server/lorite-nightly.timer" \
   "$DOTFILES/tools/home-server/lorite-nightly.target" "$UNIT_DIR/"
rm -rf "$UNIT_DIR/lorite-morning-briefing.timer.d"
systemctl --user disable --now lorite-morning-briefing.timer 2>/dev/null || true
rm -f "$UNIT_DIR/lorite-morning-briefing.timer"
systemctl --user daemon-reload
say "installed service + lorite-nightly batch units (old standalone timer removed)"

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
    systemctl --user enable --now lorite-nightly.timer
    say "ENABLED lorite-nightly.timer (batch runs the briefing last) — next run:"
    systemctl --user list-timers lorite-nightly.timer --no-pager || true
    say "test now:  systemctl --user start lorite-nightly.target   (whole batch)"
    say "      or:  systemctl --user start lorite-morning-briefing.service   (briefing only)"
else
    warn "No LLM client found (opencode preferred, claude fallback) — timer NOT enabled."
    warn "Install OpenCode (preferred):  curl -fsSL https://opencode.ai/install | bash"
    warn "Or install Claude Code:         curl -fsSL https://claude.ai/install.sh | bash"
    warn "Then re-run: bash ~/git/dotfiles/tools/lorite/setup-morning-briefing-server.sh"
fi
