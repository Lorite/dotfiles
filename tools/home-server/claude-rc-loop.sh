#!/usr/bin/env bash
# Canonical copy of the home-server Remote Control wrapper.
# Lives on the always-on server at ~/.local/bin/claude-rc-loop.sh and is launched by the
# claude-rc.service systemd *user* unit (see claude-rc.service in this dir).
#
# Runs Claude Code Remote Control in SERVER MODE: it waits for connections and lets the
# phone / claude.ai/code spawn multiple on-demand sessions (--spawn same-dir, up to the
# default capacity of 32). Restarts it if it exits (Remote Control quits the process after
# a ~10 min network outage). See CLAUDE.md → "On-the-go access (home server)".
export PATH="$HOME/.local/bin:$PATH"
cd "$HOME/git/dotfiles" || exit 1
while true; do
    claude remote-control --spawn same-dir --remote-control-session-name-prefix phd
    echo "[claude-rc] server exited at $(date -Is); restarting in 10s"
    sleep 10
done
