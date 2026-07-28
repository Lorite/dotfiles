# aw-server-rust + aw-sync for Coolify

Central ActivityWatch store for the home server (`lorite-thinkcentre-m720q`). Runs
**aw-server-rust** (REST API + web dashboard) and **aw-sync** (imports the laptop's
buckets, delivered by Syncthing). Part of the *"Use ActivityWatch to track the Linux
laptop activity time usage"* task, Phase 2.

There is no official ActivityWatch Docker image and no Dockerfile upstream, so the
`Dockerfile` here pulls the two prebuilt binaries out of the official
ActivityWatch release (`v0.13.2`) into a slim image (~140 MB). Built & tested
locally: API `/api/0/info` → `v0.13.2 (rust)`, web UI → HTTP 200, healthcheck
healthy, and `aw-sync` reaches the server over the shared network namespace.

## ⚠️ Security — read this first

aw-server has **no authentication and no HTTPS of its own** — so it must never be
exposed raw. It always sits behind something that adds those. Pick an access mode:

- **Option B — public `aw.lorite.eu` behind a login (the compose default).** A reverse
  proxy (Coolify's Traefik) terminates **HTTPS** and enforces **Basic Auth** in front;
  aw-server stays internal and only ever sees authenticated requests. The compose ships
  the Traefik labels for this; you set `AW_BASIC_AUTH` in Coolify. See "Option B" below.
- **Option A — Tailscale-only (most private; commented alternative in the compose).**
  Swap the Traefik labels for the `ports:` binding to the ThinkCentre's Tailscale IP
  (`100.72.103.27:5600`), never `0.0.0.0`. No public attack surface; tailnet-only.

Either way, data reaches the server over **Syncthing** (encrypted), so the server is
never network-exposed to *pull* from the laptop.

## Option B — public at aw.lorite.eu behind a login

You keep the same image; you just change how it's fronted. In the compose, **remove
the `ports:` host binding** on `aw-server` (Traefik reaches it on Coolify's internal
network — no host port needed) and instead:

1. **Coolify UI → the `aw-server` service → Domains:** set `https://aw.lorite.eu`,
   container port `5600`. Coolify provisions a Let's Encrypt certificate and the
   Traefik router automatically → you now have HTTPS.
2. **Add Basic Auth** (single user/password). Generate a bcrypt hash on any machine:
   ```bash
   htpasswd -nbB admin 'a-long-unique-password'      # apache2-utils
   # -> admin:$2y$05$....   (copy the whole line)
   ```
   Then install it **on the server** with the script in this directory — not as a compose
   label (see "Why not a compose label" below):
   ```bash
   ./install-traefik-auth.sh 'admin:$2y$05$....hash....'   # single-quote it: the hash has $
   # or, to reuse the AW_BASIC_AUTH value already set in Coolify:
   ./install-traefik-auth.sh
   ```
   It writes `/data/coolify/proxy/dynamic/aw.yaml` (a Traefik **file-provider** config
   holding the router, the service and the `aw-auth` middleware). Traefik watches that
   directory, so it applies within seconds — **no redeploy needed**.

### Why not a compose label

**Coolify escapes `$` when it re-emits the compose file**, so `${VAR}` inside a `labels:`
entry is *never* interpolated. The earlier
`traefik.http.middlewares.aw-auth.basicauth.users=${AW_BASIC_AUTH}` therefore reached
Traefik as the **literal string** `${AW_BASIC_AUTH}` →
`error parsing BasicUser: ${AW_BASIC_AUTH}` → Traefik dropped the router → the site
answered **503 "no available server"**. Setting the env var in Coolify does not fix this;
the value is correct, it just never reaches the label. Hard-coding the hash in the label
would work, but this repo is public. Hence the file provider.

**Fail-closed by design:** the compose only *references* `aw-auth@file`. If `aw.yaml` is
missing the middleware does not resolve and Traefik drops the router (503) rather than
serving your entire activity history with no login. Keep it that way.

**Honest tradeoff:** Basic Auth over HTTPS is fine for a personal dashboard, but it's
a *single credential* protecting your entire activity history on the public internet —
use a long, unique password. For stronger auth, put **Authentik/Authelia forward-auth**
in front instead (Coolify one-click + a forward-auth middleware). And the most private
option that still gives a nice HTTPS URL without a password is **`tailscale serve`**
(exposes it at `https://<host>.<tailnet>.ts.net`, reachable only by your own devices) —
consider that if you don't actually need access from non-Tailscale machines.

## Deploy in Coolify

1. **Prereq — Syncthing:** share the laptop's `~/ActivityWatchSync` folder to the
   server (Syncthing UI, same as the vault). Note the server-side path.
2. **New resource → Docker Compose**, source = this repo (`Lorite/dotfiles`),
   **base directory** = `tools/lorite/aw-server-coolify`.
3. **Edit `docker-compose.yaml` before deploy:**
   - `aw-sync.volumes` — set `/home/lorite/ActivityWatchSync` to the real server path
     from step 1 (or wire it as Coolify persistent storage / bind mount).
   - `aw-server.ports` — confirm `100.72.103.27` is the server's Tailscale IP.
4. **Domain:** for Option A (Tailscale-only) set **no** FQDN. For Option B set
   `https://aw.lorite.eu`, port `5600`, and run `install-traefik-auth.sh` on the server
   **before** the site is reachable — the auth middleware must exist first.
5. **Deploy.** Coolify builds the image and starts both services.

## Troubleshooting

### `no available server` (HTTP 503) at aw.lorite.eu

Traefik's catch-all (`default_redirect_503.yaml`) answering because **no router is
serving the host**. The container being `healthy` tells you nothing about routing —
check Traefik, not aw-server:

```bash
docker logs coolify-proxy --since 24h 2>&1 | grep -iE 'aw-server|aw-auth|level=err'
```

Two causes hit this deployment (both fixed, 2026-07-28):

- `error parsing BasicUser: ${AW_BASIC_AUTH}` — the `$`-escaping problem above. Fix:
  `install-traefik-auth.sh`.
- `Router aw cannot be linked automatically with multiple Services: ["aw",
  "http-0-…-aw-server", "https-0-…-aw-server"]` — once a domain is set in the Coolify UI,
  Coolify generates its **own** router *and* service. A hand-written
  `traefik.http.routers.aw.*` label then has three candidate services and Traefik refuses
  to guess. Fix: don't hand-write router/service labels; let Coolify generate them and
  only attach middlewares.

### `AxiosError: Request failed with status code 403` popup (data still renders)

`aw-server-rust` keeps a **CORS allowlist** and answers **403** to any request carrying an
`Origin` it doesn't recognise. Behind a real domain that is every XHR the web UI makes, so
the page loads from cache/SSR but each request errors. The server log is explicit:

```
CORS Error: Origin 'https://aw.lorite.eu' is not allowed to request
No 403 catcher registered. Using Rocket default.
```

v0.13.2 has **no `--cors` flag** — the allowlist only exists in `config.toml`, which lives
outside the `/data` volume and would be lost on redeploy. So `docker-entrypoint.sh`
regenerates it from **`AW_CORS_ORIGINS`** (set in the compose) on every start. To change or
add an origin, edit that env var and redeploy — never hand-edit config.toml in the
container.

Verified locally on the built image: with `AW_CORS_ORIGINS=https://aw.lorite.eu`, a request
sending that Origin returns **200**, while `Origin: https://evil.example.com` still returns
**403**. Keep it to the exact origins you serve from; do not use a wildcard.

Confirm the backend itself is fine (this path bypasses Traefik entirely):

```bash
docker exec coolify-proxy wget -qO- http://aw-server:5600/api/0/info     # {"version":"v0.13.2 (rust)"...}
docker exec coolify-proxy wget -qO- http://aw-server:5600/api/0/buckets/ # laptop buckets
```

`aw-server` is a stable Docker network alias for the container, so it survives redeploys
(the container *name* does not — it carries a timestamp suffix).

## Verify

```bash
# on the server (or from the laptop over Tailscale):
curl -s http://100.72.103.27:5600/api/0/info                       # -> {"version":"v0.13.2 (rust)"...}
curl -s http://100.72.103.27:5600/api/0/buckets/ | grep -o 'aw-watcher-window_lori-ThinkPad[^"]*'
# the laptop's buckets appear once Syncthing has delivered files AND aw-sync has run (~5 min)
```
Web dashboard: `http://100.72.103.27:5600` (over Tailscale).

## Phase 3 hook

Point the Obsidian pipeline at this server: run `aw_daily_export.py` with
`AW_SERVER=http://100.72.103.27:5600` (the script already honours that env var) to
export the server's aggregated data into the daily-note CSVs.

## Notes

- Bump `AW_VERSION` (Dockerfile arg + compose) to track newer ActivityWatch releases.
- If Coolify has trouble with `network_mode: service:aw-server`, the fallback is a
  single container running both binaries via a small entrypoint — ask and I'll add it.
- The laptop side (pushing buckets into `~/ActivityWatchSync`) is `aw-sync.service`
  in `tools/lorite/`, already installed and running.
