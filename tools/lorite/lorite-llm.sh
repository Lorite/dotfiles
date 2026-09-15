#!/usr/bin/env bash
# lorite-llm — client-agnostic headless LLM runner: Antigravity (agy) / OpenCode / Claude Code.
#
# Callers describe WHAT to run in client-neutral terms; this wrapper translates to each
# client's real CLI. It never forwards one client's flags to another (their syntaxes differ
# completely) and it never consumes a caller flag as one of its own.
#
#   --which                   print which client would be used, then exit
#   --skill <name>            run a skill / slash command (e.g. lorite-morning-briefing)
#   --skill-args "<text>"     arguments for --skill, translated per client (Claude appends
#                             them to the slash command, OpenCode folds them into the prompt)
#   --prompt "<text>"         run a free-text prompt
#   --allowed-tools <csv>     Claude only (OpenCode/Antigravity have no equivalent; ignored)
#   --max-turns <n>           Claude only (ignored elsewhere)
#   --model <m>               override the model for the picked client
#   --effort <level>          Claude: low|medium|high|xhigh|max. Antigravity: low|medium|high
#                             (xhigh/max are CLAMPED to high — see clamp_effort). Ignored on OpenCode.
#   --dry-run                 print the resolved command instead of running it
#
# Env overrides (also settable in ~/.config/environment.d/lorite-llm.conf):
#   LLM_CLIENT=antigravity|opencode|claude   force a client and skip auto-detection
#   LLM_MODEL=<model>             model override (client-specific naming)
#   LLM_EFFORT=<level>            reasoning effort; see --effort above for per-client ranges
#   LLM_FALLBACK=1|0              on primary-client failure, retry with the remaining clients in
#                                 order (default 1). Applies even when LLM_CLIENT is pinned; the
#                                 retry drops LLM_MODEL, which is client-specific. 0 = fail instead.
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
# Antigravity's installer (https://antigravity.google/cli/install.sh) drops `agy` in
# ~/.local/bin, which — like OpenCode's — is not on the PATH systemd units get.
resolve_antigravity() {
    command -v agy 2>/dev/null && return 0
    [[ -x "$HOME/.local/bin/agy" ]] && { echo "$HOME/.local/bin/agy"; return 0; }
    return 1
}

OPENCODE_BIN="$(resolve_opencode || true)"
CLAUDE_BIN="$(resolve_claude || true)"
ANTIGRAVITY_BIN="$(resolve_antigravity || true)"

client_bin() {
    case "$1" in
        antigravity) echo "$ANTIGRAVITY_BIN" ;;
        opencode)    echo "$OPENCODE_BIN" ;;
        claude)      echo "$CLAUDE_BIN" ;;
    esac
}

# Preference order for auto-detection. Antigravity leads (2026-09-15): it has been the most
# effective client in practice, and like OpenCode it keeps routine work off the Claude quota
# (a Claude weekly limit is what killed the 2026-07-20 morning briefing). OpenCode stays ahead
# of Claude for the same quota reason.
#
# Callers with a job a given client has been MEASURED to do badly should pin LLM_CLIENT
# themselves rather than flipping this order — see lorite-morning-briefing.service, which does
# exactly that and says why. Pinning picks the PRIMARY client only: since 2026-07-31 a pinned
# client still falls back when it fails, and since 2026-09-15 it falls through the remaining
# clients in this order rather than to a single hardcoded partner.
CLIENT_ORDER=(antigravity opencode claude)

detect_client() {
    local c
    case "${LLM_CLIENT:-}" in
        antigravity|opencode|claude)
            [[ -n "$(client_bin "$LLM_CLIENT")" ]] && { echo "$LLM_CLIENT"; return 0; }
            echo "ERROR: LLM_CLIENT=$LLM_CLIENT but that client is not installed" >&2; return 127 ;;
        "")
            for c in "${CLIENT_ORDER[@]}"; do
                [[ -n "$(client_bin "$c")" ]] && { echo "$c"; return 0; }
            done
            echo "ERROR: no LLM client installed (looked for: ${CLIENT_ORDER[*]})" >&2; return 127 ;;
        *)
            echo "ERROR: unknown LLM_CLIENT='${LLM_CLIENT}' — use 'antigravity', 'opencode' or 'claude'" >&2
            return 127 ;;
    esac
}

# Installed clients other than $1, in CLIENT_ORDER. The fallback chain.
fallback_clients() {
    local primary=$1 c
    for c in "${CLIENT_ORDER[@]}"; do
        [[ "$c" == "$primary" ]] && continue
        [[ -n "$(client_bin "$c")" ]] && printf '%s\n' "$c"
    done
}

# Antigravity accepts only low|medium|high, Claude also xhigh|max. The home server pins
# LLM_EFFORT=xhigh for Claude, so passing it through unclamped makes agy exit immediately with
# `invalid --effort "xhigh" (valid: low, medium, high)` — i.e. every nightly job would fail at
# launch the moment Antigravity became the client. Clamp instead of failing.
clamp_effort() {
    case "$1" in
        xhigh|max) echo high ;;
        *)         echo "$1" ;;
    esac
}

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
# Claude and Antigravity: skills are slash commands under print mode, taking their arguments
# inline. OpenCode: skills are model-visible tools, so a skill run is a prompt instructing the
# agent to use it. In every case permissions must be pre-approved (--auto / --dangerously-skip-
# permissions) because a headless run has nobody to answer a prompt.
build_cmd() {
    local client="$1"; CMD=()
    case "$client" in
        antigravity)
            # Verified 2026-09-15: `agy -p "/<skill> <args>"` expands skills and slash commands
            # in print mode (it is `--disable-slash-commands` that turns that OFF), and reads our
            # skills from ~/.gemini/config/skills -> dotfiles/.copilot/skills.
            local text="$PROMPT"
            if [[ -z "$text" ]]; then
                text="/$SKILL"
                if [[ -n "$SKILL_ARGS" ]]; then text="$text $SKILL_ARGS"; fi
            fi
            CMD=("$ANTIGRAVITY_BIN" -p "$text" --model "${MODEL:-gemini-3.1-pro-high}")
            # accept-edits + skip-permissions: a headless run has nobody to approve tool calls.
            CMD+=(--mode accept-edits --dangerously-skip-permissions)
            [[ -n "$EFFORT" ]] && CMD+=(--effort "$(clamp_effort "$EFFORT")")
            ;;
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

# Fall back EVEN WHEN LLM_CLIENT IS PINNED (changed 2026-07-31; it used to require LLM_CLIENT
# to be unset). Pinning expresses which client should do the work, not an instruction to fail
# the whole job when that client is unavailable — and a quota limit is precisely when the other
# clients earn their keep, since that is what killed the 2026-07-20 briefing.
# Opt out with LLM_FALLBACK=0.
#
# Since 2026-09-15 this walks the WHOLE remaining chain rather than one hardcoded partner, so
# with three clients installed a job survives two of them failing.
if [[ "${LLM_FALLBACK:-1}" == 1 ]]; then
    # MODEL is client-specific by definition (claude-sonnet-5 vs openclaw vs gemini-3.1-pro-high),
    # so carrying it into a retry would only fail it a second way. Drop it once and let each
    # fallback client use its own default. EFFORT needs no such handling: it is clamped per client.
    if [[ -n "$MODEL" ]] && [[ -n "$(fallback_clients "$CLIENT")" ]]; then
        echo "[lorite-llm] dropping --model '$MODEL' for the retries (models are client-specific)" >&2
        MODEL=""
    fi
    while read -r FALLBACK; do
        [[ -z "$FALLBACK" ]] && continue
        echo "[lorite-llm] $CLIENT failed (exit $STATUS) — retrying with $FALLBACK" >&2
        STATUS=0
        run_client "$FALLBACK" || STATUS=$?
        [[ $STATUS -eq 0 ]] && exit 0
        CLIENT="$FALLBACK"
    done < <(fallback_clients "$CLIENT")
fi

exit $STATUS
