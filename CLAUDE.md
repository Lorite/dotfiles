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
`excludedCommands: ["docker *","devcontainer *"]` fix that. Add a research-API host here when an
agent hits a new sandbox network prompt. `enableWeakerNestedSandbox: true` is **required in the
Desktop app**: its agent mode is itself a namespaced env where `bwrap` can't create a *nested*
user namespace (`nested userns is capability-restricted` / seccomp `setgroups` failure), so
without it every sandboxed command hard-fails at startup; the flag makes the inner sandbox
bind-mount the existing `/proc` (safe because the Desktop app provides the outer boundary).
Keep this file secret-free (it's plain-text symlinked).

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
