# CLAUDE.md — dotfiles

Personal Linux dotfiles **and** the single source of truth for AI coding-assistant
customizations (agents, skills, global instructions) shared across **Claude Code,
OpenCode, and GitHub Copilot**.

## Source-of-truth & sync model (read this first)

Author everything **once** under `.copilot/`. `install.sh` propagates it to each tool:

| Source (edit here) | Claude Code | OpenCode | Copilot |
|--------------------|-------------|----------|---------|
| `.copilot/agents/*.agent.md` | copied verbatim → `~/.claude/agents/` | copied + frontmatter normalized → `~/.config/opencode/agents/` | symlinked → `~/.copilot/agents/` |
| `.copilot/skills/<name>/SKILL.md` | symlinked → `~/.claude/skills/` | symlinked → `~/.config/opencode/skills/` | symlinked → `~/.copilot/skills/` |
| `.copilot/CLAUDE.md` | (global instructions) | → `~/.config/opencode/AGENTS.md` | (global instructions) |

**Never hand-edit `~/.claude/agents/`, `~/.config/opencode/...`, or `~/.copilot/...`** —
they are generated. Edit `.copilot/`, then run `./install.sh` to re-sync.

**Claude-only user settings** live in `.claude/settings.json` (tracked here, **symlinked**
verbatim → `~/.claude/settings.json` by `install.sh`; not synced to OpenCode/Copilot, not
generated). Edit the repo copy, not the symlink. It carries the **Bash-sandbox allowlist**:
the Claude **Desktop app runs the bubblewrap sandbox on by default**, which blocks subagents'
Bash from (a) writing outside the cwd and (b) reaching non-allowlisted hosts — so pipeline
agents couldn't write the vault / robotics repo / `~/.config/paper-scout`, reach Zotero's local
API (`localhost:23119`), the research APIs, or run the `docker exec` dev-container wrappers.
`sandbox.filesystem.allowWrite` + `sandbox.network.{allowLocalBinding,allowedDomains}` +
`excludedCommands: ["docker *","devcontainer *"]` are the knobs — but only when the sandbox can
actually run. **In the Desktop app the sandbox must be `enabled: false`**: agent mode already runs
inside a restricted user namespace, so `bwrap` can't create the *nested* userns it needs
(`nested userns is capability-restricted` / seccomp `setgroups` failure) and **every sandboxed
command hard-fails at startup**. `enableWeakerNestedSandbox` does **not** fix this — that flag only
addresses a later `/proc`-mount step, not userns creation; no `sandbox.*` key can grant back
`CAP_SYS_ADMIN` inside an already-restricted namespace. Disabling is safe because the Desktop app
itself provides the outer isolation boundary (the inner `bwrap` was redundant double-containment).
The `allowWrite`/`allowedDomains`/`allowLocalBinding`/`excludedCommands` block is harmless while
disabled and becomes useful if you instead run the agents from the **bare `claude` CLI** (no outer
namespace → `bwrap` nests fine → set `enabled: true` there). Keep this file secret-free (it's
plain-text symlinked).

**Spawned subagents run in a separate Cowork microVM — `.claude/settings.json` `sandbox.*` does
NOT control them.** Verified 2026-06-12: a spawned subagent (Agent/Task tool) reads a **stale
rootfs-image snapshot** of the vault (a note showed 4444 B where the live file was 7003 B, with a
different heading), has a **skewed clock** (VM image built 2026-03-26), and **cannot reach host
`localhost`** (Zotero `:23119`) — so its vault *writes are discarded* and its reads are stale,
while the **main session runs on the host and sees everything live** (which is why it self-reports
success and can't detect the problem). Mechanism: Claude Desktop's **Cowork** feature —
`/usr/lib/claude-desktop/.../app.asar.unpacked/cowork-vm-service.js` dispatches a pluggable backend:
`host` (run directly on the host, no isolation), `bwrap` (namespace sandbox), or `kvm` (QEMU/KVM
microVM; host dirs shared in via virtiofs but only the per-session workspace — everything else is
the stale image). Auto-detect prefers `bwrap`, but `bwrap` is non-functional here (same nested-userns
limit as above) so it falls back to the **kvm microVM** → the stale-FS symptom. **Fix: force the
host backend with `COWORK_VM_BACKEND=host`** (values `host|bwrap|kvm`), set in two host-side files
(not in this repo): a user desktop-entry override `~/.local/share/applications/claude-desktop.desktop`
(`Exec=env COWORK_VM_BACKEND=host /usr/bin/claude-desktop %u`) and
`~/.config/environment.d/claude-cowork.conf` (`COWORK_VM_BACKEND=host`). Takes effect on the **next
Claude Desktop launch** (the launcher cleans up the old cowork daemon, so a normal relaunch re-inits
the backend); revert by deleting the two files. With `host`, the stale-VM isolation is gone —
**verified 2026-06-12 23:37**: a *clean* spawn now reads a just-written host file and lands durable
writes on the live vault + reaches live Zotero (`200`), all cross-checked from the host. **But
spawning is still flaky / non-deterministic** — in the same session `lorite-paper-reader` spawned
twice and failed both times with *distinct* tool-bridge errors (run 1: corrupted Bash output — empty
`cat` on a non-empty file, garbled words, wrong/stale sizes; run 2: `<class 'AssertionError'>` on
every Bash call + the Read tool scoped to the project root), while a `general-purpose` spawn the
same minute was perfectly clean. So the remaining instability is in the **spawn/tool-bridge layer,
not the (now-fixed) VM filesystem**. **Operating rule: keep running pipeline agents that must touch
the live vault/Zotero INLINE in the main session (rock-solid); treat spawning as best-effort until
the flakiness is resolved.** (More-isolated alternative: keep the VM and virtiofs-mount specific `$HOME` dirs via
`additionalBinds` in `~/.config/Claude/claude_desktop_linux_config.json` — but that can't restore
localhost-service reachability, so Zotero stays unreachable from subagents.)

OpenCode normalization (`normalize_frontmatter_for_opencode` in `install.sh`):
`argument-hint→argumentHint`, `user-invocable→userInvocable`,
`tool-restrictions→toolRestrictions`, `tools:` arrays → `tools: {name: true}` map,
and `model:` array placeholders are dropped.

## Authoring an agent

`.copilot/agents/<name>.agent.md`:

```yaml
---
name: <kebab-name>
description: <one line — when this agent should be used>
argument-hint: "<example invocation the user might type>"
user-invocable: true            # optional
tools: [read, edit, search, execute, web, todo, 'time/*']
agents: [<subagent-name>, ...]  # optional — for orchestrator agents
---
# Role and instructions...
```

Tool namespaces follow the Copilot/VS Code set: `vscode`, `execute`, `read`, `edit`,
`search`, `web`, `agent`, `todo`, `time/*`, `brave-search/*`, `google-calendar/*`,
and extension tools like `antfu.slidev/*`.

**Every PhD-pipeline agent must carry the Obsidian read-first / log-often rule** — before acting,
read the corresponding vault note (task / paper / project) for the latest context; log findings and
decisions as you go via the `lorite-ai-chat-diary` skill (a dated diary entry in `ai_chats/diary/daily/` +
the full detail in the linked note(s)). See `.copilot/CLAUDE.md` → "Obsidian note sync" for the
canonical wording, and copy the rule into any new pipeline agent.

## Authoring a skill

`.copilot/skills/<name>/SKILL.md` with frontmatter `name`, `description`,
`argument-hint`. **Skills** = user-invoked procedures (slash-command style, good for
repeatable recipes). **Agents** = delegated personas with their own tool scope (good
for multi-step, semi-autonomous work and orchestration).

## Related repos (the PhD workflow)

| Repo | Role |
|------|------|
| `~/git/lorite_ros2_humble_phd` | Robotics code (ROS 2 Humble; Spot + Crazyflie). Uses nested `AGENTS.md` files. |
| `~/git/lorite-obsidian-notes` | Obsidian vault (edited manually). `ai_brain/` is AI-writable; key dirs: `tasks/`, `bases/`, `people/`, `templates/`, `work/`. |
| `~/git/Drone-localization-support-from-a-quadruped-robot-CLAWAR-2026-` | LaTeX paper (Springer `svproc`), CLAWAR 2026. |

## Tooling / integrations available

- **Obsidian CLI** (`~/.local/bin/obsidian`): requires the Obsidian desktop app
  running with the vault open. Prefer Bases (`base:query`) for structured reads.
  AI writes only inside `ai_brain/` unless explicitly told otherwise; if it must
  touch a note elsewhere, append under `# AI Generated` with `## Prompt` +
  `## AI Generated Answer`. Never echo secrets from `obsidian-web-clipper-settings.json`.
- **Obsidian Web Clipper**: used to turn GitHub issues into `tasks/` notes.
- **Zotero** (`/usr/bin/zotero`): reference manager feeding the paper's `references.bib`.
- **gh CLI**: GitHub issues/PRs on the robotics repo.
- **Slidev**: `slidev-theme-lorite-phd` theme for presentations.
- **SimpleTimeTracker** (Android, via **LlamaLab Automate Cloud Messaging**): live work-session
  timing. `tools/lorite/simple_time_tracker.py start|stop|add_record` POSTs to
  `https://llamalab.com/automate/cloud/message` an envelope `{secret,to,device,priority,payload}`
  where `payload.action` ∈ `start`/`stop`/`add_record` (`start`/`stop` = live timer, the
  prospective complement to the vault's retrospective `daily_time_tracker.py` blocks). Config from
  env `AUTOMATE_ANDROID_APP_{SECRET,TO,DEVICE}` (or `<vault>/.secrets/automate.env`) — never echo
  the secret.
- **Dev-container execution model**: the robotics (`lorite_ros2_humble_phd`) and CLAWAR paper repos
  each run inside a **Docker Dev Container**, but the Obsidian vault + dotfiles live on the host.
  So **run Claude/the editor on the host** (not "Reopen in Container") — the repo source is
  bind-mounted, so host edits are already live inside; only *running* the toolchain needs the
  container. Two thin host wrappers shell in (via `docker exec` / `devcontainer exec`, bringing the
  container up if down): `tools/lorite/in-ros2.sh <cmd>` (ROS 2 — colcon/ros2/gz; container
  `ros2_humble_dev`) and `tools/lorite/in-tex.sh <cmd>` (texlive — latexmk/chktex). No args → an
  interactive shell. The `lorite-ros2-operator`, `lorite-experiment-coder`, and `lorite-data-analyst`
  agents call `in-ros2.sh`; `lorite-paper-writer` calls `in-tex.sh`.

## Planned: PhD research-pipeline agents

A living plan, built incrementally **with the user** — every stage is a discussion,
never full automation. Each new agent/skill is authored in `.copilot/`.

| # | Pipeline stage | Agent / skill | Status |
|---|----------------|---------------|--------|
| 1 | Find research papers online | `lorite-paper-scout` | **built** |
| 2 | Read papers + Zotero | `lorite-paper-reader` | **built** |
| 2b | Theorize: research directions + concept notes (after reading, before design) | `lorite-robotics-theorist` | **built** |
| 3 | Task manager: TaskNotes + Calendar + GitHub issues | `lorite-task-manager` | **built** |
| 4 | Take notes in Obsidian | `lorite-obsidian-ai-brain` (existing; may extend) | exists |
| 5 | Modify robotics code | `lorite-ros2-operator` | **built** |
| 6 | Design experiments | `lorite-experiment-designer` | **built** |
| 7 | Write experiment code + run trials | `lorite-experiment-coder` (runs) / `lorite-ros2-operator` (deep nodes) | **built** |
| 8 | Check data + make plots | `lorite-data-analyst` | **built** |
| 9 | Write the LaTeX paper/article | `lorite-paper-writer` | **built** |
| 10 | Build the Slidev presentation | `lorite-slidev-presentation-*` (existing) | exists |

## Default session mode (`/lorite`)

A PhD chat is usually work on **one task with a corresponding Obsidian note**. The base session
isn't a pipeline agent, so it doesn't inherit the read-first / log-often rule automatically — the
**`lorite` skill** is how it opts in. Run `/lorite` at the start of a session (or when switching
tasks): it pins the work to a `tasks/` note (deducing it from the task list when none is given),
**reads that note first**, starts a **live SimpleTimeTracker** timer
(`tools/lorite/simple_time_tracker.py`), commits to **logging as we go** via `lorite-ai-chat-diary`,
and **routes** the work to the right `lorite-*` agent. `/lorite stop` ends the timer and writes the
closing log. Prefer this over ad-hoc work whenever the chat maps to a PhD task.

## Conventions

- Match each target repo's own `CLAUDE.md`/`AGENTS.md` conventions when working there.
- Git: commit and push directly to `main` (no feature branches on this repo);
  conventional commits (`type(scope): description`); run lint/format before
  committing when available.
- Shell scripts: 4-space indentation; keep lines under 120 chars.
