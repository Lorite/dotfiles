# OpenCode web UI on the home server (public domain + Traefik Basic Auth)

Publishes `opencode web` from `lorite-thinkcentre-m720q` at a public HTTPS domain behind
Basic Auth, so you can drive a coding agent from the phone from any network.

```bash
cd ~/git/dotfiles/tools/lorite/opencode-web && ./setup.sh opencode.lorite.eu
```

## ⚠️ Read this before publishing

`aw.lorite.eu` exposes a **read-only dashboard**. This exposes a **coding agent with shell
access** on the machine that also runs the Obsidian vault, Nextcloud, Immich and Home
Assistant. A leaked credential here is remote code execution, not a data leak.

Mitigations built into this setup:

- **Two independent Basic Auth layers** — Traefik's, and OpenCode's own
  (`OPENCODE_SERVER_USERNAME`/`PASSWORD`). Use *different* passwords; either one alone
  being misconfigured still leaves the agent guarded.
- **The backend never binds to `0.0.0.0`.** It binds to the Coolify bridge gateway, so it
  is unreachable from the LAN, Tailscale and the internet — only Traefik and the host can
  talk to it.
- **`setup.sh` refuses to publish** if the backend answers anything but `401` without
  credentials, or if the coolify network can't reach it.

The genuinely stronger option, if this becomes more than occasional phone use, is
**Authentik/Authelia forward-auth** (Coolify one-click) in front of the Traefik router —
real sessions and MFA instead of one password. The most private option remains
`tailscale serve`, which needs no public exposure at all.

## Why a host service and not a Coolify container

OpenCode needs the host's git repos, the Obsidian vault, the `obsidian` CLI, the headless
Obsidian Xvfb wrapper and the Python tooling. Containerizing it means rebuilding that whole
toolchain in an image and bind-mounting the rest — much more fragile than running the
binary where the tooling already lives. So:

```
phone ──HTTPS──> Traefik (coolify-proxy)  ──HTTP──>  opencode serve
                 Basic Auth #1                       Basic Auth #2
                 Let's Encrypt (Cloudflare DNS-01)    systemd user service on the host
                                                      bound to 10.0.1.x:4096 only
```

Coolify still owns the certificate and the proxy; only the process is outside it.

## Pieces

| File | Role |
|------|------|
| `../opencode-serve.service` | systemd **user** unit running `opencode serve`, bound to the bridge gateway |
| `opencode.yaml` | Traefik dynamic config (router + Basic Auth + HTTPS redirect + backend) |
| `setup.sh` | resolves the gateway, writes creds, installs both, opens ufw, verifies |
| `~/.config/lorite/opencode-serve.env` | **not in git**, mode 600 — bind address + backend credentials |
| `/data/coolify/proxy/dynamic/opencode.htpasswd` | Traefik's bcrypt users file |

## Gotchas found the hard way

- **`ufw` is active and drops docker-bridge → host traffic.** Without the scoped
  `ufw allow from <coolify subnet> to <gateway> port <port>` rule, Traefik gets a
  connection *timeout* and the site 504s with nothing useful in the logs. `setup.sh`
  adds the rule and then proves reachability from inside the coolify network.
- **OpenCode serves the UI unauthenticated by default.** With no
  `OPENCODE_SERVER_PASSWORD` set, `opencode serve` happily serves `/app` to anyone. The
  systemd unit therefore hard-requires its `EnvironmentFile` (no leading `-`).
- **The bridge gateway can change** if the coolify docker network is recreated. `setup.sh`
  re-resolves it and rewrites `OPENCODE_BIND_ADDR` on every run — re-run it if the site
  starts 504ing after Docker maintenance.
- **Traefik watches `/data/coolify/proxy/dynamic/`** (`--providers.file.watch=true`), so
  config changes apply without restarting the proxy.
- **Certificates use the Cloudflare DNS-01 challenge**, so the DNS record must exist
  *before* the cert can issue — port 80 reachability is not enough.

## Verify

```bash
curl -I https://opencode.lorite.eu/app                    # expect 401
curl -I -u <user>:<pass> https://opencode.lorite.eu/app   # expect 200
systemctl --user status opencode-serve
journalctl --user -u opencode-serve -n 50
docker logs coolify-proxy --tail 50 | grep -i acme        # certificate trouble
```
