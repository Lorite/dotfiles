# CLAUDE.md — dotfiles

Personal Linux dotfiles **and** the single source of truth for AI coding-assistant customizations (agents, skills, global instructions) shared across **Claude Code, OpenCode, and GitHub Copilot**.

## Source-of-truth & sync model (read this first)

Author everything **once** under `.copilot/`. `install.sh` propagates it to each tool:

| Source (edit here) | Claude Code | OpenCode | Copilot |
|--------------------|-------------|----------|---------|
| `.copilot/agents/*.agent.md` | copied + tool names translated to Claude's (`normalize_frontmatter_for_claude`) → `~/.claude/agents/` | copied + frontmatter normalized → `~/.config/opencode/agents/` | symlinked → `~/.copilot/agents/` |
| `.copilot/skills/<name>/SKILL.md` | symlinked → `~/.claude/skills/` | symlinked → `~/.config/opencode/skills/` | symlinked → `~/.copilot/skills/` |
| `.copilot/CLAUDE.md` | symlinked → `~/.claude/CLAUDE.md` (user-level global memory; wired 2026-07-06 — documented but never actually linked before, so Claude Code sessions had not been loading it) | → `~/.config/opencode/AGENTS.md` | (global instructions) |

**Never hand-edit `~/.claude/agents/`, `~/.config/opencode/...`, or `~/.copilot/...`** — they are generated. Edit `.copilot/`, then run `./install.sh` to re-sync.

**Claude-only user settings** live in `.claude/settings.json` (tracked here, **symlinked** verbatim → `~/.claude/settings.json` by `install.sh`; not synced to OpenCode/Copilot, not generated). Edit the repo copy, not the symlink. Keep it secret-free — it's plain-text symlinked.

Four operative rules about sandboxing and subagents (the forensics behind each, and the full frontmatter-normalization mapping, are in the **`dotfiles-sandbox-and-spawning`** skill — read it before changing any `sandbox.*` key or the `install.sh` sync path):

- **The sandbox must stay `enabled: false` in the Claude Desktop app.** Agent mode already runs in a restricted user namespace, so `bwrap` can't nest and *every* sandboxed command hard-fails at startup. The `allowWrite`/`allowedDomains`/`allowLocalBinding`/`excludedCommands` block is harmless while disabled and becomes useful from the bare `claude` CLI (set `enabled: true` there).
- **`COWORK_VM_BACKEND=host` must stay set** (in `~/.local/share/applications/claude-desktop.desktop` and `~/.config/environment.d/claude-cowork.conf`, both outside this repo). Without it, spawned subagents run in a stale-filesystem microVM: their reads are stale, their writes are discarded, and they can't reach host `localhost` — while self-reporting success.
- **`normalize_frontmatter_for_claude()` in `install.sh` must keep translating tool names.** Agents are authored in the Copilot/VS-Code namespace (`read`, `execute`, `zotero/*`); Claude's are PascalCase + `mcp__<server>__*`. Sync the frontmatter verbatim and a spawned subagent gets an empty tool registry and fires nothing.
- **Spawning custom pipeline agents is reliable** with both of the above in place — run them inline *or* spawned. Agent defs are cached at session start, so `install.sh` changes only take effect in a **fresh session**.

## Authoring an agent

`.copilot/agents/<name>.agent.md` — copy the frontmatter shape from any existing agent there.

Tool namespaces follow the Copilot/VS Code set: `vscode`, `execute`, `read`, `edit`, `search`, `web`, `agent`, `todo`, `time/*`, `brave-search/*`, `google-calendar/*`, and extension tools like `antfu.slidev/*`.

**Every PhD-pipeline agent must carry the Obsidian read-first / log-often rule** — before acting, read the corresponding vault note (task / paper / project) for the latest context; log findings and decisions as you go via the `lorite-ai-chat-diary` skill (a dated diary entry in `ai_chats/diary/daily/` + the full detail in the linked note(s)). See `.copilot/CLAUDE.md` → "Obsidian note sync" for the canonical wording, and copy the rule into any new pipeline agent.

## Authoring a skill

`.copilot/skills/<name>/SKILL.md` with frontmatter `name`, `description`, `argument-hint`. **Skills** = user-invoked procedures (slash-command style, good for repeatable recipes). **Agents** = delegated personas with their own tool scope (good for multi-step, semi-autonomous work and orchestration).

## Related repos (the PhD workflow)

| Repo | Role |
|------|------|
| `~/git/lorite_ros2_humble_phd` | Robotics code (ROS 2 Humble; Spot + Crazyflie). Uses nested `AGENTS.md` files. Runs across **three Tailscale hosts** — see below. |
| `~/git/lorite-obsidian-notes` | Obsidian vault (edited manually). `ai_brain/` is AI-writable; key dirs: `tasks/`, `bases/`, `people/`, `templates/`, `work/`. |
| `~/git/Drone-localization-support-from-a-quadruped-robot-CLAWAR-2026-` | LaTeX paper (Springer `svproc`), CLAWAR 2026. |

The robotics repo runs on **three machines**, so "where do I run this?" is a real decision — GPU-heavy perception (FoundationPose / Isaac ROS DNN) only runs on the two with a discrete GPU. The two lab machines (Lab PC + Orin) are reachable from the laptop both over **Tailscale** (remote) and on the **lab LAN** (on-site):

| Machine | Tailscale name | Arch / GPU | Role |
|---------|----------------|------------|------|
| **Laptop** (the host Claude runs on) | `lori-ThinkPad-P15-Gen-2i` | x86_64 · RTX A2000 **4 GB** | Edit, `colcon build`, dry runs. **Too little VRAM for FoundationPose** (≥7.5 GB) — don't run heavy inference here. |
| **Lab PC** | `helix-lab-linux-asus-nvidia-rtx-3080-desktop` | x86_64 · RTX **3080** | Lab workstation; reaches RealSense + OptiTrack + Crazyradio; builds x86 TensorRT engines. |
| **AGX Orin on Spot** | `helix-lab-linux-spot-nvidia-jetson-agx-orin` | aarch64 · Orin 64 GB | On-robot deployment + onboard-runtime numbers; aarch64 `.plan` engines (don't transfer across arch). |

Typical flow: edit/build on the **laptop** → push → pull + run GPU work on the **Lab PC** or the **Orin** over SSH (Tailscale when remote, the lab LAN when on-site). (The repo's own `CLAUDE.md` carries the same table for in-repo agents.)

## On-the-go access (home server)

An always-on home server, **`lorite-thinkcentre-m720q`** (Tailscale `100.72.103.27`, OS user `lorite`), runs **Claude Code Remote Control** so you can work from the phone when the laptop is off. It keeps the vault live via Syncthing and can run **Obsidian headless** (Xvfb); Zotero there is **web-only**; **robotics / dev-container / hardware work stays on the laptop**.

Setup, the per-workspace tmux + systemd units, how to add a workspace, and the OAuth-401 re-auth procedure are in the **`dotfiles-home-server`** skill.

## Tooling / integrations available

Index only — configuration, modes, gotchas, and env keys for each of these are in the **`dotfiles-tooling`** skill. Read it before configuring, debugging, or changing any of them.

- **Obsidian CLI** (`~/.local/bin/obsidian`): needs the desktop app running with the vault open. Prefer Bases (`base:query`) for structured reads. AI writes only inside `ai_brain/` unless told otherwise. Never echo secrets from `obsidian-web-clipper-settings.json`.
- **Obsidian Web Clipper**: turns GitHub issues into `tasks/` notes.
- **Zotero** (`/usr/bin/zotero`) + the **`zotero-mcp` MCP server**: reference manager feeding the paper's `references.bib`, exposed to `lorite-paper-reader`. PDFs are linked files in `~/nextcloud/zotero/`; **all AI reading content goes to the Obsidian literature note** (`media/research/<title> - <citekey>.md`), never Zotero child notes. A 15-min timer guarantees **every Zotero item already has a literature note** — agents may assume it exists.
- **gh CLI**: GitHub issues/PRs on the robotics repo.
- **Obsidian daily notes, automatically**: an hourly timer creates and fully processes missing `diary/daily/` notes (yesterday back 7 days, never today). LLM time-slot summaries are *not* written by the timer — that's the **`lorite-daily-note`** skill.
- **SimpleTimeTracker late-entry enrichment (`refresh-stt`)**: hourly top-up of back-filled STT entries; creates Media DB notes for catalogable media and queues the rest to `ai_chats/notes/STT media to triage.md` (never guesses).
- **Nextcloud → Obsidian file bridge** (`tools/nextcloud-bridge/setup-bridge.sh`): symlinks curated Nextcloud folders into `vault/nextcloud/` for stable cross-machine wikilinks. Bridge **only curated subfolders, never the whole tree**, and point it at the **desktop sync client, not a WebDAV/rclone mount**.
- **Slidev**: `slidev-theme-lorite-phd` theme for presentations.
- **SimpleTimeTracker** (Android, via LlamaLab Automate): live work-session timing, `tools/lorite/simple_time_tracker.py start|stop|add_record`. Never echo the secret.
- **Dev-container execution model**: the robotics and CLAWAR paper repos run in Docker Dev Containers, but **run Claude/the editor on the host** — source is bind-mounted, only the toolchain needs the container. Shell in with `tools/lorite/in-ros2.sh <cmd>` (ROS 2) and `tools/lorite/in-tex.sh <cmd>` (texlive).

## The PhD research pipeline

All ten stages are built. The ordering — which agent descriptions refer to (e.g. "the stage-5 implementer") — is: **1** scout → **2** read → **2b** theorize → **3** task-manage → **4** note-take → **5** modify robotics code → **6** design experiments → **7** run trials → **8** analyse data → **9** write the paper → **10** build the deck. `ls .copilot/agents/` names the agent for each; their `description` frontmatter states the role.

Built incrementally **with the user** — every stage is a discussion, never full automation. Each new agent/skill is authored in `.copilot/`.

## Default session mode (`/lorite`)

A PhD chat is usually work on **one task with a corresponding Obsidian note**. The base session isn't a pipeline agent, so it doesn't inherit the read-first / log-often rule automatically — the **`lorite` skill** is how it opts in. Run `/lorite` at the start of a session (or when switching tasks): it pins the work to a `tasks/` note (deducing it from the task list when none is given), **reads that note first**, starts a **live SimpleTimeTracker** timer (`tools/lorite/simple_time_tracker.py`), commits to **logging as we go** via `lorite-ai-chat-diary`, and **routes** the work to the right `lorite-*` agent. `/lorite stop` ends the timer and writes the closing log — but **stopping is the AI's responsibility, not the user's**: whichever agent or skill holds the session must stop the timer the moment the work ends (deliverable finished, or the user pivots elsewhere), in the same turn as the closing log and `status` update, without being asked and without asking. A timer left running past the work silently inflates the day's tracking. Prefer this over ad-hoc work whenever the chat maps to a PhD task.

## Conventions

- Match each target repo's own `CLAUDE.md`/`AGENTS.md` conventions when working there.
- Git: commit and push directly to `main` (no feature branches on this repo); conventional commits (`type(scope): description`); run lint/format before committing when available.
- Shell scripts: keep lines under 120 chars (4-space indentation is set globally).
