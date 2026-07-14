#!/usr/bin/env bash
# Canonical copy of the home-server Remote Control wrapper.
# Lives on the always-on server at ~/.local/bin/claude-rc-loop.sh and is launched by the
# claude-rc*.service systemd *user* units (claude-rc.service = dotfiles,
# claude-rc-vault.service = Obsidian vault; both in this dir).
#
# Runs Claude Code Remote Control in SERVER MODE for ONE workspace directory: it waits for
# connections and lets the phone / claude.ai/code spawn multiple on-demand sessions
# (--spawn same-dir, up to the default capacity of 32). Each Remote Control server is bound
# to a SINGLE directory, so one wrapper instance == one "New session" workspace in the app.
# Run a second unit pointing at another dir to expose a second workspace. Restarts if it
# exits (Remote Control quits the process after a ~10 min network outage).
# See CLAUDE.md -> "On-the-go access (home server)".
#
# Usage: claude-rc-loop.sh [WORKDIR] [PREFIX]
#   WORKDIR  workspace directory to serve   (default: ~/git/dotfiles)
#   PREFIX   session-name prefix in the app (default: basename of WORKDIR)
export PATH="$HOME/.local/bin:$PATH"
WORKDIR="${1:-$HOME/git/dotfiles}"
PREFIX="${2:-$(basename "$WORKDIR")}"
cd "$WORKDIR" || exit 1
while true; do
    claude remote-control --spawn same-dir --remote-control-session-name-prefix "$PREFIX"
    echo "[claude-rc] server ($WORKDIR) exited at $(date -Is); restarting in 10s"
    sleep 10
done
