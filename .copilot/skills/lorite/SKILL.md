---
name: lorite
description: The default working mode for any chat-driven work session — PhD research, side-projects/coding, personal life & admin, meetings, writing — all in the one Obsidian vault + ActivityWatch. Run it at the start of a chat to anchor the work to one or several Obsidian task notes, start a live declaration per anchored task, hold the read-first / log-often contract for the whole session, and route to a specialized lorite-* agent when one fits (otherwise work inline). If no task is given, deduce it from the tasks/ notes. Use when starting work, adding or switching tasks, or wrapping up.
argument-hint: "optional task hint(s), e.g. 'work on the CLAWAR pose-source experiment', 'fix the obsidian-SR data store', or 'plan the week' — 'add <task>' to anchor a second one alongside, 'stop [<task>]' to end one or all timers; omit to deduce the task"
---

# lorite — default work-session mode (anchor the task(s), time them, log them, route them)

The thing you talk to in a chat is the **base session**, not a pipeline agent — so the read-first / log-often Obsidian rule baked into `lorite-experiment-coder`, `lorite-paper-reader`, etc. doesn't apply to it automatically. This skill is how the base session adopts that rule for **any tracked work** — PhD research, a side-project or coding task, personal life & admin, a meeting, some writing — since it all lives in the one vault and is tracked in the one timeline. Run `/lorite` at the **start of a chat** and it (1) pins the session to one or more specific **task notes**, (2) times the work — a **live declaration per anchored task** when work starts now, or a **back-filled block** when it's already done — (3) commits to **logging as we go**, and (4) **routes** the work to a specialized agent when one fits (otherwise you work inline). Re-run it to **anchor another task**, **switch task**, or **stop** one or all of the timers.

**Several tasks can be anchored at once**, because work genuinely overlaps: a build or an agent grinding on one task while another is being written up is two real streams, not one. `lorite_intent.py` therefore accepts several running declarations and closes them by name, and the day is not inflated by the overlap: `intent_resolve.py` splits every observed minute evenly across the declarations covering it. Anchor a second task when its work is **actually running in this session**, not speculatively (see "Anchoring more than one task" below).

Vault: `~/git/lorite-obsidian-notes`. Timer scripts: **`~/git/dotfiles/tools/lorite/lorite_intent.py`** (ActivityWatch, primary) and `~/git/dotfiles/tools/lorite/simple_time_tracker.py` (SimpleTimeTracker, run in parallel during the transition). Dates `yyyy-MM-dd`, times `HH:mm` (current local time from the `time` tool or `date "+%H:%M"`).

## Session contract (Opus 4.8 calibration)
For the whole anchored session, the user steers and the AI works:
- **Decision points, not drip-questions.** Confirm the task pick (step 1, an explicit `/lorite` argument that matches an existing task note counts as confirmed) and honor each routed agent's own approval gates; between those, make the minor calls yourself and note them. When a fork genuinely needs the user, present one batched proposal with a recommendation first.
- **The routing table is a set of triggers.** When the work matches a row, route to that agent/skill rather than improvising the same job inline; when no row matches, inline is correct — don't delegate for the sake of it.
- **Logs are resumable state.** Diary + note entries are how the user *and future AI sessions* resume the work and audit the process — log decisions with their why, exact replication commands, and only claims backed by this session's tool output (unverified → say so in the log).
- **Stopping the timer is the AI's job, not the user's.** The timer is started without being asked, so it must be stopped without being asked. **The moment the work on an anchored task is finished — that deliverable done, or the user pivots away from it — stop that task's declaration** (step 6) as part of wrapping up, in the same turn, alongside the closing log and the `status` update. With several anchored, stop **each one as its own work ends**, not all of them at the end: a stream left running past its work is exactly the inflation this guards against. Do not wait for `/lorite stop`, do not ask "shall I stop the timer?", and never end a turn reporting completed work while its declaration is still running. `/lorite stop` is a convenience for the user, not the only trigger.
- **Every anchored task is a full anchor.** Each one gets read first (step 2), logged as you go (step 4), stopped when its work ends, and a `status` update at wrap-up. If you are not going to do all four for a task, do not anchor it.

## When to use
- **At the start of any work session** — PhD research, a side-project, life admin, a meeting, writing, anything you track — before doing the work, so it's anchored and timed.
- **When the task changes** mid-session — stop the old timer, re-anchor, start a new one.
- **When a second task starts running alongside** the first (a long build, a delegated agent, an interleaved errand): anchor it too and start its own declaration, leaving the first running.
- **At wrap-up** — stop the timer(s) and write the closing diary log. Triggered **either** by the user (`/lorite stop`, or `/lorite stop <task>` for just that one) **or** by the AI noticing the work is done / the user has moved on — whichever comes first (see the session contract).
- **To log already-finished work** — e.g. "create a task for what we did, log it, mark done": skip the live timer and back-fill a finished block with `add_record` (step 3, retrospective mode).

## Procedure

### 1. Determine the task(s) (and their notes)
Resolve, in order — confirm the pick with the user before starting the timer. When the user names **several** tasks, resolve each the same way and confirm them in **one** batched message, not one ask per task:
1. **Explicit** — the `/lorite` argument or the user's first message names the task/note.
2. **Deduce** — if nothing is given, list `tasks/` notes (`type: task`) **Bases-first** via the `lorite-obsidian-bases` skill (or `obsidian` CLI search); prefer ones that are in-progress / due today / recently edited. Read a candidate's **task text** only when the name is ambiguous. Propose the most likely task and ask the user to confirm or correct.
3. **Fallback** — if there's genuinely no matching task note, ask whether to (a) create one via `lorite-task-manager`, or (b) proceed untracked (no timer, log to today's diary only).

The "corresponding note", per `.copilot/CLAUDE.md → Obsidian note sync`, is the **task note** first; else the relevant project / area / literature note it links (e.g. a research project note, a side-project note, or a life-area note); else today's diary.

#### Anchoring more than one task
Anchor a second (or third) task when its work is **actually live in this session**, and only then. The test is whether real time is going into it right now, not whether it is on your mind:

- **Yes**: a `colcon build` or a long trial recording running under task A while you draft task B; a delegated agent working task A while you review task B with the user; two threads the user is genuinely alternating between within the same stretch.
- **No**: a task you merely plan to get to later (anchor it when you start it), a five-minute detour inside the main task (that is the same task), or a task nobody is working while the session runs.

**Keep it to 2 or 3.** Past that, every observed minute is split so many ways that no task's number means anything, and the per-note logs get thin. If the user asks for more, say so and propose the sequential alternative: anchor one, stop it, anchor the next.

**Confirm the whole set at once**, then declare each. When a task's work ends mid-session, stop *its* declaration (step 6) and leave the others running.

### 2. Read it first (context before action)
Read the task note (and the project / area / paper note it links) for the latest human + AI context — status, decisions, prior findings. Don't re-derive what the note already records. Surface the current state back to the user in a line or two. **Do this for every anchored task before its declaration starts**, not just the first one: an anchor you never read is an anchor you will log badly.

### 3. Track the time — live timer, or back-fill a finished block
Pick the mode from when the work happens:

**Default (work starts now)** — start a running declaration tied to the task note name:

```bash
LORITE_INTENT_SOURCE=claude python3 ~/git/dotfiles/tools/lorite/lorite_intent.py start \
  --activity Task --task "<task-note name>"
python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py start \
  --activity Task --comment "<task-note name>"
```

**Several tasks at once** — run `lorite_intent.py start` again for each additional anchored task, without stopping the first. `status` lists everything running:

```bash
LORITE_INTENT_SOURCE=claude python3 ~/git/dotfiles/tools/lorite/lorite_intent.py start \
  --activity Task --task "<second task-note name>"
python3 ~/git/dotfiles/tools/lorite/lorite_intent.py status
```

**SimpleTimeTracker only ever holds the primary task.** It has a single live activity and no API of its own, so it cannot represent overlap: run its `start` for the task in focus and leave the concurrency to ActivityWatch, which is the destination anyway. If the focus moves to another anchored task for a long stretch, `stop` and re-`start` STT on that one. Do not try to fake overlap in STT.

**Retrospective (the work is already done)** — when the user asks you to *log/record* a piece of work that's already finished, or you reach wrap-up and realize no live timer was ever running, do **not** start a live timer. Back-fill a **finished block** with `add_record` instead:

```bash
LORITE_INTENT_SOURCE=claude python3 ~/git/dotfiles/tools/lorite/lorite_intent.py add \
  --activity Task --task "<task-note name>" \
  --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM"
python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py add_record \
  --activity Task --comment "<task-note name>" \
  --start "YYYY-MM-DD HH:MM:SS" --end "YYYY-MM-DD HH:MM:SS"
```

You usually don't know exactly when the user started — **propose your best estimate of start/end and confirm before sending** (show it with `--dry-run` first). This is the right move whenever the session is "create a task / log what we did / mark done" on already-completed work.

- `--comment` is the task-note **basename** (no `.md`, no `[[ ]]`) — the vault renders it as a `[[wikilink]]`, matching `daily_time_tracker.py`.
- For non-task work use a different `--activity` with a free-text `--comment`. Pick an activity that already exists in your SimpleTimeTracker (e.g. `Code`, `Read`, `Write`, `Meeting`, or whatever life/admin activities you track) rather than inventing a new one.
- **Two trackers, on purpose (transition).** `lorite_intent.py` writes to **ActivityWatch** — the destination — and `simple_time_tracker.py` keeps feeding SimpleTimeTracker so no history is lost while the AW path is still young. Run both on every start/stop/add **for the primary task**, and AW alone for the concurrent ones. Drop the STT line once a couple of weeks of AW declarations look right; that is the user's call, not an automatic cutover.
- **Overlap is honest, not double-counted.** Two running declarations mean both statements are true of that time, so both are stored as-is. The observed side is what must not be counted twice, and `intent_resolve.py` (in `~/git/lorite-activitywatch`) handles it: an observed minute is split evenly across the declarations covering it, each slice carrying `shared_with`. So two tasks declared over the same hour show roughly half an hour of resolved activity each, not an hour each.
- **A repeated `start` for the same task is refused**, since that is always a forgotten stop rather than a second stream. `status` shows what is live, `stop --task "<name>"` closes one, `stop --all` closes everything.
- **`stop` refuses to close a declaration another source started** (the phone, the user's own CLI) unless `--force`. With several running, prefer `stop --task "<name>"` over `--all` for exactly this reason: `--all` will trip that guard the moment one of them is not yours.
- **`lorite_intent.py` corrections.** Unlike STT it is editable, so a wrong entry is fixable rather than permanent: `list [--date]` shows event ids, `edit <id> [--task|--activity|--comment|--start|--end]`, `rm <id>`. Use these instead of asking the user to fix it in an app.
- **`lorite_intent.py` talks to the LOCAL aw-server** (`AW_SERVER`, default `http://localhost:5600`) and the declaration rides aw-sync to the home server. If ActivityWatch is not running it exits non-zero with a clear message — say so and carry on, exactly as with a missing STT config.
- `--dry-run` is a **global** flag for both scripts: place it **before** the subcommand (`simple_time_tracker.py --dry-run add_record …`), not after — it prints the envelope (secret redacted) without sending.
- Transport = **LlamaLab Automate Cloud Messaging** (`POST https://llamalab.com/automate/cloud/message`), not a per-flow webhook. Config comes from env (or `<vault>/.secrets/automate.env`): `AUTOMATE_ANDROID_APP_SECRET` (**secret — never print**), `AUTOMATE_ANDROID_APP_TO`, `AUTOMATE_ANDROID_APP_DEVICE`. The Automate flow branches on `payload.action` (`start`/`stop`).
- If config is missing or the endpoint is unreachable the script exits non-zero with a clear message — **don't block the work**, tell the user the timer didn't start and continue.

### 4. Hold the log-often contract (the whole session)
For the rest of the session, log **as you work, not only at the end**, via the **`lorite-ai-chat-diary`** skill: a lightweight dated entry in `ai_chats/diary/daily/AI Chat - <date>` plus the full detail appended in the task/project note under `# AI Generated`. Honor the write policy (`ai_chats/`-only free writes; elsewhere append-only under `# AI Generated`; never rewrite hand-written content; never write secrets). Log at: the session start (after step 2), after each substantive piece of work, and at wrap-up.

**With several tasks anchored, each note gets its own detail.** Write each piece of work into the journal of the task it belongs to, never a merged entry in one note with the others left thin. The daily diary stays a single short entry that wikilinks all of them, and it is the one place that says they ran concurrently (worth a clause, since the split time in the day's totals will otherwise look odd later).

### 5. Route to a specialized agent when one fits (else work inline)
You (base session) can invoke any agent or skill — match the work to it and hand off, keeping the timer + logging in this main thread. Routing is **optional and domain-specific**: a lot of work (general coding, life admin, quick writing, ad-hoc tasks) has no specialized agent, so just do it inline. Spawning an agent is the expensive path — only delegate when the stage genuinely matches.

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
| Author or extend a campaign for an existing experiment | the `lorite-experiment-campaign` skill, inline in this session |
| Write experiment run-code + run trials / record bags | `lorite-experiment-coder` |
| Check data, compute metrics, make figures/tables | `lorite-data-analyst` |
| Write the LaTeX paper | `lorite-paper-writer` *(planned)* |
| Build a Slidev **paper** deck | `lorite-slidev-presentation-*` |
| Build a Slidev **meeting / status** deck (PhD 3-1, status updates) | `lorite-slidev-meeting-deck` |

### 6. Add / switch task, wrap up
- **Add**: anchor another task alongside the running one (step 1 to confirm, step 2 to read, step 3 to declare). Nothing is stopped.
- **Switch**: stop the current task's declaration, then `/lorite <new task>` (step 1). For the STT side, just starting the new activity is treated as switching the running one.
- **Stop / wrap up** — **run this yourself as soon as the work ends; don't wait to be asked** (see the session contract). Concretely, stop a task's declaration when any of these is true: its deliverable is finished, the user says the equivalent of "that's it"/"thanks", the user pivots away from it (stop, then re-anchor), or the session is otherwise ending:

  ```bash
  LORITE_INTENT_SOURCE=claude python3 ~/git/dotfiles/tools/lorite/lorite_intent.py stop \
    --task "<task-note name>"
  python3 ~/git/dotfiles/tools/lorite/simple_time_tracker.py stop
  ```

  With several anchored, stop each by name as its own work ends. `stop --all` is for the end of the session, once you have checked with `status` that everything still running is yours to close (the STT `stop` runs once, with the primary task's block). Then write the closing `lorite-ai-chat-diary` entry summarizing the session. If no live timer was ever running (e.g. retrospective logging), back-fill the block with `add_record` (step 3) instead of `stop`. **Update each anchored task's `status`** to reflect where its own work landed (allowed agent values: todo / investigating / in-progress / blocked / pending-review / cancelled — never `done`): set **`pending-review`** when the session finished the task's deliverable and it now awaits the user's review; leave `in-progress` when work continues next session. **When you set `pending-review`, also fill the task note's `# ✅ Outcome & Learnings` subsections** (`## Outcome` / `## Learnings` / `## Next Steps`) by distilling its `# 📓 Journal / Work Log` — the closing act of finishing a task, per the `lorite-ai-chat-diary` skill (Part 2).

## Notes & gotchas
- **Confirm the task before starting the timer** — a wrong activity pollutes the day's tracking. With several, confirm the whole set in one message.
- **A timer left running is the same pollution.** Starting is gated on the user's confirmation; stopping is not gated on anything — the AI stops it the moment the work ends. If you're unsure whether the session is over, stop it anyway: a re-`start` costs nothing, whereas hours of phantom time on a finished task have to be corrected by hand.
- **Concurrency is for work that is really concurrent.** Anchoring a task that nobody is working is worse than not anchoring it: it takes a share of every observed minute away from the task that earned it. When in doubt, one anchor.
- **`lorite_intent.py` entries stay editable**, which is the safety net for a mis-declared overlap: `list` shows ids, `edit <id> --start/--end/--task` fixes one, `rm <id>` removes it. Fix it there rather than asking the user to.
- **Bases need the Obsidian app running** for the CLI; if it's down, fall back to reading `tasks/*.md` frontmatter directly and say so.
- **This is the live, prospective complement** to the vault's retrospective `scripts/daily_time_tracker.py` (which buckets a day's activity into finished blocks). Both go through the same Automate flow; this skill's `start`/`stop` run the timer live, while `add_record` (and the vault script) back-fill finished blocks. The flow branches on `payload.action`.
- **Degrade gracefully** — missing timer, missing task, or app down should never block the actual work; note the gap and carry on.
