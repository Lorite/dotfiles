#!/usr/bin/env bash
# setup-bridge.sh — Bridge Nextcloud reference folders into the Obsidian vault.
#
# Creates per-machine symlinks under a dedicated vault subfolder (default
# vault/nextcloud/) pointing at real Nextcloud sync-client folders, so notes can
# embed/link files with stable vault-relative wikilinks (e.g. ![[nextcloud/papers/foo.pdf]])
# that resolve identically on every machine — while the actual bytes live in
# Nextcloud (editable by any app, offline-available via the sync client). The whole
# bridge subfolder is added to the vault's .stignore AND .gitignore so it is NEVER
# synced: targets differ per host (~/nextcloud on the laptop vs the server's data
# dir), and the /home/<user> path itself differs (lori vs lorite), so every machine
# must create its own links locally.
#
# IMPORTANT: point NEXTCLOUD_BASE at the Nextcloud *sync client* (real local files,
# e.g. ~/nextcloud), NOT a WebDAV mount (e.g. ~/nextcloud-all). WebDAV reads are
# slow, break when offline, and can serve stale cache — a hazard for Obsidian's
# indexer and for agents/scripts that read the files non-interactively.
#
# Only curated subfolders are bridged (never the whole Nextcloud tree): a
# whole-tree link makes Obsidian enumerate/watch thousands of unrelated files,
# pollutes the explorer/search/graph, and risks symlink recursion.
#
# Config (all optional, per-machine) from ~/.config/dotfiles/paths.env or the env:
#   NEXTCLOUD_BASE         default: $HOME/nextcloud                 (sync-client root — NOT WebDAV)
#   OBSIDIAN_VAULT         default: $HOME/git/lorite-obsidian-notes
#   NEXTCLOUD_VAULT_SUBDIR default: "nextcloud"  vault subfolder the links live under ("" = vault root)
#   NEXTCLOUD_BRIDGE       default: "zotero:papers"                 (space/newline "subfolder:linkname" pairs)
#
# Idempotent: safe to re-run. Refuses to replace a real (non-symlink) vault path.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
say() { echo -e "${BLUE}→${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }

# --- Config (per-machine) -------------------------------------------------------
PATHS_ENV="${DOTFILES_PATHS_ENV:-$HOME/.config/dotfiles/paths.env}"
if [ -f "$PATHS_ENV" ]; then
    # shellcheck disable=SC1090
    . "$PATHS_ENV"
fi
NEXTCLOUD_BASE="${NEXTCLOUD_BASE:-$HOME/nextcloud}"
OBSIDIAN_VAULT="${OBSIDIAN_VAULT:-$HOME/git/lorite-obsidian-notes}"
NEXTCLOUD_VAULT_SUBDIR="${NEXTCLOUD_VAULT_SUBDIR-nextcloud}"
NEXTCLOUD_BRIDGE="${NEXTCLOUD_BRIDGE:-zotero:papers}"

if [ ! -d "$OBSIDIAN_VAULT" ]; then
    warn "Vault '$OBSIDIAN_VAULT' not found — skipping Nextcloud→Obsidian bridge"
    exit 0
fi

say "Bridging Nextcloud folders into vault '$OBSIDIAN_VAULT'"
say "  base: $NEXTCLOUD_BASE"

# WebDAV footgun heuristic: warn if the base sits on a network/FUSE mount.
fstype="$(findmnt -no FSTYPE --target "$NEXTCLOUD_BASE" 2>/dev/null || true)"
case "$fstype" in
    *dav* | fuse | fuse.*)
        warn "base is on a '$fstype' mount — looks like WebDAV/network, not a sync client."
        warn "  Prefer the Nextcloud desktop sync client (real local files); WebDAV is"
        warn "  slow, offline-broken, and cache-stale for Obsidian + agents."
        ;;
esac

# --- Helpers --------------------------------------------------------------------

# Append a line to a file if not already present (exact match). Creates the file.
append_unique() {
    local file="$1" entry="$2"
    touch "$file"
    if grep -qxF "$entry" "$file" 2>/dev/null; then
        return 0
    fi
    printf '%s\n' "$entry" >>"$file"
    ok "added '$entry' to $(basename "$file")"
}

# Link <link_root>/<link> -> NEXTCLOUD_BASE/<sub>. Uses globals link_root/rel_prefix.
bridge_one() {
    local sub="$1" link="$2"
    local source="$NEXTCLOUD_BASE/$sub"
    local target="$link_root/$link"

    if [ ! -d "$source" ]; then
        warn "source '$source' not present on this machine — skipping '$link' (not synced here?)"
        return 0
    fi

    if [ -L "$target" ]; then
        if [ "$(readlink "$target")" = "$source" ]; then
            ok "'$rel_prefix$link' → '$source' (already linked)"
        else
            ln -sfn "$source" "$target"
            ok "'$rel_prefix$link' re-pointed → '$source'"
        fi
    elif [ -e "$target" ]; then
        # Never clobber a real vault folder/file — that would be hand-authored content.
        warn "'$target' exists as a real path (not a symlink) — refusing to replace; skipping"
        return 0
    else
        ln -sfn "$source" "$target"
        ok "'$rel_prefix$link' → '$source' (linked)"
    fi

    # When links sit at the vault root, ignore each individually (no parent to ignore).
    if [ -z "$subdir" ]; then
        append_unique "$OBSIDIAN_VAULT/.stignore" "/$link"
        append_unique "$OBSIDIAN_VAULT/.gitignore" "/$link"
    fi
}

# --- Run ------------------------------------------------------------------------
# All bridge links live under an optional dedicated subfolder (default vault/nextcloud/),
# which is entirely machine-local generated content — so ignore the whole subfolder once.
subdir="${NEXTCLOUD_VAULT_SUBDIR#/}"
subdir="${subdir%/}"
if [ -n "$subdir" ]; then
    link_root="$OBSIDIAN_VAULT/$subdir"
    rel_prefix="$subdir/"
    mkdir -p "$link_root"
    append_unique "$OBSIDIAN_VAULT/.stignore" "/$subdir"
    append_unique "$OBSIDIAN_VAULT/.gitignore" "/$subdir/"
    say "  links under: vault/$subdir/"
else
    link_root="$OBSIDIAN_VAULT"
    rel_prefix=""
fi

# shellcheck disable=SC2086  # intentional word-splitting of the "sub:link" pairs
for pair in $NEXTCLOUD_BRIDGE; do
    case "$pair" in
        *:*) ;;
        *)
            warn "bad bridge entry '$pair' (expected 'subfolder:linkname') — skipping"
            continue
            ;;
    esac
    bridge_one "${pair%%:*}" "${pair##*:}"
done

ok "Nextcloud → Obsidian bridge done"
