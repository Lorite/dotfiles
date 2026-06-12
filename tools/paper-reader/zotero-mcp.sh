#!/usr/bin/env bash
# Launch the zotero-mcp server (github.com/54yyyu/zotero-mcp; PyPI: zotero-mcp-server)
# in HYBRID mode — reads hit the LOCAL Zotero API (localhost:23119, no key, fast), while
# writes go through the Zotero WEB API with the read/write key. This is the same
# read-local/write-web split the curl + add_to_collection.py / zotero_note.py helpers use.
#
# Why a wrapper: it keeps the Web API key OUT of every MCP-client config (~/.claude.json,
# OpenCode, Copilot) — the secret is sourced at launch from the gitignored paper-scout home
# (chmod 600), never inlined. The numeric library id is not secret.
#
# Registered with Claude Code (user scope) by install.sh, equivalently:
#   claude mcp add --scope user zotero -- /home/<you>/git/dotfiles/tools/paper-reader/zotero-mcp.sh
#
# Pilot scope (2026-06): only lorite-paper-reader consumes this server; lorite-paper-scout
# still uses the connector/curl flow (and fetch_attach.py for paywalled PDFs — which this
# server cannot replace, since it does not drive the authenticated institutional proxy).
set -euo pipefail

HOME_DIR="${PAPER_SCOUT_HOME:-$HOME/.config/paper-scout}"

export ZOTERO_LOCAL="true"                                        # read from the running desktop app
export ZOTERO_LIBRARY_TYPE="${ZOTERO_LIBRARY_TYPE:-user}"
export ZOTERO_LIBRARY_ID="${ZOTERO_LIBRARY_ID:-15209457}"         # numeric web userID (not secret)
export ZOTERO_EMBEDDING_MODEL="${ZOTERO_EMBEDDING_MODEL:-default}" # local all-MiniLM-L6-v2 (free, offline)

key_file="$HOME_DIR/zotero-api-key"
if [[ -z "${ZOTERO_API_KEY:-}" && -f "$key_file" ]]; then
    ZOTERO_API_KEY="$(cat "$key_file")"
    export ZOTERO_API_KEY
fi

bin="$HOME/.local/bin/zotero-mcp"
[[ -x "$bin" ]] || bin="$(command -v zotero-mcp || true)"
[[ -n "$bin" ]] || { echo "zotero-mcp not found on PATH — run: uv tool install 'zotero-mcp-server[all] @ git+https://github.com/54yyyu/zotero-mcp'" >&2; exit 127; }

exec "$bin" serve "$@"
