#!/usr/bin/env bash
# Install the Traefik file-provider config that puts https://aw.lorite.eu behind
# Basic Auth. RUN THIS ON THE HOME SERVER (lorite-thinkcentre-m720q).
#
# Why a file-provider config instead of compose labels: Coolify escapes `$` when it
# re-emits the compose file, so `${AW_BASIC_AUTH}` in a label is never interpolated and
# reaches Traefik as a literal string ("error parsing BasicUser: ${AW_BASIC_AUTH}"),
# which makes Traefik drop the router -> 503 "no available server". The file provider is
# hot-reloaded (`--providers.file.watch=true`), so this takes effect with no redeploy,
# and the bcrypt line stays on the server instead of in this public repo.
#
# Usage:
#   ./install-traefik-auth.sh                      # reuse AW_BASIC_AUTH from the container
#   ./install-traefik-auth.sh 'admin:$2y$05$...'   # or pass an htpasswd line explicitly
#                                                  # (single-quote it: the hash has $)
# Generate a line with:  htpasswd -nbB admin 'a-long-unique-password'

set -euo pipefail

PROXY="coolify-proxy"
DEST="/traefik/dynamic/aw.yaml"
DOMAIN="aw.lorite.eu"
UPSTREAM="http://aw-server:5600"

AUTH="${1:-}"

if [ -z "$AUTH" ]; then
    container=$(docker ps --filter 'name=^aw-server-' --format '{{.Names}}' | head -n1)
    if [ -z "$container" ]; then
        echo "No running aw-server container found, and no htpasswd line given." >&2
        exit 1
    fi
    AUTH=$(docker inspect "$container" --format '{{range .Config.Env}}{{println .}}{{end}}' \
        | sed -n 's|^AW_BASIC_AUTH=||p' | head -n1)
    if [ -z "$AUTH" ]; then
        echo "AW_BASIC_AUTH is not set on $container. Pass an htpasswd line as \$1." >&2
        exit 1
    fi
    echo "Reusing AW_BASIC_AUTH from $container (user: ${AUTH%%:*})"
fi

# Sanity-check the shape before writing; a malformed line would break auth open-endedly.
case "$AUTH" in
    *:\$2[aby]\$*) : ;;
    *) echo "Refusing to write: '\$1' is not a user:bcrypt-hash line (expected user:\$2y\$...)." >&2
       exit 1 ;;
esac
case "$AUTH" in
    *"'"*) echo "Refusing to write: the htpasswd line contains a single quote." >&2; exit 1 ;;
esac

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

# priority 1000 makes this router win over Coolify's auto-generated `https-0-*` router,
# whose rule (Host(...) && PathPrefix(`/`)) is longer and would otherwise take precedence.
cat > "$tmp" <<YAML
# Managed by dotfiles: tools/lorite/aw-server-coolify/install-traefik-auth.sh
# Router + service + Basic Auth for https://${DOMAIN} (ActivityWatch).
# The bcrypt line lives ONLY here — never in the public dotfiles repo.
http:
  routers:
    aw:
      rule: "Host(\`${DOMAIN}\`)"
      entryPoints:
        - https
      priority: 1000
      middlewares:
        - aw-auth
      service: aw
      tls:
        certResolver: letsencrypt
  services:
    aw:
      loadBalancer:
        servers:
          - url: "${UPSTREAM}"
  middlewares:
    aw-auth:
      basicAuth:
        users:
          - '${AUTH}'
YAML

docker cp "$tmp" "${PROXY}:${DEST}"
docker exec -u root "$PROXY" chmod 644 "$DEST"

echo "Installed ${DEST} in ${PROXY}. Traefik hot-reloads it within a few seconds."
echo
echo "Verify (401 = auth is being enforced, which is what you want):"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' https://${DOMAIN}/"
echo "  curl -s -u admin:'<password>' https://${DOMAIN}/api/0/info"
