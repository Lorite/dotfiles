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

## The nightly batch (lorite-nightly.target, 01:00, added 2026-07-31)

All four nightly server jobs run as **one systemd chain**, not four staggered timers: `lorite-nightly.timer` (01:00, `Persistent=true`, canonical in `tools/home-server/`) starts `lorite-nightly.target`, whose `Wants=` pulls in `ha-to-aw.service` → `aw-daily-export.service` (both from `~/git/lorite-activitywatch/systemd/`) → `dotfiles-pull.service` → `lorite-morning-briefing.service`, ordered strictly by `After=` lines inside each service. Each job starts the moment the previous one finishes: no dead gaps, no overlap. `After=` does not propagate failure, so a crashed job never blocks the rest, and each keeps its own `journalctl --user -u <name>` history. `StopWhenUnneeded=true` on the target lets it re-fire the next night. The morning briefing (the batch's Claude run, the last job) is why the server used to query Claude at a fixed nightly hour. **To move the hour, edit `OnCalendar` in `lorite-nightly.timer` only.** The four standalone timers (`ha-to-aw.timer`, `aw-daily-export.timer`, `dotfiles-pull.timer`, `lorite-morning-briefing.timer`) remain in their repos as fallbacks but stay **disabled** on the server, and both repos' install scripts keep them that way. Run the whole batch on demand with `systemctl --user start lorite-nightly.target`.

## Dotfiles freshness (dotfiles-pull.timer, added 2026-07-30)

The server's `~/git/dotfiles` does **not** stay current on its own, and its `~/.claude/CLAUDE.md` + skills are symlinks into that checkout, so phone sessions were loading stale rules (caught 2 days behind on 2026-07-30). `dotfiles-pull.service` (a `git pull --ff-only`) now runs nightly as the third job of the **`lorite-nightly.target` 01:00 batch** (see below), right before the morning briefing so it loads fresh skills. Canonical copies in `tools/home-server/`, live at `~/.local/bin/dotfiles-pull.sh` + `~/.config/systemd/user/dotfiles-pull.service` (the standalone `dotfiles-pull.timer` stays disabled since 2026-07-31).

It **deliberately never runs `install.sh`** (unattended-run bug history + this host's uutils traps): when a pull changes `.copilot/agents/`, it writes a flag to `~/.local/state/dotfiles-pull/install-sh-needed` and every later run repeats the reminder in its journal — run `install.sh` there manually, then delete the flag. A `--ff-only` failure (diverged checkout) shows as a failed `dotfiles-pull.service`.

**Control:** `tmux attach -t {phd,vault}`; `systemctl --user {status,restart,stop} claude-rc claude-rc-vault` (needs `XDG_RUNTIME_DIR=/run/user/$(id -u)` over SSH).

## Which LLM the nightly jobs use (set 2026-07-31)

Headless jobs go through **`lorite-llm.sh`**, whose built-in default is **OpenCode-first with Claude as fallback** (to keep low-effort work off the Claude quota). The server overrides that in **`~/.config/environment.d/lorite-llm.conf`** (machine-local; `install.sh` never overwrites an existing copy):

```
LLM_CLIENT=claude
LLM_MODEL=claude-sonnet-5
LLM_EFFORT=xhigh
```

So every headless job on this host runs **Claude Sonnet 5 at extra-high reasoning effort** — today that means the morning briefing plus the daily-note LLM summaries it performs (`obsidian_daily_note.py` deliberately does no LLM work itself). The **full model name is pinned rather than the `sonnet` alias**, so a future Sonnet release cannot silently change what runs overnight. `LLM_EFFORT` maps to Claude's `--effort` (`low|medium|high|xhigh|max`); unset means the client's own `settings.json` default, and OpenCode ignores it. Higher effort trades wall-clock for thoroughness, which suits jobs running at 01:00 with nobody waiting. Reload with `systemctl --user daemon-reload`, then confirm with `systemctl --user show-environment | grep -i llm`.

**Fallback (changed 2026-07-31):** pinning `LLM_CLIENT` selects the **primary** client only — a pinned client **still falls back** to the other one when it fails, and the retry drops `LLM_MODEL` because model names are client-specific. So a Claude quota limit no longer kills the job, which is what happened on 2026-07-20. `LLM_FALLBACK=0` opts out.

**The catch, worth knowing before you trust a briefing:** the morning briefing pins Claude for a *measured* reason — on 2026-07-25 OpenCode returned "✅ No issues found" on a commit where Claude caught live Google OAuth tokens committed in plaintext. With fallback now active, a Claude outage means that security audit silently runs on the weaker client. The swap is logged to the journal by `lorite-llm`, so check it when a briefing reports a clean audit after an outage. Add `Environment=LLM_FALLBACK=0` to `lorite-morning-briefing.service` if a false-negative audit is ever worse than a missing briefing.

## Auth note (401s)

The login is a subscription **OAuth** credential in `~/.claude/.credentials.json`. If the phone starts getting **401s**, the access token has expired — re-auth with an **interactive `claude` `/login`** (not `setup-token`), which stores a **refresh token** so it auto-refreshes; a token with no refresh token silently expires and 401s until manually re-logged (hit 2026-07-15).

`claude` lives at `~/.local/bin/claude`, which isn't on an interactive SSH shell's PATH by default (the wrapper prepends it) — call the full path or `export PATH="$HOME/.local/bin:$PATH"`.

## What works on the server vs. stays on the laptop

The Obsidian **vault is kept live by Syncthing**. There's no Obsidian *GUI* there, but **Obsidian runs headless on demand** (Xvfb) via **`tools/home-server/with-headless-obsidian.sh`** (installed to `~/.local/bin`), so the full `obsidian` CLI works — `eval`/`command`/Bases/**Virtual Linker**/**Media DB** — not just the direct file-write fallback.

The wrapper is on-demand (launch → run → stop), so it never fights the laptop's live instance over the Syncthing-synced `.obsidian/`; enabling it was a one-time `"cli":true` in the server's global `~/.config/obsidian/obsidian.json` (machine-local, not synced). It's a passthrough when Obsidian is already up (laptop) and degrades to file-only if it can't launch. See the task note *"Set up headless Obsidian on the home server for the pipeline"*. Agents can still fall back to direct file writes when they don't need the app.

**Zotero** runs **web-only** there (the `zotero-mcp` launcher auto-detects this — see the `dotfiles-tooling` skill; the Web API key is at `~/.config/paper-scout/zotero-api-key`).

**Robotics / dev-container / hardware work stays on the laptop** (can't move to a headless box).
