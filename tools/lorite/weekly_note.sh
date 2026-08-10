#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/weekly_note.sh
# Headless run of the lorite-weekly-note skill: create + fill the weekly note
# (diary/weekly/<gggg-Www>.md) for the last completed ISO week. Data sections are
# computed from vault frontmatter (no Run plugin, no Templater), reflective answers
# are drafted as marked AI proposals, and an AI Generated week roll-up is appended.
# Idempotent per week: exits 0 when the target note already exists.
#
# Runs on the home server via lorite-weekly-note.timer (Mon 03:00, after the 01:00
# nightly batch has written Sunday's daily summary). Same dual-host model as
# morning_briefing.sh: VAULT is the Syncthing working copy on the server, the live
# repo on the laptop. The skill reads VAULT and OBSIDIAN_GUI.
set -euo pipefail

VAULT="${LORITE_VAULT:-$HOME/git/lorite-obsidian-notes}"

# Target week: ISO week of yesterday (Mon 03:00 run -> the week that just ended).
WEEK="${1:-$(date -d yesterday +%G-W%V)}"
NOTE="$VAULT/diary/weekly/$WEEK.md"

if [[ -e "$NOTE" ]]; then
    echo "weekly-note: $WEEK already written ($NOTE), skipping"
    exit 0
fi

# GUI probe, same as morning_briefing.sh but with no launch attempt: the weekly
# note is pure file ops, a GUI only adds an optional lint at the end.
if command -v obsidian >/dev/null 2>&1 && obsidian vault >/dev/null 2>&1; then
    OBSIDIAN_GUI=1
else
    OBSIDIAN_GUI=0
fi
export VAULT OBSIDIAN_GUI

export OPENCODE_PRINT_BG_WAIT_CEILING_MS=1200000
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=1200000

echo "weekly-note: target $WEEK, OBSIDIAN_GUI=$OBSIDIAN_GUI, VAULT=$VAULT"

LLM="$HOME/git/dotfiles/tools/lorite/lorite-llm.sh"
echo "weekly-note: detected client $("$LLM" --which 2>/dev/null || echo unknown)"

exec "$LLM" --skill lorite-weekly-note \
     --allowed-tools Bash,Read,Write,Edit,Glob,Grep,TodoWrite,Skill \
     --max-turns 100 \
     "$WEEK"
