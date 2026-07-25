#!/usr/bin/env bash
# Set up the OpenCode web UI on the home server, published at a public domain behind
# Traefik Basic Auth (Coolify's proxy) with HTTPS from the existing Let's Encrypt resolver.
#
#   ./setup.sh <domain>          e.g. ./setup.sh opencode.lorite.eu
#
# Shape (see opencode.yaml and ../opencode-serve.service for the why):
#   opencode serve  -- systemd USER service on the host, bound to the Coolify bridge
#                      gateway only (not 0.0.0.0), with its own Basic Auth
#   Traefik         -- terminates HTTPS, enforces a SECOND Basic Auth, proxies to it
#
# Secrets are never written by this script and never enter git. It prompts you to
# create them; the htpasswd hash and the backend password are yours to choose.
set -euo pipefail

DOMAIN="${1:-}"
PORT="${OPENCODE_PORT:-4096}"
DYNAMIC_DIR="/data/coolify/proxy/dynamic"
ENV_FILE="$HOME/.config/lorite/opencode-serve.env"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }

[[ -n "$DOMAIN" ]] || die "usage: $0 <domain>   (e.g. $0 opencode.lorite.eu)"
[[ -x "$HOME/.opencode/bin/opencode" ]] || die "opencode not found at ~/.opencode/bin/opencode"

# ── 1. Resolve the Coolify bridge gateway ───────────────────────────────────────
# Binding here (not 0.0.0.0) keeps the agent off the LAN, Tailscale and the internet;
# only containers on the coolify network — i.e. Traefik — and the host can reach it.
step "Resolving the Coolify docker-network gateway"
GATEWAY="$(docker network inspect coolify \
    --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>/dev/null || true)"
[[ -n "$GATEWAY" ]] || die "could not read the 'coolify' docker network gateway — is Coolify running?"
echo "    gateway: $GATEWAY  (backend will be http://$GATEWAY:$PORT)"

# ── 2. Backend credentials (OpenCode's own Basic Auth) ──────────────────────────
step "Backend credentials → $ENV_FILE"
mkdir -p "$(dirname "$ENV_FILE")"
if [[ -f "$ENV_FILE" ]]; then
    echo "    exists — leaving it alone (delete it to regenerate)"
else
    read -r -p "    OpenCode server username [lorite]: " OC_USER
    OC_USER="${OC_USER:-lorite}"
    read -r -s -p "    OpenCode server password (input hidden): " OC_PASS; echo
    [[ ${#OC_PASS} -ge 16 ]] || die "use at least 16 characters — this password guards shell access"
    umask 077
    cat > "$ENV_FILE" <<EOF
# Written by tools/lorite/opencode-web/setup.sh — NOT in git, mode 600.
OPENCODE_BIND_ADDR=$GATEWAY
OPENCODE_PORT=$PORT
OPENCODE_SERVER_USERNAME=$OC_USER
OPENCODE_SERVER_PASSWORD=$OC_PASS
EOF
    chmod 600 "$ENV_FILE"
    unset OC_PASS
    echo "    written (mode 600)"
fi

# Keep the bind address current even if the docker network was recreated.
sed -i "s|^OPENCODE_BIND_ADDR=.*|OPENCODE_BIND_ADDR=$GATEWAY|" "$ENV_FILE"

# ── 3. systemd user service ─────────────────────────────────────────────────────
step "Installing the opencode-serve user service"
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 "$HERE/../opencode-serve.service" "$HOME/.config/systemd/user/opencode-serve.service"
systemctl --user daemon-reload
systemctl --user enable --now opencode-serve.service
sleep 5
systemctl --user is-active --quiet opencode-serve.service \
    || die "opencode-serve did not start — check: journalctl --user -u opencode-serve"
ss -ltn | grep -q "$GATEWAY:$PORT" \
    || die "opencode-serve is running but not listening on $GATEWAY:$PORT"
echo "    listening on $GATEWAY:$PORT"

# Prove the backend rejects unauthenticated requests before anything is published.
CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://$GATEWAY:$PORT/app" || true)"
[[ "$CODE" == "401" ]] || die "backend answered HTTP $CODE without credentials, expected 401 — refusing to publish"
echo "    backend correctly returns 401 without credentials"

# ── 3b. Let Traefik's container actually reach the host ─────────────────────────
# ufw is active on this host and drops traffic from docker bridges into the host, so
# without this rule Traefik gets a connection timeout and the site 504s with no clue
# why. Scope it to the coolify subnet and this one port — not a blanket bridge allow.
step "Allowing the coolify subnet to reach $GATEWAY:$PORT (ufw)"
SUBNET="$(docker network inspect coolify \
    --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || true)"
[[ -n "$SUBNET" ]] || die "could not read the 'coolify' docker network subnet"
if sudo ufw status | grep -q "$GATEWAY $PORT"; then
    echo "    rule already present"
else
    sudo ufw allow from "$SUBNET" to "$GATEWAY" port "$PORT" proto tcp \
        comment "opencode web backend (Traefik -> host)"
    echo "    added: from $SUBNET to $GATEWAY:$PORT/tcp"
fi

# Verify from INSIDE the coolify network — this is the step that catches a firewall
# or bind mistake, and it is the one that silently fails if skipped.
step "Verifying reachability from the coolify network"
REACH="$(docker run --rm --network coolify busybox:latest \
    wget -q -S -O /dev/null "http://$GATEWAY:$PORT/app" 2>&1 | grep -oE 'HTTP/[0-9.]+ [0-9]+' | head -1 || true)"
case "$REACH" in
    *401) echo "    reachable, and returns 401 as expected" ;;
    "")   die "coolify network cannot reach $GATEWAY:$PORT — check ufw and the bind address" ;;
    *)    die "unexpected response from inside the coolify network: $REACH" ;;
esac

# ── 4. Traefik Basic Auth users file ────────────────────────────────────────────
step "Traefik Basic Auth"
if sudo test -f "$DYNAMIC_DIR/opencode.htpasswd"; then
    echo "    $DYNAMIC_DIR/opencode.htpasswd exists — leaving it alone"
else
    command -v htpasswd >/dev/null || die "htpasswd not found — install apache2-utils"
    echo "    This is a SECOND credential, in front of the backend one. Use a different password."
    read -r -p "    Traefik username [lorite]: " TR_USER
    TR_USER="${TR_USER:-lorite}"
    HASH="$(htpasswd -nB "${TR_USER}")"   # prompts for the password itself, twice
    sudo mkdir -p "$DYNAMIC_DIR"
    printf '%s\n' "$HASH" | sudo tee "$DYNAMIC_DIR/opencode.htpasswd" >/dev/null
    sudo chmod 644 "$DYNAMIC_DIR/opencode.htpasswd"
    unset HASH
    echo "    written"
fi

# ── 5. Traefik dynamic config ───────────────────────────────────────────────────
step "Publishing the Traefik router for $DOMAIN"
TMP="$(mktemp)"
sed -e "s|__DOMAIN__|$DOMAIN|g" \
    -e "s|__BACKEND_URL__|http://$GATEWAY:$PORT|g" \
    "$HERE/opencode.yaml" > "$TMP"
sudo install -m 0644 "$TMP" "$DYNAMIC_DIR/opencode.yaml"
rm -f "$TMP"
echo "    installed $DYNAMIC_DIR/opencode.yaml (Traefik watches this dir — no restart needed)"

cat <<EOF

Done. Remaining manual steps:

  1. DNS — point $DOMAIN at this host in Cloudflare (the Let's Encrypt resolver here
     uses the Cloudflare DNS-01 challenge, so the record must exist before the cert issues).
  2. Wait ~60 s, then check:  curl -I https://$DOMAIN/app     -> expect 401
                              curl -I -u <user>:<pass> https://$DOMAIN/app -> expect 200
  3. Certificate trouble:     docker logs coolify-proxy --tail 50 | grep -i acme

Reminder about what you just published: OpenCode is a coding agent with shell access on
the machine that also runs your Obsidian vault, Nextcloud, Immich and Home Assistant.
Two Basic Auth layers guard it, but both are single credentials on the public internet.
Use long, unique passwords, and consider putting Authentik/Authelia forward-auth in front
(Coolify one-click) if this becomes more than occasional phone use.
EOF
