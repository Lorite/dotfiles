---
name: lorite-daily-note
description: Generate or backfill Obsidian daily notes end-to-end — create from the Templater template, execute the Run-plugin script blocks (tasks, calendar, weather, notes, SimpleTimeTracker, app usage; all retroactive), strip the script code, convert Virtual Linker links, lint, and then write the LLM summary of the "Daily Questions" section from the note's own data. Use when asked to create, process, backfill, or summarize daily notes (diary/daily/YYYY-MM-DD).
argument-hint: "2026-05-26 · backfill · backfill --since 2026-04-26"
---

# lorite-daily-note — generate + summarize Obsidian daily notes

Automates the manual daily-note flow (create from template → Run command → strip scripts with `%% run start[\s\S]*?%%\n([\s\S]*?)\n%% run end %%` → `$1` → Virtual Linker convert-all → save/lint) and adds the LLM summary the task note `tasks/Generate an automatic LLM summary of the daily note in Obsidian` asks for.

**Two halves, two actors:**

1. **Mechanical pipeline** — `~/git/dotfiles/tools/lorite/obsidian_daily_note.py` drives the live Obsidian app through the `obsidian` CLI + the QuickAdd macro "Process Daily Note (run, strip, links, lint)" (`scripts/process_daily_note.js` in the vault, QuickAdd command id `quickadd:choice:a8895b3d-1db5-4476-8c7d-9c5a0eca8a6c`).
2. **LLM summary** — YOU (the agent) write it; there is no API call. After `process` succeeds, fill the summary from the note's own generated data, then run `finish`.

## Preconditions

- Obsidian **desktop app running** with the vault (`~/git/lorite-obsidian-notes`) open — the CLI and macro drive the live app. Notes are processed in the foreground: tabs open/switch, and the macro may **bring the Obsidian window to front** (rendering is required for Virtual Linker decorations; a hidden/minimized window stalls them). Warn the user before a long batch.
- Never run two `process` invocations in parallel — one editor, one sentinel file.

## Per-date procedure

```bash
python3 ~/git/dotfiles/tools/lorite/obsidian_daily_note.py process <YYYY-MM-DD>
```

Creates the note if missing (Templater file-template expands it), fills the `%% run %%` blocks, strips the script code, converts virtual links, lints, saves. Idempotent; safe on notes that are already half-processed. It never touches hand-written content outside the `%% run %%` blocks.

Then write the summary (see spec below) by editing `~/git/lorite-obsidian-notes/diary/daily/<date>.md` directly, and lint the result:

```bash
python3 ~/git/dotfiles/tools/lorite/obsidian_daily_note.py finish <YYYY-MM-DD>
```

## Automatic daily run (yesterday's note)

The **`obsidian-daily-note.timer`** systemd user timer (canonical units in `~/git/dotfiles/tools/lorite/`, installed + enabled by `install.sh`) runs `obsidian_daily_note.py auto` hourly: it creates + processes every missing/unprocessed note from **yesterday** back 7 days (never today — its data is still accumulating), and no-ops quietly when Obsidian isn't running or nothing is pending. It does **not** write LLM summaries — when invoked for summaries, first `pending` to find `summary-todo` dates, then do the summary + `finish` loop. Control: `systemctl --user {status,start} obsidian-daily-note.{timer,service}`; logs via `journalctl --user -u obsidian-daily-note`.

## Backfill (many dates)

```bash
python3 ~/git/dotfiles/tools/lorite/obsidian_daily_note.py pending [--since YYYY-MM-DD]
```

lists `missing` / `unprocessed` / `summary-todo` dates up to today. Work **sequentially, chronologically**. Expect ~1–2 min per note. Log progress via `lorite-ai-chat-diary` at start, every ~10 notes, and at the end — the batch is resumable from `pending` at any time.

## LLM summary spec (from the task note)

Target: the `# ⁉️ Daily Questions` → `### 📌 Summary` section — replace the five `TODO` bullets, keeping the exact template shape, **one phrase per time slot**:

```
- In the morning, …
- Around noon, …
- In the afternoon, …
- In the evening, …
- Before night, …
```

- Source the phrases **mainly from** `# ✏️ Tasks`, `# 📅 [[Google Calendar]] Events`, and `# 📑 [[Android SimpleTimeTracker App]] Logs` (App-Usage time logs help for evenings).
- Only state what the data shows — never invent. If a slot has no data, say so plainly (e.g. "nothing was logged.").
- Use `[[wikilinks]]` to the tasks / meeting notes / places involved (copy link targets from the sections above; Virtual Linker has already converted the body, so match its style).
- The note must contain no `%% run start` text before summarizing (`process` guarantees this).
- All-day calendar events render with a bogus current-time stamp (`HH:mm–HH:mm` identical, e.g. "02:17–02:17 — Whit Monday.") — treat them as all-day facts, not timed events.

## Troubleshooting

- The macro writes `.process_daily_note_done` (vault root): `<path>\t<ok|error: …>\t<debug json>`. `error: Obsidian window is not rendering` → make the Obsidian window visible and rerun. Debug fields: `rafBefore/rafAfter` (window painting), `sourceMode`, `editorShown`, `wasTyping` (Virtual Linker's stuck-isTyping guard), `retoggled`, per-chunk `seen=/converted=` counts.
- `seen=0` on every chunk → Virtual Linker isn't decorating: check the window is visible, the plugin is enabled, and rerun (the macro already clears `isTyping`, retoggles the linker, and forces live preview).
- After editing `scripts/process_daily_note.js`: nothing to reload (QuickAdd re-reads user scripts). After editing the QuickAdd choice itself: `obsidian plugin:reload id=quickadd`.
- The Run plugin's all-day-event time quirk and the `## [[AI Chat - moment(...)]]` heading come from the user's own template/scripts — reproduce, don't fix, unless asked.
- The macro must never link to notes under Virtual Linker's **Excluded directories** setting (e.g. `_types/task.md` → `[[task|Task]]`): the plugin decorates them anyway, so `process_daily_note.js` filters those targets itself (reads `excludedDirectories` live from the plugin settings). In summaries, don't hand-write links to those targets either.
