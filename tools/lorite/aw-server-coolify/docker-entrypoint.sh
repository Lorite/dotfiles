#!/bin/sh
# Entrypoint for the aw-server-rust service.
#
# aw-server-rust refuses cross-origin requests from any origin not on its CORS
# allowlist, answering 403. Served behind a real domain, the web UI's own XHRs carry
# `Origin: https://aw.lorite.eu`, so the dashboard renders but every request that sends
# an Origin header fails with the popup:
#     AxiosError: Request failed with status code 403
# and the server logs:
#     CORS Error: Origin 'https://aw.lorite.eu' is not allowed to request
#
# The allowlist is only settable in config.toml (v0.13.2 has no --cors flag), and that
# file lives outside the /data volume — so a redeploy would silently lose it. Instead we
# regenerate it from $AW_CORS_ORIGINS on every start, which makes the setting declarative
# and redeploy-proof.
#
# Only the aw-server service uses this entrypoint; aw-sync overrides it in the compose.
set -eu

CONFIG_DIR="${XDG_CONFIG_HOME:-/root/.config}/activitywatch/aw-server-rust"
CONFIG_FILE="$CONFIG_DIR/config.toml"

if [ -n "${AW_CORS_ORIGINS:-}" ]; then
    # Reject quotes/backslashes rather than emit a malformed TOML array, which
    # aw-server-rust would fail to parse at startup.
    case "$AW_CORS_ORIGINS" in
        *'"'* | *'\'*)
            echo "entrypoint: AW_CORS_ORIGINS must not contain quotes or backslashes" >&2
            exit 1
            ;;
    esac

    # "a, b" -> "a", "b"
    list=$(printf '%s' "$AW_CORS_ORIGINS" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
        | grep -v '^$' | sed 's/^/"/;s/$/"/' | paste -sd, -)

    mkdir -p "$CONFIG_DIR"
    printf 'cors = [%s]\n' "$list" > "$CONFIG_FILE"
    echo "entrypoint: CORS allowlist -> [$list]"
fi

exec aw-server-rust "$@"
