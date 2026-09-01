---
name: lorite-video-note-summary
description: Fill the empty "# AI Summary" and "## Flashcards" sections of Obsidian video notes in media/videos, from each note's own transcript, following the Web Clipper template's own interpreter prompts. These sections are blank on every note clipped headlessly (by the capture pipeline or the phone) because obsidian-clipper-cli has no LLM interpreter. Runs nightly on the home server via lorite-video-note-summary.service, and on demand. Use when asked to summarize video notes, fill missing AI summaries, or generate flashcards for videos.
argument-hint: "(no arg = every pending note, capped) · a note path · --limit N"
---

# lorite-video-note-summary — fill AI Summary + Flashcards on video notes

Vault: `$VAULT` (default `~/git/lorite-obsidian-notes`). Notes live in `media/videos/`.

## Why this exists

The Web Clipper template renders two sections from `{{"prompt"}}` **interpreter variables**, which the browser extension executes with its own LLM. `obsidian-clipper-cli` has no interpreter (`--help` lists no such flag), so anything clipped headlessly arrives with `# AI Summary` and `## Flashcards` blank while browser-clipped notes have them filled. This skill closes that gap the way the rest of this workflow does: **the agent is the LLM, there is no API call**.

The rule this must not break: a note without enough source text is **left alone**, never filled from the model's own knowledge of the video. The transcript is the evidence.

## Procedure

### 1. Find what is pending

```bash
~/git/dotfiles/tools/lorite/obsidian-clipper/video-notes-pending.py --verbose
```

That script is the **single definition of pending** and is shared with the nightly wrapper, so do not reimplement the check. It reports, per note, which of the two sections is missing and whether the usable source is the transcript or the `# About` description, oldest note first. Notes under 200 words of source text are skipped and counted, not queued.

A note whose `## Flashcards` heading does not exist at all is not pending for flashcards. Older notes predate that template revision, and adding the section would be inventing structure the user never asked for.

**Cap the run.** Default to **5 notes** unless told otherwise (`--limit`). These are long transcripts and a runaway nightly job that rewrites forty notes is worse than one that takes five nights.

### 2. Read the template's prompts, do not reinvent them

The prompts are the user's, and they change. Read them from the template rather than hardcoding:

```bash
python3 -c "import json,re; b=json.load(open('$HOME/.config/obsidian-clipper-cli/templates/010-youtube-with-transcript.json'))['noteContentFormat']; \
[print('='*20+'\n'+m) for m in re.findall(r'\{\{\"(.*?)\"\}\}', b, re.S)]"
```

If that file is absent, fall back to `$VAULT/obsidian-web-clipper-settings.json` (the source of truth, from which `export-templates.py` generates the CLI copies). **Never print anything else from that file: it holds API keys.**

Follow whatever those prompts say. As of 2026-09-02 the summary prompt mandates `## Summary`, `## Key points` (with `[mm:ss](http://www.youtube.com/watch?v=<id>&t=<seconds>)` links), `## Technical terms` and `## Conclusion`, and the flashcard prompt asks for 5 to 8 cards mixing types.

### 3. Honor the summary prompt's error-correction instruction

The prompt explicitly says to **correct transcription errors, especially technical terms, software names and specialized vocabulary**, because YouTube auto-captions mangle them. This is real work, not a formality: on one talk it turned "Densenet V2" into **Depth Anything V2**, "counter by function" into **control barrier function**, "scented Kalman filter" into **unscented Kalman filter**, "NX sensor D" into **TensorRT** and "Cocoa dataset" into **COCO**.

Correct only from context and domain knowledge, and only when the intended term is unambiguous. When two readings are genuinely possible, keep the transcript's wording rather than guessing, since a confidently wrong technical term is worse than a clumsy one. **Never invent numbers, names or claims the transcript does not support.**

### 4. Write the flashcards in the syntax the installed plugin actually parses

Check the live config, do not trust memory:

```bash
python3 -c "import json; s=json.load(open('$VAULT/.obsidian/plugins/obsidian-spaced-repetition/data.json'))['settings']; \
print({k:v for k,v in s.items() if 'eparator' in k or 'loze' in k or 'olders' in k})"
```

As of 2026-09-02 that reports `convertFoldersToDecks: true` (so **no `#flashcards` tag**, the folder is the deck), separators `::` (basic), `:::` (bidirectional), `?` and `??` on their own line (multi-line), `convertHighlightsToClozes: true`, and `clozePatterns: ['==[123;;]answer[;;hint]==']`. That last one means **the number goes first and the hint last, both delimited by `;;`**: `==answer==`, `==answer;;hint==`, `==2;;answer==`.

`media/videos` must not be in `noteFoldersToIgnore` for the cards to be picked up. Check rather than assume.

### 5. Edit the note, and only the two sections

Direct file edit. Replace the empty section bodies in place, leaving the heading lines, the frontmatter, `# About`, `# Obsidian Notes` and the whole `# Transcript` untouched.

**Verify each note before moving on:**
- the transcript line count is unchanged,
- the only frontmatter difference is Obsidian's own `updated:` bump,
- the heading structure now matches the notes the extension filled (`## Summary` / `## Key points` / `## Technical terms` / `## Conclusion`),
- `video-notes-pending.py` no longer lists the note.

### 6. Log

Per `lorite-ai-chat-diary`: a short dated entry in the daily diary, and the detail in [[Automate the Obsidian capture + note-enrichment pipeline (obsidian-clipper CLI + instant phone capture)]]. Record which notes were filled, which were skipped and why, and any transcription corrections that mattered. On a nightly run with nothing pending, write nothing at all rather than a "nothing to do" entry.

## Notes & gotchas

- **Obsidian rewrites frontmatter seconds after a note changes**, stripping quotes and localizing `thumbnailUrl` into a `[[<md5>.jpg]]` attachment. A note re-read immediately looks different from the same note a minute later. That is not a regression, so do not "fix" it.
- **Headless runs have no GUI**, so the plugin will not re-scan decks until the app next opens. Nothing to do about it, and nothing to report.
- The two sections are the only ones this skill may write. `# Obsidian Notes` is the user's own space and is never touched.
