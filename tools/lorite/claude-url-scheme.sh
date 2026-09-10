#!/usr/bin/env bash
# claude-url-scheme.sh - deliver a claude:// URL to the RIGHT Claude Desktop instance.
#
# Why this exists: signing in to Claude Desktop finishes with an OAuth callback delivered as a
# claude:// deep link. xdg-open routes that scheme to ONE .desktop entry (x-scheme-handler/claude in
# ~/.config/mimeapps.list), so with two instances running the callback lands on whichever entry is
# the default. If that is the wrong instance it just raises its own window and the instance that
# started the login never receives the token.
#
# Flipping the default is NOT reliable on its own: "desktopName": "com.anthropic.Claude.desktop" is
# baked into the app, so EVERY instance re-registers that one entry as the handler on startup via
# setAsDefaultProtocolClient - the personal instance clobbers the flip itself.
#
# So `open-personal` is the method that actually works. Launching claude-desktop with the same
# --user-data-dir as a running instance hands the URL to THAT instance through its own
# single-instance lock, bypassing xdg-open and mimeapps.list entirely.
#
# Sign-in procedure for the personal account:
#   1. start the sign-in from the personal window
#   2. complete it in the browser
#   3. when the browser offers to open Claude, DON'T let it - copy the claude://... link instead
#      (right-click the "Open Claude" button -> Copy Link, or copy it out of the protocol dialog)
#   4. claude-url-scheme.sh open-personal 'claude://...'
#
# Usage:
#   claude-url-scheme.sh status                 # which entry currently owns claude://
#   claude-url-scheme.sh open-personal <url>    # hand a claude:// URL to the personal instance
#   claude-url-scheme.sh open-itu <url>         # hand a claude:// URL to the ITU instance
#   claude-url-scheme.sh personal               # flip the default handler (fragile, see above)
#   claude-url-scheme.sh itu                    # hand the default back

set -euo pipefail

SCHEME="x-scheme-handler/claude"
ITU_ENTRY="com.anthropic.Claude.desktop"
PERSONAL_ENTRY="com.anthropic.Claude-Personal.desktop"
ITU_PROFILE="$HOME/.config/Claude"
PERSONAL_PROFILE="$HOME/.config/Claude-Personal"
PERSONAL_CONFIG="$HOME/.claude-personal"

usage() {
    sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

describe() {
    case "$1" in
        "$ITU_ENTRY") echo "$1  (ITU / PhD, profile $ITU_PROFILE)" ;;
        "$PERSONAL_ENTRY") echo "$1  (personal, profile $PERSONAL_PROFILE)" ;;
        "") echo "(none set)" ;;
        *) echo "$1" ;;
    esac
}

require_url() {
    if [ -z "${1:-}" ]; then
        echo "error: need a claude:// URL" >&2
        exit 1
    fi
    case "$1" in
        claude://*) ;;
        *)
            echo "error: not a claude:// URL: $1" >&2
            exit 1
            ;;
    esac
}

# Hand a URL to the instance owning $profile. If that instance is running, its single-instance
# lock forwards the argv to it and this process exits at once; if not, it starts there.
dispatch() {
    local profile=$1 config=$2 url=$3
    require_url "$url"
    if [ ! -d "$profile" ]; then
        echo "error: no such profile: $profile" >&2
        echo "       run ./install.sh to create the launchers and profiles" >&2
        exit 1
    fi
    COWORK_VM_BACKEND=host CLAUDE_CONFIG_DIR="$config" \
        claude-desktop --user-data-dir="$profile" "$url" >/dev/null 2>&1 &
    echo "delivered to $profile"
}

set_default() {
    local entry=$1
    if [ ! -f "$HOME/.local/share/applications/$entry" ] &&
        [ ! -f "/usr/share/applications/$entry" ]; then
        echo "error: desktop entry not found: $entry" >&2
        echo "       run ./install.sh to install the Claude launchers" >&2
        exit 1
    fi
    xdg-mime default "$entry" "$SCHEME"
    echo "claude:// -> $(describe "$entry")"
    echo "note: any Claude instance re-registers $ITU_ENTRY on startup, so this can be undone"
    echo "      at any time. Prefer 'open-personal <url>' for a sign-in."
}

case "${1:-status}" in
    status) echo "claude:// -> $(describe "$(xdg-mime query default "$SCHEME" 2>/dev/null || true)")" ;;
    open-personal) dispatch "$PERSONAL_PROFILE" "$PERSONAL_CONFIG" "${2:-}" ;;
    open-itu) dispatch "$ITU_PROFILE" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${2:-}" ;;
    personal) set_default "$PERSONAL_ENTRY" ;;
    itu | default) set_default "$ITU_ENTRY" ;;
    -h | --help | help) usage 0 ;;
    *)
        echo "error: unknown command '${1}'" >&2
        usage 1 >&2
        ;;
esac
