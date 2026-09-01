#!/usr/bin/env bash
# Canonical copy: ~/git/dotfiles/tools/lorite/video_note_summary.sh
# Headless run of the lorite-video-note-summary skill: fill the empty "# AI Summary" and
# "## Flashcards" sections of media/videos notes from each note's own transcript.
#
# Those sections are {{"prompt"}} interpreter variables in the Web Clipper template,
# executed by the browser extension's LLM. obsidian-clipper-cli has no interpreter, so
# every headlessly-clipped note (capture pipeline or phone share) arrives with both blank.
#
# Runs on the home server as part of lorite-nightly.target (01:00). Same dual-host model
# as morning_briefing.sh: VAULT is the Syncthing working copy on the server, the live
# repo on the laptop. The skill reads VAULT.
set -euo pipefail

VAULT="${LORITE_VAULT:-$HOME/git/lorite-obsidian-notes}"
LIMIT="${LORITE_VIDEO_SUMMARY_LIMIT:-5}"
PENDING="$HOME/git/dotfiles/tools/lorite/obsidian-clipper/video-notes-pending.py"

export VAULT

# Exit before spending an LLM call when there is nothing to do. This is the common case
# on most nights, and it keeps the nightly batch fast and the journal quiet.
if [[ ! -x "$PENDING" ]]; then
    echo "video-note-summary: $PENDING missing, skipping" >&2
    exit 0
fi
COUNT="$(OBSIDIAN_VAULT="$VAULT" "$PENDING" --count 2>/dev/null || echo 0)"
if [[ "$COUNT" -eq 0 ]]; then
    echo "video-note-summary: nothing pending, skipping"
    exit 0
fi

echo "video-note-summary: $COUNT note(s) pending, filling up to $LIMIT, VAULT=$VAULT"
OBSIDIAN_VAULT="$VAULT" "$PENDING" --verbose --limit "$LIMIT" || true

export OPENCODE_PRINT_BG_WAIT_CEILING_MS=1200000
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=1200000

LLM="$HOME/git/dotfiles/tools/lorite/lorite-llm.sh"
echo "video-note-summary: detected client $("$LLM" --which 2>/dev/null || echo unknown)"

# The limit rides --skill-args, never a bare positional: lorite-llm.sh parses flags only
# and exits 2 on anything else (the bug that silently killed every weekly-note run from
# 2026-08-17 to 08-31).
exec "$LLM" --skill lorite-video-note-summary \
     --skill-args "--limit $LIMIT" \
     --allowed-tools Bash,Read,Write,Edit,Glob,Grep,TodoWrite,Skill \
     --max-turns 120
