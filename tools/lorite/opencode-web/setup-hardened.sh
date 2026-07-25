#!/usr/bin/env bash
# Set up OpenCode's web UI on the home server the SAFE way:
#
#   * a dedicated unprivileged user (not in docker, not in sudo, no SSH keys)
#   * bound to 127.0.0.1 only
#   * published via a Cloudflare Tunnel (no inbound port at all)
#   * gated by Cloudflare Access (Google SSO) before traffic reaches the host
#
# This SUPERSEDES setup.sh (Traefik + Basic Auth). The tunnel makes the whole
# bridge-gateway / ufw / Traefik-router arrangement unnecessary: nothing listens on a
# public interface, so there is nothing to firewall.
#
#   sudo ./setup-hardened.sh opencode.lorite.eu
#
# Why the dedicated user matters more than the auth layer: `lorite` is in the `docker`
# group, which is root on this host via `docker run -v /:/host --privileged` without
# ever touching sudo, and holds the SSH key that reaches the Lab PC and the Orin. A
# credential leak on an agent running as `lorite` is a full host compromise. Running as
# `opencode-web` caps the blast radius at the vault.
set -euo pipefail

DOMAIN="${1:-}"
SVC_USER="${OPENCODE_WEB_USER:-opencode-web}"
PORT="${OPENCODE_PORT:-4096}"
OWNER="${OPENCODE_OWNER:-lorite}"
VAULT="${OPENCODE_VAULT:-/home/$OWNER/git/lorite-obsidian-notes}"
DOTFILES="${OPENCODE_DOTFILES:-/home/$OWNER/git/dotfiles}"
SVC_HOME="/home/$SVC_USER"

die()  { echo "ERROR: $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }

[[ $EUID -eq 0 ]] || die "run with sudo: sudo $0 <domain>"
[[ -n "$DOMAIN" ]] || die "usage: sudo $0 <domain>   (e.g. sudo $0 opencode.lorite.eu)"
[[ -d "$VAULT" ]] || die "vault not found at $VAULT (override with OPENCODE_VAULT=)"

# ── 1. The unprivileged service user ────────────────────────────────────────────
step "Service user: $SVC_USER"
if id "$SVC_USER" &>/dev/null; then
    echo "    exists"
else
    useradd --create-home --shell /usr/sbin/nologin "$SVC_USER"
    echo "    created"
fi

# Assert the properties we actually care about, rather than trusting the create above.
for bad in docker sudo adm wheel; do
    if id -nG "$SVC_USER" | tr ' ' '\n' | grep -qx "$bad"; then
        die "$SVC_USER is in the '$bad' group — that defeats the entire point. Remove it."
    fi
done
[[ ! -e "$SVC_HOME/.ssh" ]] || die "$SVC_HOME/.ssh exists — this account must hold no SSH keys"
echo "    verified: not in docker/sudo/adm/wheel, no SSH keys"

# ── 2. A shared opencode binary both accounts can run ───────────────────────────
step "OpenCode binary"
SRC_BIN="/home/$OWNER/.opencode/bin/opencode"
[[ -x "$SRC_BIN" ]] || die "opencode not found at $SRC_BIN"
if [[ ! -x /usr/local/bin/opencode ]] || ! cmp -s "$SRC_BIN" /usr/local/bin/opencode; then
    install -m 0755 "$SRC_BIN" /usr/local/bin/opencode
    echo "    installed /usr/local/bin/opencode ($(/usr/local/bin/opencode --version 2>/dev/null | head -1))"
else
    echo "    /usr/local/bin/opencode already current"
fi

# ── 3. Grant ONLY what the agent needs ──────────────────────────────────────────
# ACLs rather than chown/chgrp: the vault is a Syncthing working copy owned by $OWNER,
# and changing its ownership would disturb sync. ACLs add an entry without touching it.
step "Granting $SVC_USER access to the vault (and read-only skills)"
command -v setfacl >/dev/null || die "setfacl not found — install 'acl'"

# NO traverse grant on the owner's home. An earlier version granted `u:$SVC_USER:--x` on
# /home/$OWNER so the service could reach the vault by its real path — and that silently
# exposed everything world-readable beneath it (~/.config is 0775, so ~/.config/lorite
# was readable). Tightening those directories one at a time is whack-a-mole: any new
# world-readable dir under the home re-opens the hole.
#
# Instead the agent never sees the home at all. Bind mounts put exactly two things into
# its own tree under /srv/$SVC_USER, set up by root, so no host-path traversal is needed:
#
#     /srv/$SVC_USER/vault   <- $VAULT              (read/write)
#     /srv/$SVC_USER/skills  <- .copilot/skills     (read-only)
#
# Isolation is then structural rather than a property of permissions further up the tree.
chmod 750 "/home/$OWNER"          # still worth doing; container bind-mounts are unaffected
setfacl -x "u:$SVC_USER" "/home/$OWNER" 2>/dev/null || true
setfacl -x "u:$SVC_USER" "/home/$OWNER/git" 2>/dev/null || true

# Repair: an earlier version ran `install -d -o root -g root /srv/$SVC_USER/vault` without
# checking whether the vault was ALREADY bind-mounted there. On a re-run it was, so install
# chowned the mounted vault's root directory to root:root — which locked $OWNER out of
# their own vault (Syncthing, Obsidian and the note timers all write to it). Undo that
# before anything else, and before the ACL step below, which would otherwise re-apply on
# top of a wrongly-owned directory.
if [[ "$(stat -c %U "$VAULT")" != "$OWNER" ]]; then
    chown "$OWNER:$OWNER" "$VAULT"
    echo "    repaired ownership of $VAULT (was $(stat -c %U "$VAULT"), now $OWNER)"
fi

install -d -m 0755 -o root -g root "/srv/$SVC_USER"
# Create the mount points only when nothing is mounted there yet. On a re-run these are
# already bind mounts, and writing through them hits the REAL directories underneath:
# `install -d` would chown/chmod the vault itself (see the repair above), and EROFS on the
# read-only skills mount. This guard is what stops that.
for mp in "/srv/$SVC_USER/vault" "/srv/$SVC_USER/skills"; do
    mountpoint -q "$mp" || install -d -m 0755 -o root -g root "$mp"
done

# File-level access still comes from ACLs — they apply through the bind mount, since it is
# the same inodes. Default ACLs so files the agent creates stay accessible to both sides.
setfacl -R -m "u:$SVC_USER:rwX" "$VAULT"
setfacl -R -d -m "u:$SVC_USER:rwX" "$VAULT"
echo "    vault: read/write  ($VAULT -> /srv/$SVC_USER/vault)"

# ...except the vault's own secrets directory. Granting the whole vault would otherwise
# hand the agent $VAULT/.secrets/automate.env (the SimpleTimeTracker secret) and the
# Google OAuth client-secret JSON — the exact credentials this whole exercise is about.
if [[ -d "$VAULT/.secrets" ]]; then
    setfacl -R -x "u:$SVC_USER" "$VAULT/.secrets" 2>/dev/null || true
    find "$VAULT/.secrets" -type d -exec setfacl -d -x "u:$SVC_USER" {} + 2>/dev/null || true
    chmod -R go-rwx "$VAULT/.secrets"
    echo "    vault/.secrets: EXCLUDED from the grant, and no longer world-readable"
fi

# ── 3a. Bind mounts (systemd .mount units so they survive reboot) ───────────────
step "Bind-mounting the vault and skills into /srv/$SVC_USER"
mk_mount() {
    local src="$1" dst="$2" ro="$3"
    local unit; unit="$(systemd-escape -p --suffix=mount "$dst")"
    cat > "/etc/systemd/system/$unit" <<EOF
# Generated by setup-hardened.sh — gives $SVC_USER the path WITHOUT traversing /home/$OWNER.
[Unit]
Description=Bind $src -> $dst for $SVC_USER
# NO After=local-fs.target here. systemd implicitly orders mount units BEFORE
# local-fs.target, so declaring After= creates an ordering cycle; systemd resolves it by
# DROPPING the mount at boot, and opencode-web (which Requires= it) then never starts.
# Symptom: everything works until the first reboot, then Cloudflare returns 502.

[Mount]
What=$src
Where=$dst
Type=none
Options=bind${ro:+,ro}

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now "$unit" >/dev/null
    mountpoint -q "$dst" || die "bind mount failed: $dst"
    echo "    $dst  <- $src${ro:+  (read-only)}"
}
mk_mount "$VAULT" "/srv/$SVC_USER/vault" ""
if [[ -d "$DOTFILES/.copilot/skills" ]]; then
    mk_mount "$DOTFILES/.copilot/skills" "/srv/$SVC_USER/skills" "ro"
fi

# Repair damage from an earlier version of this script, which ran
# `chown -h $SVC_USER:$SVC_USER <symlink-to-skills>`. On uutils coreutils (this host ships
# 0.8.0) that DEREFERENCED the symlink and chowned the real dotfiles directory instead of
# the link. Put it back before doing anything else.
if [[ -d "$DOTFILES/.copilot/skills" ]] && [[ "$(stat -c %U "$DOTFILES/.copilot/skills")" != "$OWNER" ]]; then
    chown "$OWNER:$OWNER" "$DOTFILES/.copilot/skills"
    echo "    repaired ownership of $DOTFILES/.copilot/skills (was $SVC_USER, now $OWNER)"
fi

# Point OpenCode's skills lookup at the bind mount, not the real dotfiles path — the
# service account has no way to reach the latter, and shouldn't.
if [[ -d "/srv/$SVC_USER/skills" ]]; then
    setfacl -x "u:$SVC_USER" "$DOTFILES" 2>/dev/null || true
    setfacl -x "u:$SVC_USER" "$DOTFILES/.copilot" 2>/dev/null || true
    setfacl -R -m "u:$SVC_USER:rX" "$DOTFILES/.copilot/skills"
    install -d -o "$SVC_USER" -g "$SVC_USER" "$SVC_HOME/.config/opencode"
    # Created as root, and deliberately NOT chown'd. A symlink's own ownership does not
    # affect access — the target's permissions govern — so there is nothing to fix up,
    # and `chown -h` is what corrupted the dotfiles directory above. Not using runuser
    # either: $SVC_USER has a nologin shell by design.
    ln -sfn "/srv/$SVC_USER/skills" "$SVC_HOME/.config/opencode/skills"
    echo "    skills: read-only  (/srv/$SVC_USER/skills)"
fi

# ── 3a½. Let the service account SEE the vault's git repo ───────────────────────
# The vault is a git repo owned by $OWNER, but the service runs as $SVC_USER — and git
# >= 2.35.2 refuses a repo owned by another user ("detected dubious ownership") unless
# safe.directory says otherwise. Without this, OpenCode cannot derive a project from the
# vault and collapses it into the catch-all `global` project (worktree /), which breaks
# the web UI's project list and file picker. Found 2026-07-25: every git verification had
# run as $OWNER, so the failure only existed for the service user and was invisible.
step "Granting the service user git access to the vault (safe.directory)"
GITCFG="$SVC_HOME/.gitconfig"
[[ -f "$GITCFG" ]] || install -o "$SVC_USER" -g "$SVC_USER" -m 0644 /dev/null "$GITCFG"
for p in "$SVC_HOME/vault" "/srv/$SVC_USER/vault"; do
    if git config --file "$GITCFG" --get-all safe.directory 2>/dev/null | grep -qx "$p"; then
        echo "    already present: $p"
    else
        git config --file "$GITCFG" --add safe.directory "$p"
        echo "    added: $p"
    fi
done
chown "$SVC_USER:$SVC_USER" "$GITCFG"   # git config rewrites via rename, dropping the owner

# ── 3b. Tighten secret files that were world-readable ───────────────────────────
# Found on this host 2026-07-25: several .env / .secrets files at mode 0664 under a 0755
# home. Harmless while `lorite` was the only account; not harmless once a service account
# exists. Fixed unconditionally — these should never have been group/world readable.
step "Tightening world-readable secret files"
tightened=0
while IFS= read -r s; do
    [[ -e "$s" ]] || continue
    if [[ -d "$s" ]]; then chmod -R go-rwx "$s"; else chmod go-rwx "$s"; fi
    echo "    $s"
    tightened=$((tightened + 1))
done < <(
    find "/home/$OWNER" -maxdepth 4 \( -name .cache -o -name node_modules \) -prune -o \
        \( -type f \( -name '*.env' -o -name 'credentials*' \) -perm /o=r -print \) 2>/dev/null
    find "/home/$OWNER" -maxdepth 4 -type d -name '.secrets' -print 2>/dev/null
)
[[ $tightened -gt 0 ]] || echo "    none found (already tight)"

# Explicitly prove the agent CANNOT read the owner's secrets. This is the check that
# makes the hardening real rather than aspirational — it is what caught the 0755 home.
step "Verifying the blast radius is actually capped"
FORBIDDEN=(
    "/home/$OWNER"                       # the whole home is now off-limits, not just parts of it
    "/home/$OWNER/.ssh/id_ed25519"
    "/home/$OWNER/.config/lorite"
    "/home/$OWNER/.config/lorite/morning-briefing.env"
    "/home/$OWNER/.env"
    "/var/run/docker.sock"
    "/srv/$SVC_USER/vault/.secrets"
    "/srv/$SVC_USER/vault/.secrets/automate.env"
)
# Probe with REAL operations, never `test -r`/`test -w`. This host ships uutils coreutils
# 0.8.0, whose test builtin answers from the mode bits alone and ignores POSIX ACLs: it
# reported the vault as unwritable (other=r-x for uid 1001) while an actual write through
# the `user:opencode-web:rwx` entry succeeded. For a security assertion that failure mode
# is the dangerous direction — a path the account CAN reach could be reported as safe.
can_read() {
    local p="$1"
    if [[ -d "$p" ]]; then
        sudo -u "$SVC_USER" ls -A "$p" >/dev/null 2>&1
    else
        sudo -u "$SVC_USER" head -c1 "$p" >/dev/null 2>&1
    fi
}
can_write() {
    local p="$1" probe="$1/.opencode-probe.$$"
    if sudo -u "$SVC_USER" touch "$probe" 2>/dev/null; then
        rm -f "$probe" 2>/dev/null || true
        return 0
    fi
    return 1
}
explain_access() {
    local path="$1"
    echo "--- diagnosis for $path ---" >&2
    stat -c '  owner=%U group=%G mode=%A' "$path" >&2 || true
    getfacl -p "$path" 2>/dev/null | sed 's/^/  /' >&2 || true
    findmnt -no TARGET,SOURCE,OPTIONS -T "$path" 2>/dev/null | sed 's/^/  mount: /' >&2 || true
    echo "  service account: $(id "$SVC_USER")" >&2
    sudo -u "$SVC_USER" touch "$path/.opencode-write-probe" 2>&1 | sed 's/^/  probe: /' >&2 || true
    rm -f "$path/.opencode-write-probe" 2>/dev/null || true
}

for forbidden in "${FORBIDDEN[@]}"; do
    if [[ -e "$forbidden" ]] && can_read "$forbidden"; then
        die "$SVC_USER can read $forbidden — refusing to continue"
    fi
done

# The positive side, checked through the bind mount the service actually uses.
can_read  "/srv/$SVC_USER/vault" || { explain_access "/srv/$SVC_USER/vault"; die "$SVC_USER cannot read the vault mount"; }
can_write "/srv/$SVC_USER/vault" || { explain_access "/srv/$SVC_USER/vault"; die "$SVC_USER cannot write the vault mount"; }
if [[ -d "/srv/$SVC_USER/skills" ]]; then
    can_read "/srv/$SVC_USER/skills" || die "$SVC_USER cannot read the skills mount"
    # The skills mount must be read-only in practice, not just in the unit's Options=.
    ! can_write "/srv/$SVC_USER/skills" || die "the skills mount is WRITABLE — it must be read-only"
fi
echo "    can read+write /srv/$SVC_USER/vault, can read (not write) the skills mount"
echo "    cannot read: /home/$OWNER at all, the docker socket, or the vault's .secrets/"

# This script grants access; it must never take ownership away from $OWNER. An earlier
# version did exactly that via `chown -h` on a symlink, silently, and nothing caught it.
# Assert the invariant so a repeat is loud instead of silent.
STOLEN="$(find "$DOTFILES" "$VAULT" -maxdepth 3 -not -user "$OWNER" -printf '%u %p\n' 2>/dev/null | head -5)"
[[ -z "$STOLEN" ]] || die "these paths are no longer owned by $OWNER — this script must never do that:
$STOLEN"
echo "    $OWNER still owns everything under the vault and dotfiles"

# ── 4. Backend credentials (second layer, under Cloudflare Access) ──────────────
step "Backend credentials"
ENV_FILE="/etc/opencode-web.env"
if [[ -f "$ENV_FILE" ]]; then
    echo "    $ENV_FILE exists — leaving it alone"
else
    read -r -s -p "    OpenCode server password (min 16 chars, input hidden): " OC_PASS; echo
    [[ ${#OC_PASS} -ge 16 ]] || die "use at least 16 characters"
    umask 077
    cat > "$ENV_FILE" <<EOF
# Second auth layer, underneath Cloudflare Access. Browsers cache it per session, so it
# costs one prompt at session start and covers an Access/tunnel misconfiguration.
OPENCODE_PORT=$PORT
OPENCODE_SERVER_USERNAME=$OWNER
OPENCODE_SERVER_PASSWORD=$OC_PASS
EOF
    chmod 600 "$ENV_FILE"; chown root:"$SVC_USER" "$ENV_FILE"; chmod 640 "$ENV_FILE"
    unset OC_PASS
    echo "    written to $ENV_FILE (mode 640, root:$SVC_USER)"
fi

# ── 5. systemd system service ───────────────────────────────────────────────────
step "Installing opencode-web.service"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Derive the mount unit name with the SAME command that created it, rather than
# reconstructing it — systemd's escaping of a path and of a bare name do not always agree.
VAULT_MOUNT_UNIT="$(systemd-escape -p --suffix=mount "/srv/$SVC_USER/vault")"

# Substitute with bash parameter expansion, NOT sed. The unit name contains systemd's
# escaping (e.g. srv-opencode\x2dweb-vault.mount), and sed interprets `\x2d` in the
# REPLACEMENT text as a hex escape — silently turning it back into `-` and producing a
# Requires= that points at a unit which does not exist. Bash replaces literally.
unit_text="$(cat "$HERE/opencode-web.service")"
unit_text="${unit_text//__VAULT_MOUNT_UNIT__/$VAULT_MOUNT_UNIT}"
unit_text="${unit_text//__SVC_HOME__/$SVC_HOME}"
unit_text="${unit_text//__VAULT__/$VAULT}"
unit_text="${unit_text//__SVC_USER__/$SVC_USER}"
printf '%s\n' "$unit_text" > /etc/systemd/system/opencode-web.service

# Prove the reference resolves before asking systemd to honour it — this exact mismatch
# is what produced "Unit srv-opencode-web-vault.mount not found".
[[ -f "/etc/systemd/system/$VAULT_MOUNT_UNIT" ]] \
    || die "mount unit $VAULT_MOUNT_UNIT missing — the bind-mount step and this step disagree"
grep -qF "Requires=$VAULT_MOUNT_UNIT" /etc/systemd/system/opencode-web.service \
    || die "Requires= in opencode-web.service does not match the real unit name $VAULT_MOUNT_UNIT"
systemctl daemon-reload
systemctl enable --now opencode-web.service
sleep 6
systemctl is-active --quiet opencode-web.service \
    || die "service did not start — journalctl -u opencode-web -n 50"
ss -ltn | grep -q "127.0.0.1:$PORT" || die "not listening on 127.0.0.1:$PORT"
CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/app" || true)"
[[ "$CODE" == "401" ]] || die "backend returned HTTP $CODE without credentials, expected 401"
echo "    running as $SVC_USER, listening on 127.0.0.1:$PORT, returns 401 unauthenticated"

# ── 6. cloudflared ──────────────────────────────────────────────────────────────
step "cloudflared"
if ! command -v cloudflared >/dev/null; then
    ARCH="$(dpkg --print-architecture)"
    TMP="$(mktemp -d)"
    curl -fsSL -o "$TMP/cloudflared.deb" \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb"
    dpkg -i "$TMP/cloudflared.deb"
    rm -rf "$TMP"
    echo "    installed $(cloudflared --version 2>/dev/null | head -1)"
else
    echo "    already installed: $(cloudflared --version 2>/dev/null | head -1)"
fi

cat <<EOF

────────────────────────────────────────────────────────────────────────────
The host side is done and verified. Two interactive steps are yours — they open a
browser and must run as $OWNER, NOT root, because they write to ~/.cloudflared:

  cloudflared tunnel login          # pick the zone for $DOMAIN
  cloudflared tunnel create opencode

Then hand the rest to the companion script, which copies the credentials to
/etc/cloudflared (root:root 0600 — cloudflared.service runs as root, so pointing the
config at your home directory is what fails), writes and validates config.yml, adds the
DNS route, starts the service and verifies end to end:

  sudo $HERE/finish-tunnel.sh $DOMAIN

Last step, in the Cloudflare dashboard -> Zero Trust:
  * Settings -> Authentication: add Google as a login method
  * Access -> Applications: add a self-hosted app for $DOMAIN, enable Google on it
  * Policy: Action Allow, Include -> Emails -> your address
    (Access is deny-by-default; "That account does not have access" means no Allow
     policy matched. Zero Trust -> Logs -> Access shows the exact identity presented.)

Nothing is reachable from the internet until step 4 completes.
────────────────────────────────────────────────────────────────────────────
EOF
