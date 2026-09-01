#!/usr/bin/env bash
# lorite-llm — client-agnostic headless LLM runner: Claude Code (default) / OpenCode.
#
# Callers describe WHAT to run in client-neutral terms; this wrapper translates to each
# client's real CLI. It never forwards Claude flags to OpenCode (their syntaxes differ
# completely) and it never consumes a caller flag as one of its own.
#
#   --which                   print which client would be used, then exit
#   --skill <name>            run a skill / slash command (e.g. lorite-morning-briefing)
#   --skill-args "<text>"     arguments for --skill, translated per client (Claude appends
#                             them to the slash command, OpenCode folds them into the prompt)
#   --prompt "<text>"         run a free-text prompt
#   --allowed-tools <csv>     Claude only (OpenCode has no equivalent; ignored there)
#   --max-turns <n>           Claude only (ignored on OpenCode)
#   --model <m>               override the model for the picked client
#   --effort <level>          Claude only: low|medium|high|xhigh|max (ignored on OpenCode)
#   --dry-run                 print the resolved command instead of running it
#
# Env overrides (also settable in ~/.config/environment.d/lorite-llm.conf):
#   LLM_CLIENT=claude|opencode    force a client and skip auto-detection
#   LLM_MODEL=<model>             model override (client-specific naming)
#   LLM_EFFORT=<level>            Claude only: reasoning effort (low|medium|high|xhigh|max)
#   LLM_FALLBACK=1|0              on primary-client failure, retry with the other (default 1).
#                                 Applies even when LLM_CLIENT is pinned; the retry drops
#                                 LLM_MODEL, which is client-specific. Set 0 to fail instead.
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

# Auto-detection prefers OpenCode: the whole point of having it is to keep low-effort
# work off the Claude quota (a Claude weekly limit is what killed the 2026-07-20 morning
# briefing). Claude is the automatic fallback.
#
# Callers with a job OpenCode has been MEASURED to do badly should pin LLM_CLIENT=claude
# themselves rather than flipping this default — see lorite-morning-briefing.service,
# which does exactly that and says why. Pinning picks the PRIMARY client only: since
# 2026-07-31 a pinned client still falls back to the other one when it fails.
detect_client() {
    case "${LLM_CLIENT:-}" in
        claude)
            [[ -n "$CLAUDE_BIN" ]] && { echo claude; return 0; }
            echo "ERROR: LLM_CLIENT=claude but claude is not installed" >&2; return 127 ;;
        opencode)
            [[ -n "$OPENCODE_BIN" ]] && { echo opencode; return 0; }
            echo "ERROR: LLM_CLIENT=opencode but opencode is not installed" >&2; return 127 ;;
        "")
            [[ -n "$OPENCODE_BIN" ]] && { echo opencode; return 0; }
            [[ -n "$CLAUDE_BIN"   ]] && { echo claude;   return 0; }
            echo "ERROR: neither opencode nor claude is installed" >&2; return 127 ;;
        *)
            echo "ERROR: unknown LLM_CLIENT='${LLM_CLIENT}' — use 'claude' or 'opencode'" >&2; return 127 ;;
    esac
}

other_client() { [[ "$1" == claude ]] && echo opencode || echo claude; }

# ── parse args ──────────────────────────────────────────────────────────────────
WHICH=0; DRY_RUN=0
SKILL=""; PROMPT=""; ALLOWED_TOOLS=""; MAX_TURNS=""; MODEL="${LLM_MODEL:-}"; EFFORT="${LLM_EFFORT:-}"
SKILL_ARGS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --which)         WHICH=1; shift ;;
        --dry-run)       DRY_RUN=1; shift ;;
        --skill)         SKILL="$2"; shift 2 ;;
        --skill-args)    SKILL_ARGS="$2"; shift 2 ;;
        --prompt)        PROMPT="$2"; shift 2 ;;
        --allowed-tools) ALLOWED_TOOLS="$2"; shift 2 ;;
        --max-turns)     MAX_TURNS="$2"; shift 2 ;;
        --model)         MODEL="$2"; shift 2 ;;
        --effort)        EFFORT="$2"; shift 2 ;;
        -h|--help)       sed -n '2,25p' "$0"; exit 0 ;;
        *)               echo "ERROR: unknown argument '$1' (see --help)" >&2; exit 2 ;;
    esac
done

CLIENT="$(detect_client)" || exit $?
[[ $WHICH -eq 1 ]] && { echo "$CLIENT"; exit 0; }

if [[ -n "$SKILL_ARGS" && -z "$SKILL" ]]; then
    echo "ERROR: --skill-args needs --skill (it is the skill's argument line)" >&2
    exit 2
fi

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
            # Claude runs a skill as a slash command, which takes its arguments inline.
            local text="$PROMPT"
            if [[ -z "$text" ]]; then
                text="/$SKILL"
                if [[ -n "$SKILL_ARGS" ]]; then text="$text $SKILL_ARGS"; fi
            fi
            CMD=("$CLAUDE_BIN" --model "${MODEL:-sonnet}" -p "$text")
            [[ -n "$ALLOWED_TOOLS" ]] && CMD+=(--allowedTools "$ALLOWED_TOOLS")
            [[ -n "$MAX_TURNS"     ]] && CMD+=(--max-turns "$MAX_TURNS")
            # Unset => the client's own default (settings.json effortLevel), not a hardcoded one.
            [[ -n "$EFFORT"        ]] && CMD+=(--effort "$EFFORT")
            ;;
        opencode)
            # OpenCode has no slash commands: a skill run is a prompt, so the arguments
            # have to be stated in prose rather than appended as a positional.
            local text="$PROMPT"
            if [[ -z "$text" ]]; then
                if [[ -n "$SKILL_ARGS" ]]; then
                    text="Use the $SKILL skill now with these arguments: $SKILL_ARGS. Follow it to completion."
                else
                    text="Use the $SKILL skill now, and follow it to completion."
                fi
            fi
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

# Primary attempt.
#
# Status capture is deliberate: `if run_client ...; then exit 0; fi` followed by `STATUS=$?`
# reads **0**, not the client's exit code — an `if` whose condition fails and which has no
# `else` returns 0 itself. That bug (fixed 2026-07-31) made a failed run exit 0, so systemd
# logged the nightly briefing as successful when the LLM had actually died. Use `|| STATUS=$?`.
STATUS=0
run_client "$CLIENT" || STATUS=$?
if [[ $STATUS -eq 0 ]]; then
    exit 0
fi

FALLBACK="$(other_client "$CLIENT")"
FALLBACK_BIN_VAR="$([[ "$FALLBACK" == claude ]] && echo "$CLAUDE_BIN" || echo "$OPENCODE_BIN")"

# Fall back EVEN WHEN LLM_CLIENT IS PINNED (changed 2026-07-31; it used to require LLM_CLIENT
# to be unset). Pinning expresses which client should do the work, not an instruction to fail
# the whole job when that client is unavailable — and a Claude quota limit is precisely when
# the other client earns its keep, since that is what killed the 2026-07-20 briefing.
# Opt out with LLM_FALLBACK=0.
if [[ "${LLM_FALLBACK:-1}" == 1 && -n "$FALLBACK_BIN_VAR" ]]; then
    # MODEL is client-specific by definition (claude-sonnet-5 vs openclaw), so carrying it into
    # the retry would only fail it a second way. Drop it and let the fallback client use its own
    # default. EFFORT needs no such handling: build_cmd only applies it on the Claude branch.
    if [[ -n "$MODEL" ]]; then
        echo "[lorite-llm] dropping --model '$MODEL' for the $FALLBACK retry (models are client-specific)" >&2
        MODEL=""
    fi
    echo "[lorite-llm] $CLIENT failed (exit $STATUS) — retrying with $FALLBACK" >&2
    run_client "$FALLBACK"
    exit $?
fi

exit $STATUS
