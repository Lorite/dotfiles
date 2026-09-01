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

`auto` also runs **`refresh-stt`** (callable standalone: `obsidian_daily_note.py refresh-stt [--lookback N]`, default 10 days; file-only, works without Obsidian): the user back-fills SimpleTimeTracker entries on the phone days late, so it re-renders each recent day's rows from `.android-simpletimetracking/stt_records_automatic.csv` (byte-identical to `scripts/daily/simple_time_tracker.js`) and **inserts only the missing lines** by `(start, end)` time pair into the note's STT section — existing lines and their wikilinks are never touched; late-inserted lines stay plain text (no Virtual Linker pass re-runs). Summaries of topped-up days are **not** auto-rewritten — redo one on request from the enlarged section.

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

**Write a record of the day, not a description of its logs.** This is the one rule the rest serve. The reader, months later, wants to know what they worked on, attended, finished and learned. They do not want a narration of their own telemetry. Audited on [[2026-09-01]]: as the ActivityWatch sections were added, summaries drifted from "I finished the poster, prepped the course, travelled to DTU" (2026-05-06) into "no work was declared before 11:32, the log shows Spotify at 01:29, then Pokémon TCGP at 09:16" (2026-08-27), with the day's real paper work buried between the distractions. More data made the summary worse. These rules exist to stop that.

- **Sources are ranked, and the ranking is not the same as their size in the note.** The ActivityWatch sections (Day Log, Laptop Usage, Phone & Tablet, Where I Was, Category Summary) are by far the *bulkiest* and by far the *weakest* evidence of what the day was about, because they record windows and tabs rather than intent. Never let length decide the narrative.
  1. **Spine, what the day was:** `# 🎯 [[ActivityWatch]] Declared Tasks`, `# ✏️ Tasks` (especially Done Today), `# 📅 [[Google Calendar]] Events`, `# 📝 Notes` (created/touched). These are *stated or completed*, not inferred. Build every slot's phrase from these first.
  2. **Supporting detail, how the time actually went:** `# 📑 [[Android SimpleTimeTracker App]] Logs` and the ActivityWatch sections. Use them to place work in time, to fill a slot the spine leaves genuinely empty (evenings, travel, leisure), and to name a concrete thing worth remembering (a specific talk watched, a place visited). Never as the through-line.
- **Declared Tasks is the strongest single signal of *what* was worked on**, since it is stated rather than inferred, and its rows already carry the `[[task note]]` to link. Its blocks may overlap (several declarations can run at once), so read a slot as "these tasks were live", not as a partition of the hour. Absent for days before 2026-08-12, and empty on days where nothing was declared: fall back to the spine's other sections rather than treating that as "nothing happened".
- **Never open a slot with what is missing from the instrumentation.** "No work was declared before 11:32" describes the tracker, not the person. If the spine is empty for a slot, say what the supporting data does show ("a slow morning, mostly reading and music"), or say plainly that nothing was logged. Never imply idleness from a gap: undeclared work is still work, and offline work leaves no trace at all.
- **Ban the telemetry register.** Do not write "the log shows", "the data indicates", "declared work began", "a video-call window". Write the day in the **first person, past tense**, the way 2026-05-06 does: "I finished…", "I attended…", "I worked on…". Name the thing, not the sensor that saw it.
- **Leisure and distraction get proportionate space, which is small.** One clause at most per slot, and only when it genuinely characterises that stretch of the day. Do not enumerate every game, feed or clip, and never interleave them through a description of real work ("heavily interleaved with Pokémon TCGP, Reddit, and YouTube") - that editorialises rather than records. A long evening genuinely spent on leisure is simply reported as such, without apology or tally.
- Only state what the data shows, never invent. If a slot has no data, say so plainly (e.g. "nothing was logged.").
- Use `[[wikilinks]]` to the tasks / meeting notes / places involved (copy link targets from the sections above; Virtual Linker has already converted the body, so match its style).
- The note must contain no `%% run start` text before summarizing (`process` guarantees this).
- All-day calendar events render with a bogus current-time stamp (`HH:mm–HH:mm` identical, e.g. "02:17–02:17 — Whit Monday.") — treat them as all-day facts, not timed events.

## Media notes (movies & series in the SimpleTimeTracker logs)

After `process`, the `# 📑 [[Android SimpleTimeTracker App]] Logs` section may contain `— Media — Movie — <title>…` / `— Media — Series — <title>…` lines whose title stayed **plain text** — Virtual Linker only links existing note names/aliases, so a first-time watch has nothing to link to. YOU (the agent) close that gap per date, right after `process` / alongside the summary. **GUI-only** (drives the live app via `obsidian eval` + needs network for OMDb): skip headless and report "media pass skipped".

1. **Detect** — in the STT section only, lines matching `— Media — (Movie|Series) — ` where the *title segment* (text after that subtype dash, up to the next ` — `, ` at `, or trailing `.`) contains no `[[`. Only Movie/Series — never Social Media / Music / Videogame / YouTube lines.
2. **Clean the title** — strip venue suffixes ("… at Imperial cinema"), episode markers ("— S1:E6 - …", "S05 E20"), and fix obvious typos ("Tom Raider" → "Tomb Raider") to form the search query. Keep a `(year)` if the log has one.
3. **Resolve against the vault FIRST** (duplicate guard) — fuzzy-match the cleaned title against `ls media/movies media/series` basenames **and** their `aliases:` frontmatter (case/punctuation-insensitive, ignore the ` (year)` suffix). A match means the note exists but wasn't linkable (e.g. "Westworld" vs `Westworld (2016–2022).md` with no alias): **add the bare mention as an alias** to that note's frontmatter (so future Virtual Linker runs link it natively) and go to step 5 — do NOT create.
4. **Create via the Media DB plugin** (the user's sanctioned creation path — full frontmatter, template, cover image, aliases):

   ```bash
   # search (movies+series both come from OMDbAPI); filter by type, eyeball the candidates
   obsidian eval code="(async () => { const p = app.plugins.plugins['obsidian-media-db-plugin']; const r = await p.apiManager.query('<query>', ['OMDbAPI']); return JSON.stringify(r.filter(m => m.type === '<movie|series>').slice(0, 5).map(m => ({ title: m.title, year: m.year, id: m.id }))); })()"
   # create from the confident hit's id
   obsidian eval code="(async () => { const p = app.plugins.plugins['obsidian-media-db-plugin']; const d = await p.apiManager.queryDetailedInfoById('<id>', 'OMDbAPI'); await p.createMediaDbNoteFromModel(d, { attachTemplate: true, openNote: false }); return d.title + ' (' + d.year + ')'; })()"
   ```

   **Confidence rule**: create only when one candidate's title matches the cleaned title (case/punctuation-insensitive) *and* the year matches if the log gives one; sequels/specials with near-identical titles ("The Devil Wears Prada" vs "… 2") make title-only matching unsafe — when ambiguous, create nothing and report the line for the user to handle. The created basename follows the plugin's file-name template `{{ title }} ({{ year }})` — verify with `ls` after creating. Gotchas: apostrophes in titles terminate the JS string (escape them); `openNote` is overridden by the plugin's `openNoteInNewTab` setting, so tabs may open in the app — harmless.
5. **Link the line** — replace the plain title text in the daily note with `[[<note basename>|<original text>]]` (display text unchanged), STT section only. Then `finish <date>` to lint.
6. **Report** per date: created / linked-existing (alias added) / skipped-ambiguous — in the briefing's media line or to the user.

## Troubleshooting

- The macro writes `.process_daily_note_done` (vault root): `<path>\t<ok|error: …>\t<debug json>`. `error: Obsidian window is not rendering` → make the Obsidian window visible and rerun. Debug fields: `rafBefore/rafAfter` (window painting), `sourceMode`, `editorShown`, `wasTyping` (Virtual Linker's stuck-isTyping guard), `retoggled`, per-chunk `seen=/converted=` counts.
- `seen=0` on every chunk → Virtual Linker isn't decorating: check the window is visible, the plugin is enabled, and rerun (the macro already clears `isTyping`, retoggles the linker, and forces live preview).
- After editing `scripts/process_daily_note.js`: nothing to reload (QuickAdd re-reads user scripts). After editing the QuickAdd choice itself: `obsidian plugin:reload id=quickadd`.
- The Run plugin's all-day-event time quirk and the `## [[AI Chat - moment(...)]]` heading come from the user's own template/scripts — reproduce, don't fix, unless asked.
- The macro must never link to notes under Virtual Linker's **Excluded directories** setting (e.g. `_types/task.md` → `[[task|Task]]`): the plugin decorates them anyway, so `process_daily_note.js` filters those targets itself (reads `excludedDirectories` live from the plugin settings). In summaries, don't hand-write links to those targets either.
- **Recurring calendar events / wrong-date meeting links.** Each occurrence of a recurring event gets its own dated `type: calendar_event` note (`calendar_events/<date> <title>.md`), and every occurrence aliases the generic series title (e.g. "Master Thesis supervision - regular event"). Virtual Linker matches that title on *any* day's calendar line, so a note's calendar section would link the meeting to an arbitrary occurrence's date (a 2026-07-13 line → the 2026-06-29 note). `process_daily_note.js` guards this in `buildWikilink` (`calendarEventMismatch`): a `calendar_event` target is only linked when its date (`date_start`, else the `YYYY-MM-DD` title prefix) equals the daily note's date; otherwise the line stays plain text. **When you write the summary, copy link targets from the calendar section as usual — but never link a meeting to a `calendar_events/` note whose date ≠ the note's date** (leave it plain), since the calendar section no longer carries those bad links to copy.
