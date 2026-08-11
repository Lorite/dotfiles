#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/home-server/vault-git-backup.sh
# Installed to ~/.local/bin/ by install.sh. Driven by vault-git-backup.service.
#
# Commits and pushes the Obsidian vault from the home server.
#
# WHY THIS EXISTS (2026-08-12). The vault used to be committed by the obsidian-git
# plugin. On the laptop that was fine, but the home server runs Obsidian headlessly
# under Xvfb once an hour (obsidian-daily-note.service -> with-headless-obsidian.sh),
# and obsidian-git booted with it, found the git repo at the vault root and committed
# the whole vault into a LOCAL-ONLY repo that had no remote and whose own root commit
# said "never commit vault content in this clone". It ran unnoticed for two weeks and
# grew a 1.8 GB .git. The plugin is now uninstalled from the vault (it syncs to every
# device through Syncthing), and committing is this script's job instead: one place,
# one schedule, visible in journalctl.
#
# Ordering: runs inside lorite-nightly.target BEFORE lorite-morning-briefing.service,
# so the briefing's git audit reads commits that already exist.
set -euo pipefail

VAULT="${LORITE_VAULT:-$HOME/git/lorite-obsidian-notes}"
BRANCH="${LORITE_VAULT_BRANCH:-main}"

cd "$VAULT" || { echo "vault not found: $VAULT" >&2; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repo: $VAULT" >&2; exit 1; }

# Syncthing sets its own permission bits, so every file otherwise reads as a mode
# change (5492 phantom "modified" files when this was first set up).
git config core.filemode false

# HARD GATE: the vault's .gitattributes routes .obsidian/plugins/**/data*.json through
# a `redact-plugin-secrets` clean filter, and git filters are PER-CLONE, not versioned.
# A clone without it commits live credentials and git says nothing. That is exactly what
# happened on the first run of this script (2026-08-12): the server had no filter, and
# the commit carried a Google Calendar client secret, an IGDB client secret and a Toggl
# API token in the clear. Never commit from here unless the filter is configured.
if ! git config --get filter.redact-plugin-secrets.clean >/dev/null; then
    echo "REFUSING TO COMMIT: filter.redact-plugin-secrets is not configured in this clone." >&2
    echo "Plugin settings files would be committed with live credentials." >&2
    echo "Fix: bash $VAULT/scripts/install-git-filters.sh" >&2
    exit 1
fi

if [ -z "$(git status --porcelain)" ]; then
    echo "no changes to commit"
else
    git add -A
    git commit --quiet -m "vault backup: $(date +%Y-%m-%dT%H:%M:%S)"
    echo "committed: $(git log --oneline -1)"
fi

# Integrate anything pushed from another device before pushing. --rebase keeps the
# history linear; a conflict aborts rather than leaving a half-finished rebase for
# the next run to trip over.
if ! git pull --rebase --quiet origin "$BRANCH"; then
    git rebase --abort 2>/dev/null || true
    echo "pull --rebase failed (conflict?), leaving the commit unpushed for manual review" >&2
    exit 1
fi

git push --quiet origin "$BRANCH"
echo "pushed to origin/$BRANCH: $(git log --oneline -1)"
