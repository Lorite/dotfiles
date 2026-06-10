---
name: lorite
description: The default working mode for a PhD chat session — run it at the start of a chat to anchor the work to a specific Obsidian task note, start a live SimpleTimeTracker timer, hold the read-first / log-often contract for the whole session, and route to the specialized lorite-* pipeline agents. If no task is given, deduce it from the tasks/ notes. Use when starting work, switching tasks, or wrapping up.
argument-hint: "optional task hint, e.g. 'work on the CLAWAR pose-source experiment' or 'stop' to end the timer — omit to deduce the task"
---

# lorite — default PhD session mode (anchor a task, time it, log it, route it)

The thing you talk to in a chat is the **base session**, not a pipeline agent — so the
read-first / log-often Obsidian rule baked into `lorite-experiment-coder`, `lorite-paper-reader`,
etc. doesn't apply to it automatically. This skill is how the base session adopts that rule: run
`/lorite` at the **start of a chat** and it (1) pins the session to a specific **task note**,
(2) starts a **live time-tracker**, (3) commits to **logging as we go**, and (4) **routes** the
work to the right specialized agent. Re-run it to **switch task** or to **stop** the timer.

Vault: `~/git/lorite-obsidian-notes`. Timer script:
`~/git/dotfiles/tools/lorite/simple_time_tracker.py`. Dates `yyyy-MM-dd`, times `HH:mm`
(current local time from the `time` tool or `date "+%H:%M"`).

## When to use
- **At the start of a PhD work session** — before doing the work, so it's anchored and timed.
- **When the task changes** mid-session — stop the old timer, re-anchor, start a new one.
- **At wrap-up** — `/lorite stop`: stop the timer and write the closing diary log.

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
first; else the paper's literature note; else the project note (e.g. the Conference Paper).

### 2. Read it first (context before action)
Read the task note (and the project/paper note it links) for the latest human + AI context —
status, decisions, prior findings. Don't re-derive what the note already records. Surface the
current state back to the user in a line or two.

### 3. Start the live timer
Start a running SimpleTimeTracker activity tied to the task note name:

```bash
python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py start \
  --activity Task --comment "<task-note name>"
```

- `--comment` is the task-note **basename** (no `.md`, no `[[ ]]`) — the vault renders it as a
  `[[wikilink]]`, matching `daily_time_tracker.py`.
- For non-task work use a different `--activity` (e.g. `Code`, `Read`, `Write`, `Meeting`) with a
  free-text `--comment`.
- Add `--dry-run` to show the envelope first (the secret is redacted) before sending.
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

### 5. Route to the right specialized agent
You (base session) can invoke any pipeline agent — match the work to the stage and hand off,
keeping the timer + logging in this main thread:

| Work | Agent |
|------|-------|
| Find papers online | `lorite-paper-scout` |
| Read a paper + note it in Zotero/vault | `lorite-paper-reader` |
| Manage tasks / GitHub issues / calendar | `lorite-task-manager` |
| Take/synthesize vault notes | `lorite-obsidian-ai-brain` |
| Modify robotics ROS 2 code (nodes/launch) | `lorite-ros2-operator` |
| Design an experiment | `lorite-experiment-designer` |
| Write experiment run-code + run trials / record bags | `lorite-experiment-coder` |
| Check data, compute metrics, make figures/tables | `lorite-data-analyst` |
| Write the LaTeX paper | `lorite-paper-writer` *(planned)* |
| Build the Slidev deck | `lorite-slidev-presentation-*` |

Spawning an agent is the expensive path — only delegate when the stage genuinely matches;
otherwise do the work inline and keep logging.

### 6. Switch task / wrap up
- **Switch**: `/lorite stop`, then `/lorite <new task>` (step 1) — or just start the new activity,
  which the flow treats as switching the running activity.
- **Stop / wrap up**:

  ```bash
  python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py stop
  ```

  then write the closing `lorite-ai-chat-diary` entry summarizing the session.

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
  PhD work; note the gap and carry on.
