#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/morning_briefing.sh
# Run by lorite-morning-briefing.service (06:00 daily): headless Claude Code run
# of the lorite-morning-briefing skill — daily-note LLM summaries + vault git
# audit + briefing note in ai_chats/briefings/. Report-only on git; idempotent per day.
set -euo pipefail

VAULT="$HOME/git/lorite-obsidian-notes"
BRIEFING="$VAULT/ai_chats/briefings/daily/AI Briefing - $(date +%F).md"

if [[ -e "$BRIEFING" ]]; then
    echo "morning-briefing: already written today ($BRIEFING) — skipping"
    exit 0
fi

# Best-effort: open the Obsidian GUI if it's installed but not already running, so
# the daily-note processing/lint steps have a live app to drive (they use the
# `obsidian` CLI against the running app). Never fails the briefing — a headless
# host usually has no `obsidian` binary (skips), and a failed launch is swallowed.
OBSIDIAN_BIN="$(command -v obsidian || true)"
if [[ -n "$OBSIDIAN_BIN" ]] && ! pgrep -x obsidian >/dev/null 2>&1; then
    echo "morning-briefing: Obsidian installed but not running — launching it"
    export DISPLAY="${DISPLAY:-:0}"          # timer env may lack it; harmless if wrong
    ( setsid "$OBSIDIAN_BIN" >/dev/null 2>&1 </dev/null & ) || true
    # give it up to ~30s to appear and index the vault before the note steps run
    for _ in $(seq 1 30); do
        if pgrep -x obsidian >/dev/null 2>&1; then break; fi
        sleep 1
    done
    sleep 8
fi

# Headless permissions: local tools + web + subagents. `Task` lets the briefing
# delegate to the lorite-concept-note-writer agent (step 3), and WebSearch/WebFetch
# let that agent research concepts to ground the notes it writes. Still report-only
# on git; writes ai_chats/ + daily-note summaries + concept notes (work|personal/concepts).
exec claude -p "/lorite-morning-briefing" \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep,TodoWrite,Skill,Task,WebSearch,WebFetch" \
    --max-turns 150
