#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/morning_briefing.sh
# Headless OpenCode-first (Claude fallback) run of the lorite-morning-briefing skill —
# daily-note LLM summaries + vault git audit + concept notes + briefing note in
# ai_chats/briefings/. Report-only on git; idempotent per day. Runs on TWO kinds of host:
#
#   * Laptop (GUI):    Obsidian app available → drives the CLI for lint; the vault
#                      dir is itself the git repo. OnCalendar 06:00.
#   * Home server (headless, Syncthing): no GUI. Content is read/written in the
#                      Syncthing working copy ($VAULT); git history for the audit
#                      comes from a SEPARATE read-only clone ($LORITE_VAULT_GIT),
#                      because Syncthing excludes .git/ (.stignore). OnCalendar 03:00.
#
# The skill reads these exported vars: VAULT (content root), VAULT_GIT (git-history
# root), AUDIT_REF (ref to audit), OBSIDIAN_GUI (1 app-driven / 0 pure-file).
set -euo pipefail

VAULT="${LORITE_VAULT:-$HOME/git/lorite-obsidian-notes}"
# Git-history root. On the laptop it's the vault itself (has .git). On the server
# set LORITE_VAULT_GIT to a side clone that this script `git fetch`es below.
VAULT_GIT="${LORITE_VAULT_GIT:-$VAULT}"
BRIEFING="$VAULT/ai_chats/briefings/daily/AI Briefing - $(date +%F).md"

if [[ -e "$BRIEFING" ]]; then
    echo "morning-briefing: already written today ($BRIEFING) — skipping"
    exit 0
fi

# --- Mode detection: is a live Obsidian app drivable via the CLI? -------------
# Only attempt a GUI launch when a display exists (never on a headless server).
OBSIDIAN_GUI="${OBSIDIAN_GUI:-auto}"
if [[ "$OBSIDIAN_GUI" == auto ]]; then
    OBSIDIAN_BIN="$(command -v obsidian || true)"
    if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]] && [[ -n "$OBSIDIAN_BIN" ]] \
       && ! pgrep -x obsidian >/dev/null 2>&1; then
        echo "morning-briefing: Obsidian installed, display present, app down — launching it"
        export DISPLAY="${DISPLAY:-:0}"
        ( setsid "$OBSIDIAN_BIN" >/dev/null 2>&1 </dev/null & ) || true
        for _ in $(seq 1 30); do pgrep -x obsidian >/dev/null 2>&1 && break; sleep 1; done
        sleep 8
    fi
    # Authoritative probe: the CLI only answers when the app is up with a vault.
    if command -v obsidian >/dev/null 2>&1 && obsidian vault >/dev/null 2>&1; then
        OBSIDIAN_GUI=1
    else
        OBSIDIAN_GUI=0
    fi
fi

# --- Headless: refresh the side clone so the commit audit sees latest history --
if [[ "$VAULT_GIT" != "$VAULT" ]]; then
    if [[ -d "$VAULT_GIT/.git" ]]; then
        git -C "$VAULT_GIT" fetch --quiet origin 2>/dev/null \
            || echo "morning-briefing: warn — 'git fetch' on $VAULT_GIT failed; commit audit may be stale"
        AUDIT_REF="origin/main"          # audit the freshly-fetched remote head
    else
        echo "morning-briefing: warn — LORITE_VAULT_GIT=$VAULT_GIT is not a git clone; commit audit will be skipped"
        AUDIT_REF=""
    fi
else
    AUDIT_REF="HEAD"                      # laptop: the vault dir is the live repo
fi

export VAULT VAULT_GIT AUDIT_REF OBSIDIAN_GUI

# Background-wait ceiling (20 min). OpenCode reads its own env var; Claude Code reads
# CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS. Set both so whichever client fires gets it.
export OPENCODE_PRINT_BG_WAIT_CEILING_MS=1200000
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=1200000

echo "morning-briefing: mode OBSIDIAN_GUI=$OBSIDIAN_GUI VAULT=$VAULT VAULT_GIT=$VAULT_GIT AUDIT_REF=${AUDIT_REF:-<none>}"

# Headless permissions: local tools + web + subagents. `Task` lets the briefing
# delegate to the lorite-concept-note-writer agent (step 3), and WebSearch/WebFetch
# let that agent research concepts to ground the notes it writes. Still report-only
# on git; writes ai_chats/ + daily-note summaries + concept notes (work|personal/concepts).

# Use lorite-llm wrapper: OpenCode (Big Pickle) → Claude fallback (Sonnet).
LLM="$HOME/git/dotfiles/tools/lorite/lorite-llm.sh"
echo "morning-briefing: detected client $("$LLM" -p 2>/dev/null || echo unknown)"

exec "$LLM" -p "/lorite-morning-briefing" \
     --allowedTools Bash,Read,Write,Edit,Glob,Grep,TodoWrite,Skill,Task,WebSearch,WebFetch \
     --max-turns 150
