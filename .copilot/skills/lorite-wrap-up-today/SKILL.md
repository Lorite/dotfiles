---
name: lorite-wrap-up-today
description: The evening wrap-up ritual — closes out today and prepares tomorrow. Reads what you actually worked on today (AI-chat diary, git, recently-touched task notes, timer), tomorrow's Google Calendar, your open tasks + deadlines (mtn), and the curated Consumption Queue note, then writes a dated wrap-up note (ai_chats/wrapups/daily/) that recommends which tasks to work tomorrow and a few media items to consume (work AND personal — podcasts, videos, articles, research, books, videogames…), each matched to tomorrow's calendar shape and to your recent activity. Forward-looking counterpart to lorite-morning-briefing (which stays on its own early schedule and simply reads this note — the wrap-up never runs the briefing). Use when wrapping up the day / planning tomorrow, or via /lorite stop.
argument-hint: "(no args = wrap up today, plan tomorrow) · force (overwrite today's wrap-up) · <yyyy-MM-dd> (wrap up a specific day)"
---

# lorite-wrap-up-today — close today, plan tomorrow

The **evening** half of the daily loop: forward-looking, run when the user is winding down. It turns "what happened today + what's fixed for tomorrow" into a concrete, decision-ready plan — **which tasks to work tomorrow** and **what to consume** (research, articles, videos, podcasts, books, videogames, boardgames, series… work *and* personal), each slotted against tomorrow's real calendar shape and biased toward the themes the user is actively working on.

It is the counterpart to **[[lorite-morning-briefing]]**, not a replacement: the briefing runs early on its own schedule (it needs the *completed* daily note, the last-24h git audit, and overnight highlight/app-usage data that don't exist yet at night). **This skill never runs the briefing.** Instead it *feeds* it — the briefing reads today's wrap-up note for the plan the user already set.

Vault: `~/git/lorite-obsidian-notes` (use `$VAULT` when set). Dates `yyyy-MM-dd`; get the date/time from the `time` tool or `date`. `mtn` = `mdbase-tasknotes`; `G` (gcalcli) = `~/.local/share/dotfiles-agents/venv/bin/gcalcli` (read-only — context/free-slots only; expired auth → continue without calendar, don't block).

## Output note / idempotency

- **Path:** `ai_chats/wrapups/daily/Wrap-up - <today>.md` (AI-writable zone; `mkdir -p` first). Sibling to `ai_chats/briefings/daily/`.
- If today's wrap-up already exists, stop and report "already written" unless invoked with `force` (then overwrite — it's in the free-write zone).
- Never write secrets.

## Procedure

### 1. Reconstruct "today" (what was actually worked on)

`simple_time_tracker.py` is write-only and the human daily note (`diary/daily/<today>.md`) is built retroactively, so it usually **doesn't exist yet** at wrap-up. `lorite_intent.py` is the readable half (it queries the local aw-server), so today's declarations are available even when nothing else is — reconstruct today's work from what's live:

```bash
D=$(date +%Y-%m-%d)
# today's AI-chat diary = the richest "what we did" signal
cat "$VAULT/ai_chats/diary/daily/AI Chat - $D.md" 2>/dev/null
# what was DECLARED today: the measured half, straight from ActivityWatch
python3 ~/git/dotfiles/tools/lorite/lorite_intent.py list --date "$D"
python3 ~/git/dotfiles/tools/lorite/lorite_intent.py status
# task notes touched today (the work surface)
find "$VAULT/tasks" -name '*.md' -newermt "$D 00:00" -not -path '*/archived/*'
# vault commits today (may be sparse — vault auto-backs-up periodically)
git -C "$VAULT" log --since="$D 00:00" --stat
git -C "$VAULT" status --porcelain
```

Extract: which task notes advanced, key decisions/outcomes logged today, and the active themes (their `projects`/tags). This is the **recency signal** for both task and media suggestions.

**`lorite_intent.py list` is the time signal now** — it reads the `aw-intent` bucket directly, so it works at wrap-up (unlike the daily note, which is built retroactively) and it names the task note per block. Read it as: which tasks got real time today, and how much. Two caveats. Blocks may **overlap**, because several declarations can run at once, so the column sums to more than the day on purpose. And **`status` matters at wrap-up**: anything still running is a timer nobody stopped, so close it (`stop --task "<name>"`) before writing the wrap-up rather than leaving it to accrue overnight — but never `--force` another source's block, that is someone else's session still working.

SimpleTimeTracker's `.android-simpletimetracking/` export and an already-built daily note are still worth folding in when present, and are the only source for time declared **before** 2026-08-12. If neither exists and nothing was declared, infer effort from the diary.

### 2. Tomorrow's calendar (fixed commitments + free-slot shape)

```bash
TOM=$(date -d tomorrow +%Y-%m-%d)
$G agenda "$TOM" "$(date -d '+2 days' +%Y-%m-%d)"   # tomorrow's events
```

Derive the **shape of tomorrow**: fixed meetings (with times), the free blocks between them, a long commute or travel (→ audio/portable media), any evening free (→ longer personal media / games), deep-work windows (→ research/coding tasks). If gcalcli is unauthorized, note "calendar unavailable" and plan from tasks alone.

### 3. Open tasks + deadlines

```bash
mtn -p "$VAULT" ls --overdue --json
mtn -p "$VAULT" ls --status in-progress --json
mtn -p "$VAULT" ls --due "$(date -d '+7 days' +%Y-%m-%d)" --json   # horizon
```

Cross-reference with step 1's active themes. **Recommend 2–4 tasks for tomorrow**, favouring: overdue/due-soon, already in-progress (continuity with today), and ones that fit tomorrow's free blocks. Map each suggested task to a concrete slot ("Spot MPC task → the 10:00–12:00 gap before the 1-1"). Surface the **deadline horizon** separately so nothing sneaks up.

### 4. Read the Consumption Queue (don't rebuild it)

Read `ai_chats/queues/Consumption Queue.md` (the [[lorite-consumption-queue]] note). **Select** a handful — do not re-scan the vault (that's the queue skill's job, run weekly). Pick media that fits **tomorrow's shape** and **today's themes**:

- **Prefer a `▶ Continue` (in-progress) item over starting a new one** for long-form types — suggest finishing the series/book/game already on the go before proposing a fresh one;
- long commute / travel → a queued **podcast** or audiobook;
- a deep-work block → the queued **paper / research** tied to a live task;
- an evening free → a **videogame / series / book** (personal);
- short gaps / waiting → a quick **article** or a `Things TODO when little time` item.

If the queue is missing or stale (`updated` far in the past, or thin), still make suggestions from `temporary/` + `media/articles_unread/` for tonight, and **recommend running `lorite-consumption-queue`** to refresh — don't silently do the full scan here. Always include **both work and personal** picks, and a small **personal / life-admin** nudge (errand, message to send, boardgame with friends, place to visit) drawn from the plan notes (`media/plans/Things TODO *`).

### 5. Write the wrap-up note

```markdown
---
title: Wrap-up - <today>
date: <today>
tags:
  - wrapup
  - ai_generated
---

> [!note] Evening wrap-up for <today> → plan for <tomorrow, weekday>. Read by the next [[lorite-morning-briefing]]. Sources: today's diary, calendar, `mtn`, [[Consumption Queue]].

## ✅ Today in review
- <what advanced — task notes, outcomes/decisions logged, rough effort>
- <wins / anything left mid-flight to pick up tomorrow>

## 📅 Tomorrow's calendar (<tomorrow, weekday>)
- HH:MM–HH:MM <event> — <note>
- Free blocks: <e.g. 10:00–12:00 deep work · evening open>

## 🎯 Suggested tasks for tomorrow
1. [[<task note>]] — <why now (overdue / in-progress / due) → which slot> 
2. …
(2–4, matched to the free blocks above and today's momentum)

## ⏳ Deadline horizon (next 7 days)
- <yyyy-MM-dd> — [[<task>]] (<status>)

## 🍿 Media to consume
- 🎧 [[<podcast>]] — for the commute (personal)
- 📄 [[<paper>]] — ties to [[<active task>]], read in the deep-work block (work)
- 🎮 [[<game/series/book>]] — evening wind-down (personal)
(a small curated set from [[Consumption Queue]], slotted to tomorrow's shape; work + personal)

## 🌱 Personal / life
- <errand, message to send, friend/boardgame plan, place/food, health> — from `Things TODO *`

## → Handoff
Plan set for <tomorrow>. The morning briefing will read this note.
```

Include only sections with content. Keep it scannable — this is a *decision-ready* plan, not an essay.

### 6. Light upkeep + log (no heavy scans)

- **Queue upkeep (light only):** if the user mentions having consumed something today, tick/remove it from the Consumption Queue; if a strong new candidate surfaced today, add it. Do **not** do the full re-curation — that's `lorite-consumption-queue`'s job.
- **Timer / diary:** if this wrap-up is the end of a live `/lorite` session, stop the timers (see [[lorite]] step 6) — every declaration you started, by name, plus the one SimpleTimeTracker activity. Log the wrap-up via **[[lorite-ai-chat-diary]]** — a dated diary entry linking `[[Wrap-up - <today>]]` and the tasks referenced.
- Report the plan back to the user in a few lines (top task picks + top media picks), and note if the queue needs a weekly refresh.

## Boundaries (why this stays separate from the briefing)

- **Do not generate tomorrow's morning briefing here.** Its inputs (completed daily note, 24h git audit, KOReader highlights, app-usage) accrue overnight and are absent now — running it early yields a stale, half-empty briefing. The clean handoff is one-directional: wrap-up writes the plan → briefing reads it.
- **Do not rebuild the Consumption Queue here** (expensive weekly scan). Select from it; recommend a refresh when thin.
- Calendar/task reads are **read-only**; never create/modify calendar events or GitHub issues from this skill (that's [[lorite-task-manager]] on explicit request).
