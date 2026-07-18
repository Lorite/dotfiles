---
name: lorite-morning-briefing
description: Write the daily 06:00 morning briefing — fill the LLM time-slot summaries of recent daily notes (yesterday first), audit the last 24 h of the Obsidian vault git repo (commits + unstaged changes) for problems, delegate to lorite-concept-note-writer to turn the day's new unresolved concept [[links]] into concept notes, and write a briefing note (ai_chats/briefings/daily/) that reports issues and ends with the reminder to manually review yesterday's daily note. Runs headless via lorite-morning-briefing.timer; also runnable on demand. Use when asked for the morning briefing or to check the vault's recent commits.
argument-hint: "(no args) · force (rewrite today's briefing)"
---

# lorite-morning-briefing — daily-note summaries + vault git audit + briefing note

Runs headless (`morning_briefing.sh` → `claude -p "/lorite-morning-briefing"`). Everything is **report-only on the git side**: the agent never commits, reverts, stages, or deletes anything in the vault repo — it only reads and reports.

## Runtime env (set by the wrapper — always use these, never hardcode paths)

The wrapper exports four variables; read them at the start of the run (`echo "$VAULT $VAULT_GIT $AUDIT_REF $OBSIDIAN_GUI"`) and use them throughout:

- **`$VAULT`** — the content root (read notes, write summaries/briefing/diary/concept-notes here). On the laptop it's the git working copy; on the home server it's the **Syncthing working copy** (writes sync back automatically — no git push).
- **`$VAULT_GIT`** — the git-history root for the audit. On the laptop `$VAULT_GIT == $VAULT`. On the server it's a **separate read-only clone** (Syncthing excludes `.git/`), which the wrapper has already `git fetch`ed.
- **`$AUDIT_REF`** — the ref to audit: `HEAD` on the laptop, `origin/main` on the server, or empty (skip the commit audit) if no clone is available.
- **`$OBSIDIAN_GUI`** — `1` when a live Obsidian app is drivable via the CLI (laptop: use it for the lint), `0` headless (server: pure file operations, no `obsidian` CLI calls).

Two host profiles: **laptop/GUI** (06:00 timer, app available) and **home server/headless** (03:00 timer, Syncthing, no GUI). The steps below are identical on both — only the env vars differ.

## Idempotency

Today's briefing is `ai_chats/briefings/daily/AI Briefing - <today>.md`. If it already exists, stop immediately (report "already written") — unless invoked with `force`, in which case overwrite it (it's in `ai_chats/`, the free-write zone).

## Procedure

### 1. Vault audit (last 24 h) — commit history + working-copy scan

Two sources, because on the server they diverge (committed history lives in the side clone; live/uncommitted content lives in the Syncthing copy):

**(a) Commit-history audit** — only if `$AUDIT_REF` is non-empty (skip with a note in the briefing if empty):

```bash
git -C "$VAULT_GIT" log "$AUDIT_REF" --since="24 hours ago" --stat
git -C "$VAULT_GIT" log "$AUDIT_REF" --since="24 hours ago" -p -M | head -c 200000   # diffs, capped
# laptop only ($OBSIDIAN_GUI=1 / $VAULT_GIT==$VAULT): also the live working tree
[ "$VAULT_GIT" = "$VAULT" ] && { git -C "$VAULT" status --porcelain; git -C "$VAULT" diff; }
```

**(b) Working-copy scan** — always, against `$VAULT` (catches problems that never hit git, which on a Syncthing node is the *likely* failure mode):

```bash
SINCE="$(date -d '24 hours ago' '+%Y-%m-%dT%H:%M:%S')"   # ISO — portable across GNU find AND bfs ('24 hours ago' fails on bfs)
find "$VAULT" -name "*.sync-conflict-*" -newermt "$SINCE"        # fresh Syncthing conflicts
grep -rl -e '<<<<<<< ' -e '=======' -e '>>>>>>> ' "$VAULT" --include="*.md" 2>/dev/null
find "$VAULT" -name "*.md" -newermt "$SINCE" -not -path "*/.obsidian/*"   # recently-changed notes to eyeball
```

For each commit in the window (use `git -C "$VAULT_GIT" show <sha>` when the stat looks off), each recently-modified note, and any conflict file, check for:

- **Sync artifacts**: `*.sync-conflict-*` files, `conflicted copy` names, duplicated notes. (Pre-existing *old* conflicts under `.obsidian/` — from before this tooling — are benign noise; flag only ones newer than 24 h or inside actual notes.)
- **Merge/conflict markers**: `<<<<<<<`, `=======`, `>>>>>>>` inside notes.
- **Broken notes**: malformed YAML frontmatter, truncated/garbled (mojibake) content, daily notes with leftover `%% run` blocks or template `TODO` placeholders.
- **Accidental mass deletions**: whole notes deleted with no matching rename/move in the same commit.
- **Leaks**: anything under `.secrets/`, API keys/tokens, or other credentials.
- **Misplaced files**: attachments or notes landing in obviously wrong folders (e.g. vault root).
- **Message ≠ diff**: a commit whose message doesn't match what it actually changes.

Plain untracked/modified/recently-edited notes are the user's normal in-progress work — **not** an issue by themselves; flag only the anomalies above. Verdict is either "no issues found" or a concrete per-finding list (file, commit sha if committed, what's wrong).

### 2. Daily-note LLM summaries (yesterday first, 3-day catch-up)

```bash
python3 ~/git/dotfiles/tools/lorite/obsidian_daily_note.py pending --since <today-3d>
```

`pending` only reads files, so it works headless. For each `summary-todo` date in that window (oldest first): write the five time-slot phrases per the **`lorite-daily-note` skill's "LLM summary spec"** (read it — one phrase per slot, only what the note's own Tasks / Calendar / SimpleTimeTracker / App-Usage data shows, wikilinks in Virtual Linker style, no links to excluded-directory targets), editing `$VAULT/diary/daily/<date>.md` directly.

- **Lint (`obsidian_daily_note.py finish <date>`) only when `$OBSIDIAN_GUI=1`** — it drives the Obsidian Linter via the CLI. When `$OBSIDIAN_GUI=0` (server), **skip it**: the summary edit is small and the note was already linted by the laptop's pipeline; note "lint skipped (headless)" in the briefing. On the server, writing the file into `$VAULT` is enough — Syncthing carries it back to the laptop.
- If yesterday is `missing`/`unprocessed`: the daily note's `%% run %%` blocks (tasks/calendar/weather/STT) are filled by the **Obsidian app**, so only `obsidian_daily_note.py process <yesterday>` (GUI, `$OBSIDIAN_GUI=1`) can do it. When `$OBSIDIAN_GUI=0`, **do not** try to process — a summary needs the note's generated sections; report it as "pending processing" and leave it to the laptop's hourly `obsidian-daily-note.timer`. (By 03:00 the server almost always sees an already-processed note via Syncthing.)
- `summary-todo` dates **older than the 3-day window**: list them in the briefing, don't touch them.
- **Media-note pass (GUI only)**: for each date you summarize, when `$OBSIDIAN_GUI=1` also run the `lorite-daily-note` skill's **"Media notes"** procedure — unlinked `— Media — Movie/Series —` titles in the SimpleTimeTracker section get resolved against existing `media/movies|series` notes (alias added when the note exists) or created via the Media DB plugin (`obsidian eval`), then the line gets its wikilink. When `$OBSIDIAN_GUI=0`, skip and note "media pass skipped (headless)". Ambiguous titles are never auto-created — they go in the briefing for the user.

### 3. Write the briefing note — do this BEFORE the concept-note pass

**Order is load-bearing.** The concept-note pass (step 4) can be slow or get killed at the headless `claude -p` background-task ceiling, so the briefing MUST already exist on disk before you start it — otherwise a long concept pass leaves you with *no briefing at all*. Write the briefing note here, with the concept section as a placeholder you'll fill in step 5.

Create `$VAULT/ai_chats/briefings/daily/AI Briefing - <today>.md` directly (no Obsidian needed), frontmatter as in `templates/ai_note.md` (`created`, `source: ai`):

```markdown
# AI Briefing - <today>

## 📝 Daily note summaries
- (per date: summary written / lint skipped (headless) / still pending processing; wikilink each date, e.g. [[<yesterday>]])

## 🎬 Media notes
- (per date: created [[Note]] / linked existing [[Note]] (alias added) / skipped-ambiguous "<line>" / media pass skipped (headless) — omit the section when there were no Media Movie/Series lines)

## 🩺 Vault git check (last 24 h)
- Commits reviewed: <n> (<shas>), working-copy/unstaged files: <n>
- ✅ No issues found — or one bullet per finding: **file** (sha) — what's wrong

## 🧩 Concept notes (new [[links]] → notes)
- _pass running…_  ← placeholder; step 5 replaces this line with the results

## 📚 KOReader highlights
- _import running…_  ← placeholder; step 5 replaces this with the import summary (omit the section if there was no export folder / nothing new)

## ⏳ Older pending
- (older summary-todo dates, and anything else left for a human)

## 👉 Your move
- Review yesterday's daily note [[<yesterday>]] — check the generated summary and remove anything unimportant.
```

Keep it scannable — it's read over coffee, possibly on an e-reader. Only claims backed by this run's command output; anything unverified is labeled as such.

### 4. Fill in concept notes for the day's new links (LAST heavy step — best-effort)

Normal note-taking and the vault's green→`[[wikilink]]` highlight scheme leave **new, unresolved concept links** behind. Turn them into real notes by delegating to the **`lorite-concept-note-writer`** agent in its scan mode. **Run it synchronously (`run_in_background: false`)** — a backgrounded subagent gets terminated at the `claude -p` background-wait ceiling (that's what left an early version with no briefing).

> Invoke `lorite-concept-note-writer` with: *"scan recent changes — create concept notes for the new unresolved concept links in the last 24 h. Git-history root = `<the $VAULT_GIT value>`, ref = `<the $AUDIT_REF value>`; write notes into `<the $VAULT value>`. If the ref is empty, scan notes in `$VAULT` modified in the last 24 h (mtime). **Cap at ~15 notes this run**; list any beyond that as pending so a big backlog can't blow the time budget."*

Pass the concrete `$VAULT`, `$VAULT_GIT`, `$AUDIT_REF` values in the prompt (the subagent doesn't inherit your shell env). The agent extracts new `[[links]]`, drops the ones that already resolve (fast offline note-name/alias index — **not** the slow `obsidian unresolved` scan), **filters to genuine concepts** (skipping dates, media/attachment names, template placeholders, and people/works/places), web-researches each, and writes it under `work/concepts/…` or `personal/concepts/…` in the vault's concept schema (append-only if a note already exists).

**Best-effort and non-blocking:** if the agent errors, is unavailable, or runs out of budget, capture whatever it reports (or note "concept-note pass skipped/incomplete") and carry on — the briefing from step 3 already stands. **Never let this step prevent or delay the briefing.**

### 4b. Import KOReader highlights (best-effort, after the briefing exists)

Invoke the **`lorite-koreader-highlights`** skill to ingest any new KOReader highlight exports (classify by colour, format, append to the matching book / Zotero literature note / inbox, and route vocabulary to the SR decks). Same **best-effort, non-blocking** contract as step 4 — the briefing already stands. On a host where the export folder (`<vault>/Book Exports/koreader/`) isn't synced, its parser reports the dir missing and this is a no-op; note that and move on. Keep the per-book/per-category counts for the step-5 fill.

1. Replace the `_pass running…_` placeholder in the briefing's `## 🧩 Concept notes` section (best-effort Edit) with the results:
   ```markdown
   - Created: <n> — [[Note A]] · [[Note B]] … (or "none new")
   - Skipped: <grouped counts — not a concept / already exists / couldn't ground> · Deferred: <n over the cap> (omit lines that are zero)
   ```
   If the concept pass was skipped/killed, set it to `- (concept-note pass skipped this run)` — don't leave the placeholder.
2. Replace the `_import running…_` placeholder in the `## 📚 KOReader highlights` section with the import summary (`- Imported: <n> highlights across <m> books → [[Note]] · … · <k> vocab cards; <j> to the inbox`), or delete the whole section if there was no export folder / nothing new. If the import was skipped/killed, set it to `- (KOReader import skipped this run)`.
3. Append a one-line entry to the AI-chat diary per the `lorite-ai-chat-diary` skill (`ai_chats/diary/daily/AI Chat - <today>.md`), wikilinking the briefing note (and any concept notes created). Skip the per-task-note detail log for routine runs; log detail only when the audit found real issues.

## Troubleshooting

- Timer/service: `systemctl --user status lorite-morning-briefing.timer`, `journalctl --user -u lorite-morning-briefing -n 50`. Manual run: `systemctl --user start lorite-morning-briefing.service` or `~/git/dotfiles/tools/lorite/morning_briefing.sh`.
- `Persistent=true`: a run missed while the host slept fires on next wake/login; the existing-briefing check makes double-fires harmless.
- **Home-server (headless) run** (`$OBSIDIAN_GUI=0`): the wrapper sets `$VAULT` = Syncthing copy, `$VAULT_GIT` = side clone (`~/git/lorite-obsidian-notes-audit`, fetched at run time), `$AUDIT_REF=origin/main`. Writes into `$VAULT` sync back to the laptop via Syncthing — **no git push**. If the audit reports "commit audit skipped", the side clone is missing/not a git repo — re-clone it (`git clone git@github.com:Lorite/lorite-obsidian-notes.git ~/git/lorite-obsidian-notes-audit`).
- Summaries need the daily note already processed (no `%% run` blocks). That processing is **GUI-only** (Obsidian Run plugin), done by the laptop's hourly `obsidian-daily-note.timer`; by 03:00 the server sees the processed note via Syncthing. If not, the briefing reports "pending processing" and the 3-day window catches it next run.
