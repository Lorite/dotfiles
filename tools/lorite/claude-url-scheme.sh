#!/usr/bin/env bash
# claude-url-scheme.sh - point the claude:// URL scheme at one of the two Claude Desktop instances.
#
# Why this exists: signing in to Claude Desktop finishes with an OAuth callback delivered as a
# claude:// deep link. xdg-open routes that scheme to ONE .desktop entry (x-scheme-handler/claude in
# ~/.config/mimeapps.list), so with two instances running the callback always lands on whichever
# entry is the default. If that is the wrong instance it simply raises its own window (its
# second-instance handler) and the instance that started the login never receives the token.
#
# There is no per-instance routing and no manual code-paste fallback, so the login dance is:
#   claude-url-scheme.sh personal   # point the scheme at the personal instance
#   ...sign in on the personal window...
#   claude-url-scheme.sh itu        # hand the scheme back to the default/ITU instance
#
# Tokens persist per profile, so this is only needed at sign-in and at re-auth.
#
# Usage:
#   claude-url-scheme.sh status     # show which entry currently owns claude://
#   claude-url-scheme.sh personal   # route to com.anthropic.Claude-Personal.desktop
#   claude-url-scheme.sh itu        # route to com.anthropic.Claude.desktop (the default)

set -euo pipefail

SCHEME="x-scheme-handler/claude"
ITU_ENTRY="com.anthropic.Claude.desktop"
PERSONAL_ENTRY="com.anthropic.Claude-Personal.desktop"

usage() {
    sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

current() {
    xdg-mime query default "$SCHEME" 2>/dev/null || true
}

describe() {
    case "$1" in
        "$ITU_ENTRY") echo "$1  (ITU / PhD, profile ~/.config/Claude)" ;;
        "$PERSONAL_ENTRY") echo "$1  (personal, profile ~/.config/Claude-Personal)" ;;
        "") echo "(none set)" ;;
        *) echo "$1" ;;
    esac
}

set_to() {
    local entry=$1
    if [ ! -f "$HOME/.local/share/applications/$entry" ] &&
        [ ! -f "/usr/share/applications/$entry" ]; then
        echo "error: desktop entry not found: $entry" >&2
        echo "       run ./install.sh to install the Claude launchers" >&2
        exit 1
    fi
    xdg-mime default "$entry" "$SCHEME"
    echo "claude:// -> $(describe "$entry")"
}

case "${1:-status}" in
    status) echo "claude:// -> $(describe "$(current)")" ;;
    personal) set_to "$PERSONAL_ENTRY" ;;
    itu | default) set_to "$ITU_ENTRY" ;;
    -h | --help | help) usage 0 ;;
    *)
        echo "error: unknown command '${1}'" >&2
        usage 1 >&2
        ;;
esac
