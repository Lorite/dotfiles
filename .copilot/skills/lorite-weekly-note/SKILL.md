---
name: lorite-weekly-note
description: Generate the Obsidian weekly note (diary/weekly/gggg-Www) for the last completed ISO week. Creates it from the weekly template with all Templater expressions expanded by file ops, fills the tasks and notes data sections by computing directly from vault frontmatter (headless-safe, no Run plugin), drafts the reflective "Weekly Questions" answers as clearly marked strike-or-keep AI proposals, appends an AI Generated week roll-up distilled from the 7 daily notes plus the AI diaries and briefings, and audits the week for missing or empty daily notes. Use when asked to create, backfill, or summarize a weekly note, or when run by the Monday 03:00 lorite-weekly-note.timer.
argument-hint: "2026-W32 · (no arg = last completed week)"
---

# lorite-weekly-note — generate + summarize the Obsidian weekly note

Turns the dead manual weekly-review habit into an automated one: the AI does all the assembly (data sections, roll-up, drafted reflections), the user spends ~5 minutes editing the reflection drafts. Approved by the user on [[2026-08-10]] in [[Improve my Obsidian workflow to use AI LLM agents]], including the write grant below.

Vault: `$VAULT` (default `~/git/lorite-obsidian-notes`). Runs headless (server, Monday 03:00 via `lorite-weekly-note.timer` → `weekly_note.sh`) or on demand on the laptop. The wrapper exports `VAULT` and `OBSIDIAN_GUI` exactly like `morning_briefing.sh`.

## Write policy (explicit user grant, 2026-08-10)

- `diary/weekly/` is AI-creatable **for notes this skill generates from the template**. The whole note body is AI-written on creation (that is the point), with the reflective drafts clearly marked as AI proposals.
- Never overwrite an existing weekly note that has hand-written edits. If the target note already exists, stop and report (backfill/redo only when the user explicitly asks).
- Everything else follows `lorite-obsidian-note` / `lorite-ai-chat-diary` as usual.

## Procedure

### 1. Resolve the target week

Argument `gggg-Www` if given, else the ISO week of **yesterday** (`date -d yesterday +%G-W%V`), so the Monday-03:00 run targets the week that just ended. If `diary/weekly/<week>.md` exists → report "already written" and stop (the wrapper also guards this).

Compute once and reuse: week start (Monday) and end (Sunday) dates, previous/next week ids, month id `YYYY-MM` of the week's Monday, semester id `YYYY-S1` (Jan to Jun) or `YYYY-S2` (Jul to Dec), year.

### 2. Create the note from the template, expanded by file ops

Source template: `templates/diary/weekly.md`. Expand every Templater `<% %>` expression yourself (dates, nav links, day links) and **omit the `%% run %%` blocks entirely**, writing the computed static content in their place (step 3). Do not use Templater or the Run plugin: this must work headless. Keep the template's own heading and separator format exactly as authored (including its date-range heading), and keep frontmatter `tags: [diary, weekly]` with real `created`/`updated` timestamps.

### 3. Fill the data sections from frontmatter (replicating the template's dataview logic)

All computable with `grep`/`awk`/python over frontmatter. Emit the same static shape the Run plugin would have left: `- [[<task name>]]`, prefixed `(Done) ` or `(Cancelled) ` per the template's rules.

- **Tasks created this week**: `tasks/**/*.md` with `date_created` in the week. **Recursive is mandatory**: completed tasks live in `tasks/archived/`, and a non-recursive scan silently empties the Done list (found and fixed during the first live run, 2026-08-10).
- **Due for this week**: `date_due` in the week, or a `complete_instances` entry in the week.
- **Done this week**: `date_completed` in the week, or a `complete_instances` entry in the week.
- **Planned for next week**: `date_due` or `scheduled` in the next ISO week.
- **Notes created this week** / **Notes last touched this week**: all vault `*.md` (excluding `templates/`) with frontmatter `created` / `updated` in the week. These lists can be long: cap each at 100 lines and end with an italic count line when truncated, never truncate silently.

### 4. Draft the Weekly Questions (strike-or-keep AI proposals)

Directly under the `# ⁉️ Weekly Questions` heading add one italic notice line:

`_(AI drafts from the week's notes. Edit, strike, or keep. Source: [[AI Chat - <run date>]])_`

Then replace each `- TODO` with 1 to 3 drafted bullets grounded ONLY in the week's data: the 7 daily notes (`diary/daily/`), their Daily Questions summaries, the AI chat diaries (`ai_chats/diary/daily/`), briefings, wrap-ups, and the tasks lists from step 3. Never invent. A question the data cannot answer gets `- (no data this week)`. The "Focus for this Week" checkbox in the "🌞 This week" block refers to the week being reviewed: fill it from what the week's record shows the focus actually was.

### 5. Append the AI Generated week roll-up

At the end of the note:

```
# AI Generated

## Week in review ([[AI Chat - <run date>]])

<outcome-first narrative of the week, grouped per project or area, with the key decisions and their why, numbers, and wikilinks to the task notes involved. Distilled from the AI diaries + daily summaries + briefings, written for a reader who did not watch the week.>

## Data health

<missing or empty (0-byte or unprocessed) daily notes of the week, listed for backfill via lorite-daily-note. "All 7 daily notes present and processed." when clean.>
```

### 6. Log

One short `lorite-ai-chat-diary` entry linking the weekly note. The weekly note itself is the detail: do not duplicate the roll-up into the diary.

## Notes & gotchas

- **Monthly second, on demand for now.** A monthly sibling (distilling the weeklies) is planned only after the weekly proves itself. Semester (`diary/semester/`, template `templates/diary/semester.md`) and yearly reviews are on-demand only, never scheduled.
- The template's nav links point at `diary/monthly/` and `diary/semester/` notes that may not exist yet. Leave the links unresolved: that is the template's design.
- `date -d` week arithmetic: `%G-W%V` is ISO (year boundary safe). Week start: `date -d "<yesterday> -$(( $(date -d <yesterday> +%u) - 1 )) days"`.
- Degrade gracefully: a section whose data source is unreadable gets an italic one-line excuse, never a silent omission, and never blocks the rest of the note.
