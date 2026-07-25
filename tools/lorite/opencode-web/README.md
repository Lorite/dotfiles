# OpenCode web UI on the home server (public domain + Traefik Basic Auth)

Publishes `opencode web` from `lorite-thinkcentre-m720q` at a public HTTPS domain behind
Basic Auth, so you can drive a coding agent from the phone from any network.

```bash
cd ~/git/dotfiles/tools/lorite/opencode-web && ./setup.sh opencode.lorite.eu
```

## ⚠️ Read this before publishing — the blast radius is bigger than "a coding agent"

`aw.lorite.eu` exposes a **read-only dashboard**. This exposes a shell. And the account it
runs as is not an ordinary one. On `lorite-thinkcentre-m720q`, `lorite` is in:

| Group | What it grants whoever reaches the web UI |
|-------|-------------------------------------------|
| `docker` | **root on the host.** `docker run -v /:/host --privileged` bypasses `sudo` entirely — no password prompt involved |
| `sudo` | password-gated, so not directly usable — but irrelevant given the line above |
| — | `~/.ssh/id_ed25519`, the key that reaches the **Lab PC and the AGX Orin** |

So the honest statement is: **one Basic Auth password on the public internet guards root
on the home server, the Obsidian vault, Nextcloud, Immich, Home Assistant, and SSH access
to the two lab machines.** The auth layer is not the weakest link here — the service
account is.

### What this setup already does

- **Two independent Basic Auth layers** — Traefik's and OpenCode's own
  (`OPENCODE_SERVER_USERNAME`/`PASSWORD`). Use *different* passwords.
- **Rate limiting in front of the auth check**, so the password can't be brute-forced at
  internet speed (Basic Auth has no lockout of its own).
- **The backend never binds to `0.0.0.0`** — only the Coolify bridge gateway, so it is
  unreachable from LAN, Tailscale and the internet except through Traefik.
- **`setup.sh` refuses to publish** unless the backend returns `401` without credentials.

### The two things that would actually make this safe

Ranked by how much risk they remove. Neither is done yet.

**1. Cap the blast radius — run it as a dedicated, unprivileged user.** This matters more
than the auth layer, and it is the one fix that survives a credential leak:

```bash
sudo useradd -m -s /bin/bash opencode-web          # NOT in docker, NOT in sudo, no SSH keys
sudo usermod -aG lorite opencode-web               # only what it must read
# move the unit + env file to that user, re-run setup.sh as them
```
Cost: it loses the `obsidian` CLI/Xvfb session and anything keyed to `lorite`'s home. Worth
deciding *what the web agent is actually for* — if it's vault edits and light scripting, a
restricted user covers it; if it's full dev work, keep that on the laptop and don't publish it.

**2. Replace Basic Auth with Cloudflare Access.** You already run Cloudflare DNS and
Traefik already holds a `CF_DNS_API_TOKEN`, so the account and tooling are in place.
Cloudflare Access gives real SSO (Google), **MFA**, sessions, per-email allowlists and an
audit log — none of which Basic Auth has — and with a Tunnel the service needs no public
inbound port at all. Free tier covers this. `cloudflared` is **not currently installed**.

Lesser alternatives: **Authentik/Authelia** forward-auth (Coolify one-click; self-hosted
equivalent of the above, more moving parts), or an `ipAllowList` middleware (see the
commented block in `opencode.yaml`) if you can live with fixed networks.

`tailscale serve` remains the safest option and needs no public exposure — rejected here
only because off-tailnet access was wanted.

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
