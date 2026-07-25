#!/usr/bin/env bash
# lorite-llm — client-agnostic headless LLM runner: Claude Code (default) / OpenCode.
#
# Callers describe WHAT to run in client-neutral terms; this wrapper translates to each
# client's real CLI. It never forwards Claude flags to OpenCode (their syntaxes differ
# completely) and it never consumes a caller flag as one of its own.
#
#   --which                   print which client would be used, then exit
#   --skill <name>            run a skill / slash command (e.g. lorite-morning-briefing)
#   --prompt "<text>"         run a free-text prompt
#   --allowed-tools <csv>     Claude only (OpenCode has no equivalent; ignored there)
#   --max-turns <n>           Claude only (ignored on OpenCode)
#   --model <m>               override the model for the picked client
#   --dry-run                 print the resolved command instead of running it
#
# Env overrides (also settable in ~/.config/environment.d/lorite-llm.conf):
#   LLM_CLIENT=claude|opencode    force a client and skip auto-detection
#   LLM_MODEL=<model>             model override (client-specific naming)
#   LLM_FALLBACK=1|0              on primary-client failure, retry with the other (default 1)
#
# Exit status is the picked client's; 127 if no usable client exists.
set -euo pipefail

# ── client discovery ────────────────────────────────────────────────────────────
# OpenCode's installer drops the binary in ~/.opencode/bin, which is NOT on the PATH
# systemd units get — so resolve it by absolute path too, and always invoke the
# resolved path rather than the bare name.
resolve_opencode() {
    command -v opencode 2>/dev/null && return 0
    [[ -x "$HOME/.opencode/bin/opencode" ]] && { echo "$HOME/.opencode/bin/opencode"; return 0; }
    return 1
}
resolve_claude() {
    command -v claude 2>/dev/null && return 0
    [[ -x "$HOME/.local/bin/claude" ]] && { echo "$HOME/.local/bin/claude"; return 0; }
    return 1
}

OPENCODE_BIN="$(resolve_opencode || true)"
CLAUDE_BIN="$(resolve_claude || true)"

# Auto-detection prefers Claude: it is the client the lorite skills are written and
# proven against. OpenCode is opt-in (LLM_CLIENT=opencode) until it has been validated
# on these workflows — but it is a first-class fallback when Claude fails (e.g. a
# usage limit, which is exactly what broke the 2026-07-20 morning briefing).
detect_client() {
    case "${LLM_CLIENT:-}" in
        claude)
            [[ -n "$CLAUDE_BIN" ]] && { echo claude; return 0; }
            echo "ERROR: LLM_CLIENT=claude but claude is not installed" >&2; return 127 ;;
        opencode)
            [[ -n "$OPENCODE_BIN" ]] && { echo opencode; return 0; }
            echo "ERROR: LLM_CLIENT=opencode but opencode is not installed" >&2; return 127 ;;
        "")
            [[ -n "$CLAUDE_BIN"   ]] && { echo claude;   return 0; }
            [[ -n "$OPENCODE_BIN" ]] && { echo opencode; return 0; }
            echo "ERROR: neither claude nor opencode is installed" >&2; return 127 ;;
        *)
            echo "ERROR: unknown LLM_CLIENT='${LLM_CLIENT}' — use 'claude' or 'opencode'" >&2; return 127 ;;
    esac
}

other_client() { [[ "$1" == claude ]] && echo opencode || echo claude; }

# ── parse args ──────────────────────────────────────────────────────────────────
WHICH=0; DRY_RUN=0
SKILL=""; PROMPT=""; ALLOWED_TOOLS=""; MAX_TURNS=""; MODEL="${LLM_MODEL:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --which)         WHICH=1; shift ;;
        --dry-run)       DRY_RUN=1; shift ;;
        --skill)         SKILL="$2"; shift 2 ;;
        --prompt)        PROMPT="$2"; shift 2 ;;
        --allowed-tools) ALLOWED_TOOLS="$2"; shift 2 ;;
        --max-turns)     MAX_TURNS="$2"; shift 2 ;;
        --model)         MODEL="$2"; shift 2 ;;
        -h|--help)       sed -n '2,20p' "$0"; exit 0 ;;
        *)               echo "ERROR: unknown argument '$1' (see --help)" >&2; exit 2 ;;
    esac
done

CLIENT="$(detect_client)" || exit $?
[[ $WHICH -eq 1 ]] && { echo "$CLIENT"; exit 0; }

if [[ -z "$SKILL" && -z "$PROMPT" ]]; then
    echo "ERROR: nothing to run — pass --skill <name> or --prompt \"<text>\"" >&2
    exit 2
fi

# ── per-client command construction ─────────────────────────────────────────────
# Claude: skills are slash commands under --print. OpenCode: skills are model-visible
# tools, so a skill run is a prompt instructing the agent to use it, and permissions
# must be pre-approved (--auto) because a headless run has nobody to answer a prompt.
build_cmd() {
    local client="$1"; CMD=()
    case "$client" in
        claude)
            local text="${PROMPT:-/$SKILL}"
            CMD=("$CLAUDE_BIN" --model "${MODEL:-sonnet}" -p "$text")
            [[ -n "$ALLOWED_TOOLS" ]] && CMD+=(--allowedTools "$ALLOWED_TOOLS")
            [[ -n "$MAX_TURNS"     ]] && CMD+=(--max-turns "$MAX_TURNS")
            ;;
        opencode)
            local text="${PROMPT:-Use the $SKILL skill now, and follow it to completion.}"
            CMD=("$OPENCODE_BIN" run --auto)
            [[ -n "$MODEL" ]] && CMD+=(--model "$MODEL")
            CMD+=("$text")
            ;;
    esac
}

run_client() {
    local client="$1"
    build_cmd "$client"
    if [[ $DRY_RUN -eq 1 ]]; then
        printf '%q ' "${CMD[@]}"; echo; return 0
    fi
    echo "[lorite-llm] running via $client" >&2
    "${CMD[@]}"
}

# Primary attempt; on failure fall back to the other client when one is available.
if run_client "$CLIENT"; then
    exit 0
fi
STATUS=$?

FALLBACK="$(other_client "$CLIENT")"
FALLBACK_BIN_VAR="$([[ "$FALLBACK" == claude ]] && echo "$CLAUDE_BIN" || echo "$OPENCODE_BIN")"

if [[ "${LLM_FALLBACK:-1}" == 1 && -z "${LLM_CLIENT:-}" && -n "$FALLBACK_BIN_VAR" ]]; then
    echo "[lorite-llm] $CLIENT failed (exit $STATUS) — retrying with $FALLBACK" >&2
    run_client "$FALLBACK"
    exit $?
fi

exit $STATUS
