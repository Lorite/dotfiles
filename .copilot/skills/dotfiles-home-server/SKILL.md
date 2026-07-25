---
name: dotfiles-home-server
description: The always-on home server (lorite-thinkcentre-m720q) that runs Claude Code Remote Control so you can work from the phone when the laptop is off — why Remote Control not Dispatch, the tmux + systemd user services per workspace, how to add a workspace, the OAuth 401 re-auth procedure, and what runs there vs. stays on the laptop. Read when setting up, debugging, or extending on-the-go access.
argument-hint: "the phone is getting 401s from the home server"
---

# On-the-go access (home server)

To keep working with Claude from the **phone when the laptop is off**, an always-on home server runs **Claude Code Remote Control** (set up 2026-06-14). Server: `lorite-thinkcentre-m720q` (Lenovo ThinkCentre M720q), reachable over **Tailscale** (`100.72.103.27`), OS user `lorite`.

## Why Remote Control, not Dispatch

Remote Control is a **headless CLI** feature (outbound-HTTPS only, no inbound ports — the phone drives it via the Claude app *Code* tab / claude.ai/code); Dispatch needs the GUI Desktop app, which a headless server can't run. Requires a full-scope claude.ai (Pro/Max) **OAuth** login — not an API key (ensure no `ANTHROPIC_API_KEY` shadows it).

## Server mode and workspaces

`claude remote-control --spawn same-dir` so the phone can **spawn multiple on-demand chats** (capacity 32). Each Remote Control server is bound to **one directory**, so it maps to exactly one "New session" workspace in the app — run **one unit per workspace**.

Two run today: **`~/git/dotfiles`** (prefix `phd`) and **`~/git/lorite-obsidian-notes`** (prefix `vault`, added 2026-07-15).

## Persistence

Each server runs inside its own **tmux** session (`phd`, `vault`), launched by a systemd **user** service with boot-start via `loginctl enable-linger lorite`; a wrapper loop restarts it (Remote Control exits after a ~10 min network outage).

Canonical copies live in **`tools/home-server/`** — the shared wrapper `claude-rc-loop.sh` (takes `[WORKDIR] [PREFIX]` args) + one unit per workspace (`claude-rc.service` = dotfiles, `claude-rc-vault.service` = vault); the live copies on the server are `~/.local/bin/claude-rc-loop.sh` and `~/.config/systemd/user/claude-rc*.service`.

To add another workspace, drop in a new unit pointing the wrapper at that dir (it must be Claude-Code **workspace-trusted** first — run `claude` once there).

**Control:** `tmux attach -t {phd,vault}`; `systemctl --user {status,restart,stop} claude-rc claude-rc-vault` (needs `XDG_RUNTIME_DIR=/run/user/$(id -u)` over SSH).

## Auth note (401s)

The login is a subscription **OAuth** credential in `~/.claude/.credentials.json`. If the phone starts getting **401s**, the access token has expired — re-auth with an **interactive `claude` `/login`** (not `setup-token`), which stores a **refresh token** so it auto-refreshes; a token with no refresh token silently expires and 401s until manually re-logged (hit 2026-07-15).

`claude` lives at `~/.local/bin/claude`, which isn't on an interactive SSH shell's PATH by default (the wrapper prepends it) — call the full path or `export PATH="$HOME/.local/bin:$PATH"`.

## What works on the server vs. stays on the laptop

The Obsidian **vault is kept live by Syncthing**. There's no Obsidian *GUI* there, but **Obsidian runs headless on demand** (Xvfb) via **`tools/home-server/with-headless-obsidian.sh`** (installed to `~/.local/bin`), so the full `obsidian` CLI works — `eval`/`command`/Bases/**Virtual Linker**/**Media DB** — not just the direct file-write fallback.

The wrapper is on-demand (launch → run → stop), so it never fights the laptop's live instance over the Syncthing-synced `.obsidian/`; enabling it was a one-time `"cli":true` in the server's global `~/.config/obsidian/obsidian.json` (machine-local, not synced). It's a passthrough when Obsidian is already up (laptop) and degrades to file-only if it can't launch. See the task note *"Set up headless Obsidian on the home server for the pipeline"*. Agents can still fall back to direct file writes when they don't need the app.

**Zotero** runs **web-only** there (the `zotero-mcp` launcher auto-detects this — see the `dotfiles-tooling` skill; the Web API key is at `~/.config/paper-scout/zotero-api-key`).

**Robotics / dev-container / hardware work stays on the laptop** (can't move to a headless box).
