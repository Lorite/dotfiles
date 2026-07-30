#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/home-server/dotfiles-pull.sh
# Daily fast-forward pull of the dotfiles repo on the home server (lorite-thinkcentre-m720q).
# ~/.claude/CLAUDE.md and the skills are symlinks into the repo, so a pull alone refreshes them.
# This script NEVER runs install.sh: agent copies under ~/.claude/agents/ are the only thing a
# pull does not refresh, install.sh has a history of unattended-run bugs, and this host's uutils
# coreutils make silent damage worse (see the dotfiles CLAUDE.md, 2026-07-25). When a pull brings
# changes under .copilot/agents/, it writes a flag file instead and leaves the run to a human.
# Install at ~/.local/bin/dotfiles-pull.sh (chmod +x), driven by dotfiles-pull.timer.

set -euo pipefail

REPO="$HOME/git/dotfiles"
STATE_DIR="$HOME/.local/state/dotfiles-pull"
FLAG="$STATE_DIR/install-sh-needed"

mkdir -p "$STATE_DIR"
cd "$REPO"

old_head=$(git rev-parse HEAD)
# --ff-only fails (and the service shows as failed) if the checkout ever diverges from origin.
git pull --ff-only
new_head=$(git rev-parse HEAD)

if [ "$old_head" = "$new_head" ]; then
    echo "Already up to date at ${new_head:0:7}."
else
    echo "Pulled ${old_head:0:7}..${new_head:0:7}."
    if git diff --name-only "$old_head" "$new_head" -- .copilot/agents/ | grep -q .; then
        {
            echo "Agent definitions changed in ${old_head:0:7}..${new_head:0:7} (pulled $(date -Is))."
            echo "Run install.sh manually in $REPO to refresh ~/.claude/agents/:"
            git diff --name-only "$old_head" "$new_head" -- .copilot/agents/
        } > "$FLAG"
        echo "WARNING: .copilot/agents/ changed. Flag written to $FLAG. Run install.sh manually."
    fi
fi

if [ -f "$FLAG" ]; then
    echo "REMINDER: pending manual install.sh run. See $FLAG:"
    cat "$FLAG"
fi
