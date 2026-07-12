#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/morning_briefing.sh
# Run by lorite-morning-briefing.service (06:00 daily): headless Claude Code run
# of the lorite-morning-briefing skill — daily-note LLM summaries + vault git
# audit + briefing note in ai_brain/. Report-only on git; idempotent per day.
set -euo pipefail

VAULT="$HOME/git/lorite-obsidian-notes"
BRIEFING="$VAULT/ai_brain/$(date +%F) AI Brain - Morning Briefing.md"

if [[ -e "$BRIEFING" ]]; then
    echo "morning-briefing: already written today ($BRIEFING) — skipping"
    exit 0
fi

# Scoped headless permissions: local tools only (no web, no MCP); the skill is
# report-only on git and writes only ai_brain/ + daily-note summary sections.
exec claude -p "/lorite-morning-briefing" \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep,TodoWrite,Skill" \
    --max-turns 100
