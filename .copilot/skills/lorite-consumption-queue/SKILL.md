---
name: lorite-consumption-queue
description: Maintain the single always-ready "Consumption Queue" note (ai_chats/queues/Consumption Queue.md) — one curated shortlist per media type (podcasts, videos, articles, research, books, videogames, boardgames, series, movies, courses…), spanning work AND personal, drawn from the vault's unread buckets (media/articles_unread/, temporary/), the per-type media/ folders, the hand-made TODO/plan notes, already-read notes worth a revisit, and a small "fresh online" section. The slow-changing backlog that lorite-wrap-up-today selects from each evening. Run weekly or on demand — this is the expensive vault scan; the nightly wrap-up must NOT re-run it. Use when asked to refresh the consumption queue / reading-watch-play list, or when the queue runs low.
argument-hint: "(no args = refresh all) · <media type> (refresh one section) · fresh (also pull new online finds)"
---

# lorite-consumption-queue — the single curated "what to consume next" note

Builds and refreshes **one note** the rest of the workflow reads from: a curated, per-media-type shortlist of what to consume next, mixing **work** (research, courses, technical talks) and **personal** (podcasts, videogames, books, series, boardgames, places, food…). This is the *slow* half of the wrap-up system: an expensive vault-wide scan run **weekly or on demand**, so that the nightly **[[lorite-wrap-up-today]]** skill only has to *select* a few items from a ready-made list instead of re-scanning everything each evening.

Vault: `~/git/lorite-obsidian-notes` (use `$VAULT` when the wrapper sets it, e.g. running headless on the home server — see [[lorite-morning-briefing]]). Dates `yyyy-MM-dd`; get the current date from the `time` tool or `date +%Y-%m-%d`.

## The note it owns

- **Path:** `ai_chats/queues/Consumption Queue.md` (AI-writable zone → this skill may **rewrite** it freely; that's why it lives under `ai_chats/` and not in `media/plans/`, where the [[lorite-obsidian-note]] policy allows appends only). `mkdir -p` the folder first — the `obsidian` CLI `create` doesn't make parents.
- **Owner:** this skill. The whole note is AI-generated state — safe to regenerate in full each run. Never write secrets.
- **Cap each section to ~5 items** — a curated shortlist, not a dump of hundreds of unread notes. Overflow lives in the source folders; the queue is the *decision-ready* top.

## When to run / idempotency

- **Cadence:** weekly, or on demand ("refresh the queue", queue looks stale/low). **Not nightly** — the wrap-up reads this note as-is.
- **Freshness stamp:** the note's frontmatter carries `updated: <date>`. If it was refreshed today already and no arg forces it, say so and stop (still fine to re-run with an explicit arg).
- **Partial refresh:** an arg naming one media type refreshes only that section, leaving the rest untouched.

## Personalization signal (drives ranking, gather this FIRST)

The queue is ranked toward **what the user is actually doing lately**, not a flat list. Before curating, read:

1. **Recent tasks worked** — the last ~7 days of `ai_chats/diary/daily/AI Chat - *.md` entries, recently-modified `tasks/` notes (`find "$VAULT/tasks" -name '*.md' -newermt '7 days ago'`), and their `projects`/tags. These reveal active themes (e.g. FoundationPose, PX4/GNSS-denied, Crazyflie yaw, ROS 2 middleware).
2. **Recently consumed media** — notes with a recent `date_saved`/`date_read` and fresh entries in `media/*/` (esp. `media/research/`, `media/videos/`, `media/podcast_episodes/`, `media/books/`). What themes is the user reading/watching around?

Rank each candidate by relevance to those active themes, then by recency of save, then by "quick win" fit (short items that fill commute/waiting gaps). Keep a deliberate **work↔personal balance** in each run so the list never becomes all-PhD.

## Unread filter (critical — the queue is "to consume next", not "consumed")

Media notes carry a unified **`status`** property (the TaskNotes vocabulary — see [[Media notes status property (convention)]]). **Key off `status` directly** (read it with `obsidian property:read name=status path="…"` or a frontmatter grep) — it replaces the old, unreliable per-type booleans:

- **`status: done`** → finished → **exclude** from `New`; eligible only for `🔁 Revisit`, and only when it ties to a currently-active theme.
- **`status: in-progress` / `continuous`** → **`▶ In-progress`**: lead its section and **persist across refreshes** until finished — never bury a weeks-long book/series/game under Revisit or churn it out for novelty.
- **`status: new` / `backlog` / `todo` / `investigating`** → candidates for the `New` sub-section (`new` = "haven't decided yet" · `backlog`/`todo` = queued · `investigating` = sampling).
- **`status: cancelled` / `blocked`** → **skip** (abandoned; or can't proceed / not out yet).
- `released: false` (or a future `year`) → not out yet — exclude even if `status` says otherwise.

**Legacy fallback** — only for notes that don't have `status` yet (articles/research created by workflows not updated until [[Audit other media-type note workflows for status changes (Wallabag, Zotero research, etc.)]] lands): treat `personal_rating > 0` as finished, else `new`. The old `read`/`watched`/`played`/`listened` booleans have been migrated out — don't look for them.

- **Recency of `date_saved` ≠ unread.** Scanning `media/<type>/` by mtime surfaces notes the user *saved*, many already `done`. Use it only as a secondary signal; **`status` + the `TODO …` lists are the authoritative unread backlog.**

## Sources to scan (map each to its section)

Scan broadly, then curate down. Match the vault's real folder taxonomy:

- **Explicit unread buckets** — `media/articles_unread/` (read-it-later), `temporary/` (the clip/idea inbox: short stub notes, often just a title + URL). Treat `temporary/` as *raw inbox* — surface the most relevant, and flag obvious "file me properly" candidates for the user.
- **Per-type media folders** (recent `date_saved`, or explicitly unread): `media/research/`, `media/videos/`, `media/podcast_episodes/` + `media/podcast_series/`, `media/articles/`, `media/books/`, `media/videogames/`, `media/games/`, `media/boardgames/`, `media/series/`, `media/movies/`, `media/shows/`, `media/courses/`, `media/conferences/`, `media/music/`, `media/websites/`, `media/wikis/`, `media/places/`, `media/food/`.
- **The per-type `TODO … I want to …` notes — the authoritative unread backlog, the PRIMARY source for each media section.** There is one per type; enumerate them fresh each run with `find media -iname '*TODO*'` (don't hardcode — the set grows). Currently: `media/books/TODO Books I want to read.md`, `media/series/TODO series I want to watch.md`, `media/movies/TODO Movies I want to watch.md`, `media/videogames/TODO videogames I would like to play.md`, `media/boardgames/TODO Board games I would like to play.md`, `media/podcast_series/TODO podcasts I would like to listen to.md`, `media/videos/TODO Videos I want to watch.md`, `media/conferences/TODO conferences I would like to watch or go to.md`, `media/research/TODO Journal Articles I want to read.md`, `media/articles/TODO Articles and Magazines I want to read.md`, `media/courses/TODO Courses for work I would like to take.md`, `media/projects/TODO projects and repos I want to try out.md`, `media/things/TODO My wishlist.md`. Also the standalone `TODO <title>.md` notes (a `TODO ` filename prefix = an unread item, e.g. `media/books/TODO The Ph.D. Grind…`). **Pull individual items from these lists** — that IS the queue's raw material; don't just link the list note.
- **Cross-cutting plan notes** (activity ideas, not per-type) — `media/plans/General TODO Tasks and Things I can do.md`, `media/plans/Things TODO when little time like commuting or waiting.md`, `media/plans/Things TODO with friends.md`. Feed the `✅ From my TODO/plan notes` section and the personal/social slots.
- **Finished, worth a revisit** — a small `🔁 Revisit` slot: notes the user has **finished** but that connect to a currently-active theme (e.g. a paper worth *re*-reading now that a related task is live). NOT for in-progress items — those lead their own section as `▶ Continue` (see the in-progress rule above).
- **Fresh online** (only with the `fresh` arg, or default a *small* 2–3 item section) — a light `WebSearch`/brave-search pass on the active themes for genuinely new things (a new paper, a talk, a released game). Keep it tiny and clearly labelled `🌐 New online` — the vault backlog is the main course.

## Curate → write the note

For each media type present, pick the top ~5 across all sources, each as a one-line entry: a `[[wikilink]]` (vault note) or `[title](url)` (online), plus a **half-line why** (why now / how it fits a current theme / when to slot it — "commute", "deep-work block", "wind-down"). Keep work and personal visibly mixed.

**Order within every section: `▶ in-progress → 🔁 revisit → new`.** There is **no standalone Revisit section** — a finished-worth-returning item lives inside its own media category, right after any in-progress item and before the new picks. `▶ Continue` (in-progress, long-form) items go first, tagged `▶`, and **stay there on every refresh until finished** — don't let a weeks-long book/series/game get displaced by novelty; the queue exists to help *finish* things, not just start new ones. A section can hold more than one Continue item if several are genuinely on the go.

**Header links its source backlog note as a wikilink**, not a code span: `## 📚 Books · [[TODO Books I want to read]]` (a section fed by two lists links both, e.g. Series & movies → `[[TODO series I want to watch]] · [[TODO Movies I want to watch]]`). Individual items that are real vault notes are wikilinked too; only aspirational titles with no note yet, and raw `temporary/` stubs, stay as plain bold text.

### Note template

```markdown
---
title: Consumption Queue
updated: <yyyy-MM-dd>
tags:
  - queue
  - ai_generated
---

> [!info] Curated by `lorite-consumption-queue` on <yyyy-MM-dd>. The nightly [[lorite-wrap-up-today]] picks from this list. Overflow lives in the source folders — this is only the decision-ready top ~5 per type.

> Order within each section: **▶ In-progress → 🔁 Revisit → New** (`##` sub-headers). Each `#` header links its source [[TODO …]] backlog note and its `[[bases/…]]` view.

Each media category is a **first-level `#` header** that links its source `[[TODO …]]` note **and** its Bases view `[[bases/<NAME>.base]]` (map: Research→`RESEARCH.base`, Videos→`VIDEOS.base`, Articles→`ARTICLES.base`, Books→`BOOKS.base`, Podcasts→`PODCAST SERIES.base` + `PODCAST EPISODES.base`, Videogames→`VIDEOGAMES.base`, Boardgames→`BOARDGAMES.base`, Series&movies→`SERIES.base` + `MOVIES.base`; Courses has no base). Inside it, **second-level `##` sub-headers** `▶ In-progress` / `🔁 Revisit` / `New`, each present only when it has items.

## 📚 Books · [[TODO Books I want to read]] · [[bases/BOOKS.base]]
### ▶ In-progress
- [[<in-progress book>]] — still reading (personal · wind-down)
### 🔁 Revisit
- [[<finished note>]] — <why worth returning to now>
### New
- [[<unread book / TODO item>]] — <why now / when to slot>
- …

## 📺 Series & movies · [[TODO series I want to watch]] · [[TODO Movies I want to watch]] · [[bases/SERIES.base]] · [[bases/MOVIES.base]]
### ▶ In-progress
- [[<in-progress series>]] — in progress, not finished (personal · evening)
### New
- …

## 📄 Research · [[TODO Journal Articles I want to read]] · [[bases/RESEARCH.base]]
### New
- [[<paper lit note>]] — <ties to active task/theme> (work · deep-work block)
- …

## ✅ From my TODO/plan notes
- <item pulled from a plan note> — <source note> (personal · quick)

## 🌐 New online
- [title](url) — <what it is / why it fits> (found <date>)
```
(The real note uses `#` for categories and `##` for the In-progress/Revisit/New sub-headers — shown here one level down to keep this fenced example readable. Follow the live [[Consumption Queue]] note's exact heading levels.)

Only include sub-headers that have items — drop empty ones. There is **no standalone Revisit section** — revisit items sit under their own category. On a **partial** run, edit just the one category.

## After writing

- One-line report to the user: what changed per section, and anything that looked like it needs filing out of `temporary/`.
- Log the refresh via **[[lorite-ai-chat-diary]]** (a short dated diary entry linking `[[Consumption Queue]]`; no per-note detail needed — the queue note *is* the artifact).
- Do **not** run the wrap-up or the morning briefing from here — this skill only maintains the backlog.
