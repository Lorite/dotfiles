#!/usr/bin/env bash
# Keep this host's vault checkout aligned with what the home server committed.
#
# WHY THIS EXISTS. The vault is one git repo, but only the home server commits it
# (vault-git-backup.service, 01:00) and pushes. Syncthing replicates the note CONTENT to
# every other host, while .git/ is excluded (first line of .stignore), so each host keeps
# its own independent clone. Nothing ever pulled on the laptop: its HEAD sat at the
# 2026-08-12 backup while its working tree carried today's synced content, so `git status`
# reported ~953 changes that were, almost entirely, work the server had already committed.
# Realigning HEAD dropped it to 248 real ones.
#
# reset --mixed moves HEAD and the index and NEVER touches the working tree, so genuinely
# uncommitted edits survive untouched. Local COMMITS would not, which is what the guard
# below is for: this host is a follower, and a commit here means someone did something the
# script must not silently discard.
set -euo pipefail

VAULT="${LORITE_VAULT:-$HOME/git/lorite-obsidian-notes}"
cd "$VAULT" 2>/dev/null || { echo "vault-git-track: no vault at $VAULT" >&2; exit 0; }

# Offline / server down is not an error worth failing the unit over.
git fetch --quiet origin 2>/dev/null || { echo "vault-git-track: fetch failed, skipping" >&2; exit 0; }

ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
if [ "$ahead" != 0 ]; then
    echo "vault-git-track: $ahead local commit(s) not on origin/main - refusing to reset." >&2
    echo "  Push or drop them and the timer resumes. HEAD=$(git rev-parse --short HEAD)" >&2
    exit 0
fi

before=$(git rev-parse --short HEAD)
git reset --mixed --quiet origin/main
after=$(git rev-parse --short HEAD)
if [ "$before" != "$after" ]; then
    echo "vault-git-track: $before -> $after ($(git status --porcelain -uall | wc -l) real changes)"
fi
