---
name: lorite-koreader-highlights
description: Ingest KOReader highlight exports into the Obsidian vault — parse the exported JSON, map each highlight's colour to a category (yellow=general, red=super, green=concept, blue=quote, purple=heading, pink=vocabulary, orange=figure; gray/unknown → AI-classified from the text), format it the vault's colour way, append it to the matching note (Media-DB book note, Zotero literature note, or an inbox), and route vocabulary words to the per-language Spaced-Repetition decks. Idempotent via a state file. Runs on demand and as a step of lorite-morning-briefing. Use when asked to import/process KOReader highlights or "the reading highlights".
argument-hint: "(no args) · dry (preview, don't write) · <path to an export dir>"
---

# lorite-koreader-highlights — KOReader highlights → Obsidian (classify, format, route)

Turns [[KOReader]]'s exported highlights into formatted vault content, replacing the old Readest colored-export template with one flow that covers **ebooks, general PDFs, and Zotero papers**. Since I read on e-ink, most highlights carry an explicit **colour** (deterministic category); only **gray/uncoloured** ones need the LLM to classify. Tracked by the tasks [[Set up KOReader on all my devices (replacing Readest)]] and [[Set up a dictionary + Obsidian spaced-repetition vocabulary workflow]].

## Inputs & runtime

- **Source = AnnotationSync JSON** (decided 2026-07-18, architecture B′): the `AnnotationSync.koplugin` sync folder, Nextcloud-synced to **both** the laptop and the headless home server. One `<document>.json` per book/doc, keyed by annotation position-id. This is the only representation synced everywhere (book files + `.sdr` sidecars are NOT), so the t5k6 plugin is **not** used. Default dir auto-detected (laptop `~/nextcloud-all/westerndigitalnvmessd/Documents/media/koreader/AnnotationSync`, server `/westerndigitalnvmessd/Documents/media/koreader/AnnotationSync`); override with `$KOREADER_ANNOTATIONSYNC_DIR` or `--dir`.
- **Vault root** — use `$VAULT` when set (the morning-briefing wrapper sets it; on the server it's the Syncthing copy). Else `~/git/lorite-obsidian-notes`.
- **Parser tool** — `~/git/dotfiles/tools/koreader/parse_annotationsync.py` (stdlib only). It dedups against `<vault>/.koreader-highlights/state.json` (shared across hosts via Syncthing) and maps colour→category. **Never classify or dedup by hand — always go through the tool.**
- Honour the **`lorite-obsidian-note`** write policy (append-only outside `ai_chats/`, under an `# AI Generated` / `%% begin annotations %%` region; never rewrite hand-written content; never write secrets) and **`lorite-obsidian-markdown`** for syntax.

## Procedure

### 1. Get the new highlights (read-only preview)

```bash
python3 ~/git/dotfiles/tools/koreader/parse_annotationsync.py --pretty
```

Output is grouped **by document** (`docs[]`, each with `title`, `ext`, `highlights[]`); each highlight has `text, note, chapter, page, datetime, colour, category, is_tmp, hash`. `total_new: 0` → nothing to do, stop. **Do not pass `--commit` yet** — that comes after the writes succeed (step 5). Note: a doc whose `title` is a hash (KOReader's internal/quickstart docs) or otherwise unmatchable → send to the inbox (step 3).

### 2. Classify the gray ones

For every highlight with `category: "gray"`, infer the real category from its text:

- **vocabulary** — a single word / short span in one of my study languages (Danish, Spanish, Italian, Basque, English) that reads like an unknown term. → routes to an SR deck (step 3).
- **quote** — a full sentence/passage worth keeping verbatim.
- **concept** — a term + its definition, a named idea, a person/place/date/fact.
- **heading** — a short title-like line (often matches a section/chapter heading).
- **general** — anything else.

Colour categories (`general/super/concept/quote/heading/vocabulary/figure`) are already decided — **don't second-guess a coloured highlight**, only the gray ones. Ground each call in the text; when genuinely unsure, use `general`.

### 3. Format each highlight the vault colour way, and resolve its target note

Formatting (from [[Notes color highlighting]]):

| category | colour | render |
|---|---|---|
| general | yellow | `- {text}` |
| super | red | `- ❗ {text}` (also list under a "Super Highlights" heading if the note has one) |
| concept | green | `- {text}` — wrap clear key terms/people/places as `[[wikilinks]]` |
| quote | blue | `> {text}` |
| heading | purple | `### {text}` |
| figure | orange | `- 🖼️ {text}` |
| vocabulary | pink | see below → SR deck |

If a highlight has a `note`, append `  > **Note:** {note}` under it. Optionally add ` *(p. {page})*`.

**Target note** (resolve by the book's `title` / `author`):

1. **Zotero paper** — if the title matches a `media/research/<title> - <citekey>.md` literature note (search the vault; check `cite_key`/aliases), append the formatted highlights **inside its `%% begin annotations %%` block** under `## Imported from KOReader on [[<date>]]`, matching the shape the Zotero sync writes. **Dedup against text already in that block** (a paper annotated on both the BOOX-embedded path and KOReader must not double-import).
2. **Book** — if a Media-DB book note exists (`media/books/…` or wherever the title/author matches), append under its highlights section (create a `# Highlights & Annotations` / `# AI Generated` section if absent, append-only).
3. **Unmatched** (general PDF, or a book with no note yet) — append to the inbox note `ai_chats/notes/KOReader highlights inbox.md` (free-write zone) under `## {title} — [[<date>]]`, so nothing is lost; note it in the run summary for me to file.

### 4. Route vocabulary → the per-language SR decks

For each `vocabulary` highlight: detect the language (from the book's language or the word), look up a short definition (Wiktionary REST — `https://en.wiktionary.org/api/rest_v1/page/definition/<word>`, JSON keyed by language code, definitions are HTML → strip tags), and append a **bidirectional** card to `personal/languages/<lang>/<Lang> Vocabulary.md` (create if missing; folder = deck, no `#flashcards` tag):

```
{word} ::: {short definition}
```

This is the same deck + format the `Add vocabulary card` macro uses. Keep the word in the book note too (as `- ✨ {word}`) so the source is traceable.

### 5. Commit the state, then log

Only after the writes succeed:

```bash
python3 ~/git/dotfiles/tools/koreader/parse_annotationsync.py --commit >/dev/null
```

Then log via **`lorite-ai-chat-diary`**: a diary entry (counts per book + per category, decks touched, anything sent to the inbox) and — since the detail already lives in the target notes — link them. If run inside `lorite-morning-briefing`, one line in the briefing suffices.

## Idempotency & safety

- The `--commit` step records hashes so a re-run imports nothing twice. If a run dies before step 5, nothing was committed → the next run re-emits the same set (safe).
- Coloured categories are deterministic; only gray needs the LLM, so headless morning runs are cheap and stable.
- If the export dir is missing or `total_new: 0`, exit quietly.

## Morning integration

`lorite-morning-briefing` calls this as one step (after the vault audit, before writing the briefing). It runs where the KOReader export folder is synced; on a host without it, the tool reports the dir missing and the step is a no-op.

## Gotchas

- **AnnotationSync JSON format** — each file is a dict keyed by position-id → annotation (`text, color, page/pageno, chapter, datetime, drawer`, optional `note`). Parser tested against real data 2026-07-18. `*.progress.json` and `settings_sync.json` are skipped.
- **Hash-named / internal docs** — some files are named by a hash (e.g. `a91bb1…json`) or are KOReader's own quickstart; their `title` won't match a vault note → route to the inbox, don't force a match.
- **`is_tmp: true`** appears on some highlights (seen on fresh ones) — it's passed through, not filtered; revisit if it turns out to mean "unsynced/pending" and causes premature imports.
- **Routing has no source path** — AnnotationSync JSON doesn't carry the KOReader folder, so content-type is inferred by matching `title` against the vault (`media/research` cite_key/title → research; book note → book; Wallabag article → article; else inbox). The `Author - Year - Title` filename pattern is a strong research-paper signal.
- EPUB highlights are never embedded in the file (format limit) — fine, this flow reads AnnotationSync's synced JSON, not embedded annotations. (Zotero PDFs annotated on the BOOX with *embedded* highlights still also feed the separate `zotero-obsidian-sync` timer; dedup by text when merging into a literature note.)
