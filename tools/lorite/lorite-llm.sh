#!/usr/bin/env bash
# lorite-llm — LLM client wrapper: OpenCode (Big Pickle) with Claude Code (Sonnet) fallback.
#
# Respects these env overrides (set in your shell or ~/.config/environment.d/lorite-llm.conf):
#   LLM_CLIENT=opencode|claude          — force a specific client (skip auto-detection)
#   LLM_MODEL=openclaw|sonnet|<model>   — override the model (passed as --model to claude)
#
# Usage:
#   lorite-llm <args...>          # exec's opencode (or claude if opencode is missing)
#   lorite-llm -p                 # prints which client would be used ("opencode" or "claude")
#   lorite-llm --dry-run ...      # prints the full command without executing
set -euo pipefail

# Auto-detect the client: opencode first, then claude.
# Honours LLM_CLIENT env override when set.
detect_client() {
    local forced="${LLM_CLIENT:-}"
    case "$forced" in
        opencode)
            if command -v opencode &>/dev/null || [ -x "$HOME/.opencode/bin/opencode" ]; then
                echo "opencode"; return 0
            fi
            echo "ERROR: LLM_CLIENT=opencode but opencode is not available" >&2; return 1
            ;;
        claude)
            if command -v claude &>/dev/null; then
                echo "claude"; return 0
            fi
            echo "ERROR: LLM_CLIENT=claude but claude is not available" >&2; return 1
            ;;
        "")
            # No override — auto-detect with opencode preference.
            if command -v opencode &>/dev/null || [ -x "$HOME/.opencode/bin/opencode" ]; then
                echo "opencode"; return 0
            elif command -v claude &>/dev/null; then
                echo "claude"; return 1
            fi
            echo "ERROR: neither opencode nor claude is available — install OpenCode (preferred) or Claude Code" >&2
            return 2
            ;;
        *)
            echo "ERROR: unknown LLM_CLIENT='$forced' — use 'opencode' or 'claude'" >&2; return 1
            ;;
    esac
}

# Resolve the model flag for claude. opencode doesn't need --model (Big Pickle is built-in).
model_flag_for() {
    local client="$1"
    local model="${LLM_MODEL:-}"
    if [[ "$client" == "claude" ]]; then
        echo "--model ${model:-sonnet}"
    fi
    # opencode: Big Pickle is the default — no flag needed.
}

# ── parse args ──────────────────────────────────────────────────────────────────
MODE=""
ARGS=()
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|-a) MODE="$1"; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --help|-h)
            echo "Usage: lorite-llm [-p] [--dry-run] <args...>"
            echo "  Set LLM_CLIENT=opencode|claude to force a client."
            echo "  Set LLM_MODEL=<model> to override the model (only affects claude)."
            exit 0 ;;
        *) ARGS+=("$1"); shift ;;
    esac
done

# ── modes ───────────────────────────────────────────────────────────────────────

# Detection mode (-p): print which client would be used.
if [[ "$MODE" == "-p" ]]; then
    detect_client; exit $?
fi

# Dry-run: print the full command without executing.
if [[ $DRY_RUN -eq 1 && ${#ARGS[@]} -gt 0 ]]; then
    CLIENT=$(detect_client) || exit $?
    MODEL_FLAG=$(model_flag_for "$CLIENT")
    case "$CLIENT" in
        opencode) echo "opencode ${ARGS[*]}" ;;
        claude)   echo "claude $MODEL_FLAG ${ARGS[*]}" ;;
    esac
    exit 0
fi

# Direct execution: exec the picked client.
if [[ ${#ARGS[@]} -gt 0 ]]; then
    CLIENT=$(detect_client) || exit $?
    MODEL_FLAG=$(model_flag_for "$CLIENT")
    case "$CLIENT" in
        opencode)
            echo "[lorite-llm] using opencode (Big Pickle)" >&2
            exec opencode "${ARGS[@]}" ;;
        claude)
            echo "[lorite-llm] falling back to claude ($MODEL_FLAG)" >&2
            exec claude $MODEL_FLAG "${ARGS[@]}" ;;
    esac
fi
