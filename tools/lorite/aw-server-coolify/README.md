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

aw-server has **no authentication and no HTTPS**. **Do NOT assign a public domain**
to this service in Coolify. Access is Tailscale-only: the compose binds the port to
the ThinkCentre's Tailscale IP (`100.72.103.27:5600`), never `0.0.0.0`. Data reaches
the server over Syncthing (encrypted), so the server is never network-exposed to pull
from the laptop.

## Deploy in Coolify

1. **Prereq — Syncthing:** share the laptop's `~/ActivityWatchSync` folder to the
   server (Syncthing UI, same as the vault). Note the server-side path.
2. **New resource → Docker Compose**, source = this repo (`Lorite/dotfiles`),
   **base directory** = `tools/lorite/aw-server-coolify`.
3. **Edit `docker-compose.yaml` before deploy:**
   - `aw-sync.volumes` — set `/home/lorite/ActivityWatchSync` to the real server path
     from step 1 (or wire it as Coolify persistent storage / bind mount).
   - `aw-server.ports` — confirm `100.72.103.27` is the server's Tailscale IP.
4. **Do NOT set a public FQDN / domain** for the service (see security note).
5. **Deploy.** Coolify builds the image and starts both services.

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
