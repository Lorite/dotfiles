---
name: lorite-morning-briefing
description: Write the daily 06:00 morning briefing — fill the LLM time-slot summaries of recent daily notes (yesterday first), audit the last 24 h of the Obsidian vault git repo (commits + unstaged changes) for problems, delegate to lorite-concept-note-writer to turn the day's new unresolved concept [[links]] into concept notes, and write a briefing note (ai_chats/briefings/daily/) that reports issues and ends with the reminder to manually review yesterday's daily note. Runs headless via lorite-morning-briefing.timer; also runnable on demand. Use when asked for the morning briefing or to check the vault's recent commits.
argument-hint: "(no args) · force (rewrite today's briefing)"
---

# lorite-morning-briefing — daily-note summaries + vault git audit + briefing note

Runs every morning at 06:00 (systemd user timer `lorite-morning-briefing.timer` → `morning_briefing.sh` → `claude -p "/lorite-morning-briefing"`). Everything is **report-only on the git side**: the agent never commits, reverts, stages, or deletes anything in the vault repo — it only reads and reports. Vault: `~/git/lorite-obsidian-notes`.

## Idempotency

Today's briefing is `ai_chats/briefings/daily/AI Briefing - <today>.md`. If it already exists, stop immediately (report "already written") — unless invoked with `force`, in which case overwrite it (it's in `ai_chats/`, the free-write zone).

## Procedure

### 1. Vault git audit (last 24 h)

Review, in `~/git/lorite-obsidian-notes`:

```bash
git log --since="24 hours ago" --stat
git status --porcelain
git diff --stat && git diff
```

For each commit in the window (use `git show <sha>` when the stat looks off) and for the unstaged/untracked changes, check for:

- **Sync artifacts**: `*.sync-conflict-*` files (Syncthing), `conflicted copy` names, duplicated notes.
- **Merge/conflict markers**: `<<<<<<<`, `=======`, `>>>>>>>` inside notes.
- **Broken notes**: malformed YAML frontmatter, truncated/garbled (mojibake) content, daily notes committed with leftover `%% run` blocks or template `TODO` placeholders.
- **Accidental mass deletions**: whole notes deleted with no matching rename/move in the same commit.
- **Leaks**: anything under `.secrets/`, API keys/tokens, or other credentials in tracked content.
- **Misplaced files**: attachments or notes landing in obviously wrong folders (e.g. vault root).
- **Message ≠ diff**: a commit whose message doesn't match what it actually changes.

Plain untracked/modified notes are the user's normal in-progress work — **not** an issue by themselves; flag only the anomalies above. Verdict is either "no issues found" or a concrete per-finding list (file, commit sha if committed, what's wrong).

### 2. Daily-note LLM summaries (yesterday first, 3-day catch-up)

```bash
python3 ~/git/dotfiles/tools/lorite/obsidian_daily_note.py pending --since <today-3d>
```

- For each `summary-todo` date in that window (oldest first): write the five time-slot phrases per the **`lorite-daily-note` skill's "LLM summary spec"** (read it — one phrase per slot, only what the note's own Tasks / Calendar / SimpleTimeTracker / App-Usage data shows, wikilinks in Virtual Linker style, no links to excluded-directory targets), editing `diary/daily/<date>.md` directly, then run `obsidian_daily_note.py finish <date>`. If Obsidian isn't running, `finish` fails — still write the summary, skip the lint, and note it in the briefing.
- If yesterday is `missing`/`unprocessed`: run `obsidian_daily_note.py process <yesterday>` first **only if Obsidian is running** (`obsidian vault` exits 0); otherwise leave it to the hourly `obsidian-daily-note.timer` and report it as pending in the briefing.
- `summary-todo` dates **older than the 3-day window**: list them in the briefing, don't touch them.

### 3. Fill in concept notes for the day's new links (delegate — best-effort)

Normal note-taking and the vault's green→`[[wikilink]]` highlight scheme leave **new, unresolved concept links** behind. Turn them into real notes by delegating to the **`lorite-concept-note-writer`** agent in its scan mode:

> Invoke `lorite-concept-note-writer` with: *"scan recent changes — create concept notes for the new unresolved concept links in the last 24 h of vault commits + unstaged/untracked changes."*

The agent does its own work: extracts new `[[links]]` from `git log --since="24 hours ago"` / `git diff` / untracked files, drops the ones that already resolve (fast offline note-name/alias index — **not** the slow `obsidian unresolved` scan), **filters to genuine concepts** (skipping dates, media/attachment names, template placeholders, and people/works/places), web-researches each, and writes it under `work/concepts/…` or `personal/concepts/…` in the vault's concept schema (append-only if a note already exists). No per-day cap — the 24 h window bounds it.

**Best-effort and non-blocking:** if the agent errors, spawning is unavailable, or the Obsidian app is down, capture whatever it reports (or note "concept-note pass skipped") and carry on — **never fail the briefing over concept notes**. Collect its created/skipped summary for the briefing note.

### 4. Write the briefing note

Create `ai_chats/briefings/daily/AI Briefing - <today>.md` directly (no Obsidian needed), frontmatter as in `templates/ai_note.md` (`created`, `source: ai`), then:

```markdown
# AI Briefing - <today>

## 📝 Daily note summaries
- (per date: summary written / lint skipped (Obsidian closed) / still pending processing; wikilink each date, e.g. [[<yesterday>]])

## 🩺 Vault git check (last 24 h)
- Commits reviewed: <n> (<shas>), unstaged files: <n>
- ✅ No issues found — or one bullet per finding: **file** (sha) — what's wrong

## 🧩 Concept notes (new [[links]] → notes)
- Created: <n> — [[Note A]] · [[Note B]] … (or "none new")
- Skipped: <grouped counts — not a concept (people/works/dates) / already exists / couldn't ground> (or omit if none)

## ⏳ Older pending
- (older summary-todo dates, and anything else left for a human)

## 👉 Your move
- Review yesterday's daily note [[<yesterday>]] — check the generated summary and remove anything unimportant.
```

Keep it scannable — it's read over coffee, possibly on an e-reader. Only claims backed by this run's command output; anything unverified is labeled as such.

### 5. Log

Append a one-line entry to the AI-chat diary per the `lorite-ai-chat-diary` skill (`ai_chats/diary/daily/AI Chat - <today>.md`), wikilinking the briefing note (and any concept notes created in step 3). Skip the per-task-note detail log for routine runs; log detail only when the audit found real issues.

## Troubleshooting

- Timer/service: `systemctl --user status lorite-morning-briefing.timer`, `journalctl --user -u lorite-morning-briefing -n 50`. Manual run: `systemctl --user start lorite-morning-briefing.service` or `~/git/dotfiles/tools/lorite/morning_briefing.sh`.
- The 06:00 run uses `Persistent=true`: a morning missed while the laptop slept fires on the next wake/login; the existing-briefing check makes double-fires harmless.
- Summaries need the daily note already processed (no `%% run` blocks) — the hourly `obsidian-daily-note.timer` normally guarantees that by 06:00 if Obsidian was open at some point; otherwise the briefing says so and the next morning catches up (3-day window).
