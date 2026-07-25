# OpenCode web UI on the home server

Publishes `opencode web` from `lorite-thinkcentre-m720q` so you can drive a coding agent
from the phone. **Use the hardened path:**

```bash
sudo ~/git/dotfiles/tools/lorite/opencode-web/setup-hardened.sh opencode.lorite.eu
```

| | `setup-hardened.sh` **(use this)** | `setup.sh` *(superseded)* |
|---|---|---|
| Runs as | dedicated `opencode-web` user | `lorite` — **in the `docker` group, i.e. root** |
| Listens on | `127.0.0.1` only | Coolify bridge gateway |
| Reachability | Cloudflare Tunnel — **no inbound port** | Traefik, ports 80/443 open |
| Auth | Cloudflare Access (Google SSO + MFA) + Basic Auth | two Basic Auth layers |
| Firewall rules needed | none | a ufw rule for docker→host |

`setup.sh` is kept only as a no-Cloudflare fallback. It works, but it publishes an agent
running as a docker-group account behind a single password — see the risk section below.

The tunnel is what removes the complexity: because the host dials *out* to Cloudflare,
nothing listens on a public interface, so there is no reverse proxy, no bridge-gateway
binding and no firewall rule to get right.

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

### Both fixes are implemented in `setup-hardened.sh`

The section below is kept because it explains *why* the hardened script does what it does —
and it still describes `setup.sh` accurately, which is why that path is superseded.

**1. Cap the blast radius — a dedicated, unprivileged user.** This matters more than the
auth layer, and it is the one fix that survives a credential leak. `setup-hardened.sh`
creates `opencode-web`: not in `docker`/`sudo`/`adm`/`wheel`, no SSH keys, `nologin` shell.

Access is granted by **ACL, not ownership** — the vault is a Syncthing working copy owned
by `lorite`, and chowning it would disturb sync. The script adds traverse-only (`--x`) on
the home and `git/` dirs, `rwX` on the vault (with default ACLs so new files inherit), and
read-only on `.copilot/skills`. It then *proves* the cap by asserting `opencode-web` cannot
read `~/.ssh/id_ed25519`, `~/.config/lorite/`, or `/var/run/docker.sock`, and aborts if it can.

The systemd unit adds `ProtectSystem=strict`, `ProtectHome=tmpfs` (with `BindPaths` for
just the vault and its own home), a `@system-service` syscall filter, and explicit
`InaccessiblePaths` for the docker socket.

**Scope decision baked in:** the web agent gets **the vault and nothing else**. That covers
the phone use case (notes, tasks, light scripting). Full dev work stays on the laptop — if
you find yourself wanting the robotics repo here, that is a decision to revisit
deliberately, not to fix by widening the ACL.

**2. Cloudflare Access instead of Basic Auth.** Google SSO, MFA from your Google account,
sessions (24 h default, 15 min–1 month), per-email policy, audit log — and with the Tunnel,
no public inbound port at all. Free tier covers 50 users / 50 apps; you need one.
Rejected traffic never reaches the host. OpenCode's own Basic Auth stays underneath as a
second layer: browsers cache it per session, so it costs one prompt and covers an
Access/tunnel misconfiguration.

Known limitation, chosen deliberately: **browser-only.** `opencode attach` and any
scripted/API use get an HTML login redirect instead of the API. Fix if ever needed is a
Cloudflare **service token** plus a bypass policy. CLI use over SSH/Tailscale is unaffected.

Lesser alternatives: **Authentik/Authelia** forward-auth (Coolify one-click, self-hosted,
more moving parts), or an `ipAllowList` middleware (commented in `opencode.yaml`) if fixed
networks are acceptable. `tailscale serve` remains safest of all and needs no public
exposure — set aside only because off-tailnet access was wanted.

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
