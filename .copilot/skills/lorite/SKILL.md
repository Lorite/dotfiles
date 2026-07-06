---
name: lorite
description: The default working mode for any chat-driven work session — PhD research, side-projects/coding, personal life & admin, meetings, writing — all in the one Obsidian vault + SimpleTimeTracker. Run it at the start of a chat to anchor the work to a specific Obsidian task note, start a live SimpleTimeTracker timer, hold the read-first / log-often contract for the whole session, and route to a specialized lorite-* agent when one fits (otherwise work inline). If no task is given, deduce it from the tasks/ notes. Use when starting work, switching tasks, or wrapping up.
argument-hint: "optional task hint, e.g. 'work on the CLAWAR pose-source experiment', 'fix the obsidian-SR data store', or 'plan the week' — or 'stop' to end the timer; omit to deduce the task"
---

# lorite — default work-session mode (anchor a task, time it, log it, route it)

The thing you talk to in a chat is the **base session**, not a pipeline agent — so the
read-first / log-often Obsidian rule baked into `lorite-experiment-coder`, `lorite-paper-reader`,
etc. doesn't apply to it automatically. This skill is how the base session adopts that rule for
**any tracked work** — PhD research, a side-project or coding task, personal life & admin, a
meeting, some writing — since it all lives in the one vault and is tracked in the one
SimpleTimeTracker. Run `/lorite` at the **start of a chat** and it (1) pins the session to a
specific **task note**, (2) times the work — a **live timer** when work starts now, or a
**back-filled block** when it's already done — (3) commits to **logging as we go**, and
(4) **routes** the work to a specialized agent when one fits (otherwise you work inline). Re-run
it to **switch task** or to **stop** the timer.

Vault: `~/git/lorite-obsidian-notes`. Timer script:
`~/git/dotfiles/tools/lorite/simple_time_tracker.py`. Dates `yyyy-MM-dd`, times `HH:mm`
(current local time from the `time` tool or `date "+%H:%M"`).

## Session contract (Opus 4.8 calibration)
For the whole anchored session, the user steers and the AI works:
- **Decision points, not drip-questions.** Confirm the task pick (step 1, an explicit `/lorite`
  argument that matches an existing task note counts as confirmed) and honor each routed agent's
  own approval gates; between those, make the minor calls yourself and note them. When a fork
  genuinely needs the user, present one batched proposal with a recommendation first.
- **The routing table is a set of triggers.** When the work matches a row, route to that agent/skill
  rather than improvising the same job inline; when no row matches, inline is correct — don't
  delegate for the sake of it.
- **Logs are resumable state.** Diary + note entries are how the user *and future AI sessions*
  resume the work and audit the process — log decisions with their why, exact replication commands,
  and only claims backed by this session's tool output (unverified → say so in the log).

## When to use
- **At the start of any work session** — PhD research, a side-project, life admin, a meeting,
  writing, anything you track — before doing the work, so it's anchored and timed.
- **When the task changes** mid-session — stop the old timer, re-anchor, start a new one.
- **At wrap-up** — `/lorite stop`: stop the timer and write the closing diary log.
- **To log already-finished work** — e.g. "create a task for what we did, log it, mark done": skip
  the live timer and back-fill a finished block with `add_record` (step 3, retrospective mode).

## Procedure

### 1. Determine the task (and its note)
Resolve, in order — confirm the pick with the user before starting the timer:
1. **Explicit** — the `/lorite` argument or the user's first message names the task/note.
2. **Deduce** — if nothing is given, list `tasks/` notes (`type: task`) **Bases-first** via the
   `lorite-obsidian-bases` skill (or `obsidian` CLI search); prefer ones that are in-progress /
   due today / recently edited. Read a candidate's **task text** only when the name is ambiguous.
   Propose the most likely task and ask the user to confirm or correct.
3. **Fallback** — if there's genuinely no matching task note, ask whether to (a) create one via
   `lorite-task-manager`, or (b) proceed untracked (no timer, log to today's diary only).

The "corresponding note", per `.copilot/CLAUDE.md → Obsidian note sync`, is the **task note**
first; else the relevant project / area / literature note it links (e.g. a research project note,
a side-project note, or a life-area note); else today's diary.

### 2. Read it first (context before action)
Read the task note (and the project / area / paper note it links) for the latest human + AI
context — status, decisions, prior findings. Don't re-derive what the note already records.
Surface the current state back to the user in a line or two.

### 3. Track the time — live timer, or back-fill a finished block
Pick the mode from when the work happens:

**Default (work starts now)** — start a running SimpleTimeTracker activity tied to the task note name:

```bash
python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py start \
  --activity Task --comment "<task-note name>"
```

**Retrospective (the work is already done)** — when the user asks you to *log/record* a piece of
work that's already finished, or you reach wrap-up and realize no live timer was ever running, do
**not** start a live timer. Back-fill a **finished block** with `add_record` instead:

```bash
python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py add_record \
  --activity Task --comment "<task-note name>" \
  --start "YYYY-MM-DD HH:MM:SS" --end "YYYY-MM-DD HH:MM:SS"
```

You usually don't know exactly when the user started — **propose your best estimate of start/end
and confirm before sending** (show it with `--dry-run` first). This is the right move whenever the
session is "create a task / log what we did / mark done" on already-completed work.

- `--comment` is the task-note **basename** (no `.md`, no `[[ ]]`) — the vault renders it as a
  `[[wikilink]]`, matching `daily_time_tracker.py`.
- For non-task work use a different `--activity` with a free-text `--comment`. Pick an activity
  that already exists in your SimpleTimeTracker (e.g. `Code`, `Read`, `Write`, `Meeting`, or
  whatever life/admin activities you track) rather than inventing a new one.
- `--dry-run` is a **global** flag: place it **before** the subcommand
  (`simple_time_tracker.py --dry-run add_record …`), not after — it prints the envelope (secret
  redacted) without sending.
- Transport = **LlamaLab Automate Cloud Messaging** (`POST https://llamalab.com/automate/cloud/message`),
  not a per-flow webhook. Config comes from env (or `<vault>/.secrets/automate.env`):
  `AUTOMATE_ANDROID_APP_SECRET` (**secret — never print**), `AUTOMATE_ANDROID_APP_TO`,
  `AUTOMATE_ANDROID_APP_DEVICE`. The Automate flow branches on `payload.action` (`start`/`stop`).
- If config is missing or the endpoint is unreachable the script exits non-zero with a clear
  message — **don't block the work**, tell the user the timer didn't start and continue.

### 4. Hold the log-often contract (the whole session)
For the rest of the session, log **as you work, not only at the end**, via the
**`lorite-ai-chat-diary`** skill: a lightweight dated entry in
`ai_chats/diary/daily/AI Chat - <date>` plus the full detail appended in the task/project note
under `# AI Generated`. Honor the write policy (`ai_brain/`-only free writes; elsewhere
append-only under `# AI Generated`; never rewrite hand-written content; never write secrets).
Log at: the session start (after step 2), after each substantive piece of work, and at wrap-up.

### 5. Route to a specialized agent when one fits (else work inline)
You (base session) can invoke any agent or skill — match the work to it and hand off, keeping the
timer + logging in this main thread. Routing is **optional and domain-specific**: a lot of work
(general coding, life admin, quick writing, ad-hoc tasks) has no specialized agent, so just do it
inline. Spawning an agent is the expensive path — only delegate when the stage genuinely matches.

**General (any domain):**

| Work | Agent / skill |
|------|------|
| Manage tasks / GitHub issues / calendar | `lorite-task-manager` |
| Capture / synthesize vault notes | `lorite-obsidian-ai-brain` (or the `lorite-obsidian-note` / `-markdown` / `-bases` / `-json-canvas` skills directly) |
| Prep or summarize a meeting | `lorite-meeting-prep`, `lorite-meeting-status-summary`, `lorite-recurring-meeting-docx` |
| Produce a Word / PDF / slide / spreadsheet deliverable | the `docx` / `pdf` / `pptx` / `xlsx` skills |
| Anything else (general coding, admin, ad-hoc) | handle inline in this session |

**PhD robotics-research pipeline:**

| Work | Agent |
|------|-------|
| Find papers online | `lorite-paper-scout` |
| Read a paper + note it in Zotero/vault | `lorite-paper-reader` |
| Theorize research directions / write concept notes | `lorite-robotics-theorist` |
| Modify robotics ROS 2 code (nodes/launch) | `lorite-ros2-operator` |
| Design an experiment | `lorite-experiment-designer` |
| Write experiment run-code + run trials / record bags | `lorite-experiment-coder` |
| Check data, compute metrics, make figures/tables | `lorite-data-analyst` |
| Write the LaTeX paper | `lorite-paper-writer` *(planned)* |
| Build a Slidev **paper** deck | `lorite-slidev-presentation-*` |
| Build a Slidev **meeting / status** deck (PhD 3-1, status updates) | `lorite-slidev-meeting-deck` |

### 6. Switch task / wrap up
- **Switch**: `/lorite stop`, then `/lorite <new task>` (step 1) — or just start the new activity,
  which the flow treats as switching the running activity.
- **Stop / wrap up**:

  ```bash
  python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py stop
  ```

  then write the closing `lorite-ai-chat-diary` entry summarizing the session. If no live timer was
  ever running (e.g. retrospective logging), back-fill the block with `add_record` (step 3) instead
  of `stop`. **Update the task's `status`** to reflect where the work landed (allowed agent values:
  todo / investigating / in-progress / blocked / pending-review / cancelled — never `done`):
  set **`pending-review`** when the session finished the task's deliverable and it now awaits the
  user's review; leave `in-progress` when work continues next session.

## Notes & gotchas
- **Confirm the task before starting the timer** — a wrong activity pollutes the day's tracking.
- **Bases need the Obsidian app running** for the CLI; if it's down, fall back to reading
  `tasks/*.md` frontmatter directly and say so.
- **This is the live, prospective complement** to the vault's retrospective
  `scripts/daily_time_tracker.py` (which buckets a day's activity into finished blocks). Both go
  through the same Automate flow; this skill's `start`/`stop` run the timer live, while
  `add_record` (and the vault script) back-fill finished blocks. The flow branches on
  `payload.action`.
- **Degrade gracefully** — missing timer, missing task, or app down should never block the actual
  work; note the gap and carry on.
