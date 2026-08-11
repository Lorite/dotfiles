---
name: lorite-obsidian-note
description: Safely create or append an Obsidian vault note following the AI-write policy (AI writes only inside ai_chats/; outside it, append under an "AI Generated" heading and never rewrite existing content) and Obsidian Flavored Markdown conventions. The shared note-writing procedure used by lorite-obsidian-ai-brain, other pipeline agents, and you directly. Works via the Obsidian CLI when the app is running, with a direct file-write fallback when it isn't.
argument-hint: "title=<note title> [content=<markdown>] [target=notes|<path-outside-ai_chats>] [links=[[A]],[[B]]]"
---

# lorite-obsidian-note — the safe vault-write procedure

This is the **single, canonical way** to write notes into the Obsidian vault (`~/git/lorite-obsidian-notes`). `lorite-obsidian-ai-brain` and any other agent that needs to write a note should follow this exact procedure so scope and formatting stay consistent. Reading/querying the vault is out of scope here — use the `lorite-obsidian-bases` skill (Bases) and `obsidian` CLI search for that.

## The write policy (never violate)
- **AI writes only inside `ai_chats/`** — the vault's AI free-write zone, laid out by kind: `ai_chats/notes/` (working notes/deliverables — this skill's default target), `ai_chats/briefings/daily/` (morning briefings), `ai_chats/diary/daily/` (the work diary, via `lorite-ai-chat-diary`), `ai_chats/chats/` (saved transcripts).
- **Outside `ai_chats/` you may only *append*, never rewrite** existing content (the rest of the vault is hand-maintained by the user):
  - **Task notes** (`type: task`, in `tasks/`): put AI content under `# 📓 Journal / Work Log` →
    `## [[YYYY-MM-DD]]` (today) → `### AI generated`. New dated entries go at the **top** of the
    Journal section (newest-first); leave existing entries untouched.
  - **Checkbox exception (task notes):** you may tick a `- [ ]` → `- [x]` checkbox in a task
    note's `# 🎯 Task Description` when the subtask is **verifiably done** (evidence stated in the
    journal entry you write alongside). Toggle only the checkbox state — never edit, reword, or
    reorder the item text, and never untick a box the user checked.
  - **High Level TODOs exception (task notes):** a task note may carry an **AI-owned** `## High Level TODOs` subsection at the **end** of its `# 🎯 Task Description` (after the user's own bullets/checkboxes, before the next heading); create it lazily the first time you have a forward plan to record. Unlike the user's hand-written checklist above it — which you may only tick — **this list is yours to maintain**: **add** a new `- [ ]` (nestable — indent to nest), **complete** `- [ ]` → `- [x]` at the same evidence bar as the checkbox exception (verifiably done, logged in the journal), and **remove** by striking the text `~~like this~~` rather than deleting the line (abandoned / superseded / no-longer-relevant — keep the trail). Never migrate the user's hand-written subtasks into it; the two lists stay separate. It holds the **living forward plan** (what's left) — distinct from the `# 📓 Journal / Work Log` dated history (what happened) — so refresh it whenever you log to the note.
  - **Status exception (task notes):** you may set the `status` frontmatter field to **todo /
    investigating / in-progress / blocked / pending-review / cancelled** as the work state actually
    changes — notably **`pending-review`** when the deliverable is finished and awaits the user's
    review. **Never set `done`** (completion is the user's call), and don't touch other frontmatter.
    Log the change + evidence in the journal entry.
  - **Outcome & Learnings exception (task notes) — fill it when you set `pending-review`.** The
    task template ships a `# ✅ Outcome & Learnings` section with three placeholder subsections
    (`## Outcome` · `## Learnings` · `## Next Steps`, each holding a bare `- TODO`). **When — and
    only when — you transition the task to `status: pending-review`** (its deliverable is finished),
    fill all three by **distilling the note's own `# 📓 Journal / Work Log`** (synthesize what the
    journal already records; don't re-derive the work): **Outcome** = what was delivered and the end
    state; **Learnings** = the load-bearing findings, decisions + *why*, and gotchas worth carrying
    forward; **Next Steps** = what's left / follow-ups (mirror the open `## High Level TODOs`).
    Grounding still applies — only claims backed by the journal/session output; mark anything
    unverified as such. **Replace the `- TODO` placeholder only**; if a subsection already holds the
    user's hand-written text, append beneath it under an `_(AI generated)_` line rather than
    overwriting (never rewrite the user's content). Missing section/subsections → add them under the
    template's headings. Use a **direct file edit** for this positioned fill.
  - **Any other note**: append a top-level `# AI Generated` section containing exactly `## Prompt`
    and `## AI Generated Answer`.
  - **Related-notes exception (task notes — user grant [[2026-07-31]]): the AI finds and maintains
    the links itself.** A task note may carry an **AI-owned `## Related notes` subsection** at the
    end of `# 🎯 Task Description` (after `## High Level TODOs` if present; create it lazily): a
    bullet list of `[[wikilinks]]` to the reference notes this task touches. Populate it by
    **keyword search over note names, `aliases:`, and `tags`** (plus Bases queries) using the task's
    own terms, and add any note the session actually consulted or edited. Maintain it like High
    Level TODOs — add freely, retire by striking `~~[[X]]~~`, never touch the user's own links.
    These links (anywhere in the task note — the user's, the journal's, or this list) are what put
    a reference note **in scope for the inline-maintenance exception below**, so keeping this list
    honest is part of keeping the vault current.
  - **Inline-maintenance exception (reference notes wikilinked from the driving task note — user
    grant [[2026-07-31]]).** Append-only builds a split brain on reference notes: the hand-written
    body keeps stating the outdated fact while the correction sits in an appended section below, and
    readers trust the top. So in a note that is **wikilinked from the task note driving the current
    session**, you may keep the body factually current:
    - **Add** a short sentence or bullet where the new fact belongs (matching the note's own style).
    - **Correct** an outdated statement by **strike-and-replace with a date**:
      `~~old fact~~ new fact ([[<yyyy-MM-dd>]])`. **Strike, never delete or reword** — the
      hand-written original must stay readable in place, not only in git.
    - **Cross out** a statement that is simply no longer true the same way (strike + date), even
      with no replacement.
    Hard limits: only facts **verified by this session's tool output** (never "probably outdated");
    short factual statements only — never restyle the user's prose, and for opinion-like or
    meaning-changing edits **ask instead**; no frontmatter (beyond the task-status exception), no
    `templates/`, no `diary/` notes, no `people/` notes; and **log every inline edit in the task
    note's journal entry** (which note, what changed, the evidence). Anything bigger or uncertain
    still goes through the `# AI Generated` append path. The vault's git history plus the morning
    briefing's daily commit audit are the safety net — keep edits small enough that a diff reads at
    a glance.
  - **Creation exception (new reference notes, anywhere in the vault — user grant [[2026-07-31]]).**
    Inline maintenance can only fix notes that already exist. When a session verifies a real thing
    that has **no note at all**, you may create one **anywhere in the vault**, not just `ai_chats/`.
    The narrowness lives in the evidence bar and the review loop, not in a folder whitelist:
    - **Prove it is missing first.** Search note **names *and* `aliases:` across the whole vault**
      before concluding nothing covers it — a basename search in one folder is not evidence (the
      `[[Lenovo ThinkPad P15 Gen 2i]]` near-miss of 2026-07-31 is exactly why this clause exists).
      If any note covers the thing, maintain it inline instead of creating a second one.
    - **Only for something this session actually verified exists** — the same evidence bar as inline
      maintenance. Never create a note for something inferred, planned, or merely believed.
    - **Match the destination's conventions**: the template/schema of the folder you're writing into,
      the vault's path→tags convention, **and the `work`/`personal` domain tag** (see the tagging
      exception below). Copy the shape of a sibling note in that folder.
    - **Write only what you verified.** A short honest stub beats an invented encyclopedia entry;
      mark anything unconfirmed `[VERIFY: …]`. Never invent dates, prices, specs, or history.
    - **Mark it for review — mandatory.** Add **`ai_created: <yyyy-MM-dd>`** to the frontmatter. The
      morning briefing lists every note carrying a fresh `ai_created:` date so the user can review or
      delete it (see the `lorite-morning-briefing` skill). A created note **without** this field is
      invisible to that review, so omitting it is a policy violation, not a formatting slip.
    - **Log it** in the task note's journal and add it to `## Related notes`, like any other edit.
    - **Do not create**, each for a concrete reason: `templates/` (Templater sources, not notes),
      `diary/daily/` (owned by the daily-note pipeline), and `tasks/` (created through `mtn` /
      `lorite-task-manager` so ids and schema stay consistent). **People notes ARE allowed** —
      the user lifted that exclusion on [[2026-07-31]] now that the briefing review loop exists.
      Same bar as everything else: only real people the session actually encountered in the vault,
      a thin honest stub (never invented biography), matching `people/`'s template, and stamped
      `ai_created:` so each one lands in the briefing for review.
    When unsure whether a thing deserves its own note, **add the fact to an existing note instead**.
    A wrongly created note is worse than a wrong correction: a strikethrough is self-evident and
    reversible in place, while a bogus note is a new object someone has to find and delete.
  - **Archiving exception (retiring a note for something no longer used — user grant
    [[2026-07-31]]).** The vault archives a note in exactly two steps, which the user's QuickAdd
    "Archive Current Note" macro performs (`scripts/add-archived-tag.js` + `scripts/move-to-archived.js`)
    and which you replicate directly when working outside the GUI:
    1. add `archived` to the note's `tags:` frontmatter array (leave every other tag alone), and
    2. move the file to a **sibling `archived/` folder** — `media/digital_tools/Karakeep.md` →
       `media/digital_tools/archived/Karakeep.md`. Never invent a different archive location, and
       skip the move if any path segment is already `archived`.
    Use `git mv` so history follows the file. Wikilinks are **basename**-resolved, so a folder move
    does not break `[[Name]]` links — but grep for path-style links (`[[media/digital_tools/Name]]`)
    before moving and fix any you find.
    - **Evidence bar: prove disuse, don't infer it.** A note may be archived only when this session
      verified the thing is no longer in use — the service has no container/unit on the host, its
      task note is `cancelled`, the account is closed, the tool was explicitly replaced. Two
      independent signals is the standard (e.g. "no container at all" *and* a `status: cancelled`
      task). **Absence of evidence is not evidence of disuse**: plenty of tools are used without
      running on a server, so a missing container proves nothing about, say, a phone app.
    - **Never archive** notes that are still linked as current by an active task, `tasks/` notes
      (use `mtn archive`), daily notes, or anything the user touched recently — ask instead.
    - **Stamp and log it**: add `ai_archived: <yyyy-MM-dd>` to the frontmatter so the morning
      briefing surfaces it for review, and record the evidence in the task note's journal.
    Archiving is reversible (the QuickAdd "Unarchive Current Note" macro undoes both steps), which
    is exactly why it must stay cheap to audit — one line per archived note in the briefing.
  - **Tagging exception (bringing any note up to the tagging convention — user grant [[2026-08-10]], extended [[2026-08-11]]).** **This applies to every in-scope note, not only untagged ones.** A note that already has tags is still a candidate: existing tags are never a reason to skip it, they are only a floor you add on top of. "Already tagged" is what let 2,553 notes drift domain-less — an imported clipping arrives carrying `media, articles`, passes any is-it-tagged check, and is never looked at again. Check all three layers independently, and fill whichever are missing:
    1. **Folder-path tags** per the vault's path→tags convention (`media/articles/` → `media, articles`; `temporary/` → `temporary`). Add any that are absent, even when other tags are present.
    2. **Topical tags** — bring the note to 1 to 3 of them, **reused from the existing vocabulary** (`obsidian tags counts`, or a frontmatter scan when headless), preferring tags already used at least twice (the hierarchical `engineering/…` ones are the interesting ones for technical content). A note that already has 3 good topical tags needs nothing here; one that has only folder tags gets topped up. A new tag is allowed only when nothing existing fits (snake_case, reported for review).
    3. **The `work`/`personal` domain tag** — one or both. **Every note carries a domain tag**: `work` (PhD, ITU/Novo Nordisk, MiR, academic study incl. the JEMARO master's, robotics/software craft, career), `personal` (life, home, health, food, family and friends, hobbies, travel, news, personal finance), or **both** when it genuinely spans the two, as [[Cloudflare]], [[Coolify]] and [[BOOX Note Air4 C]] already do.
    When the note genuinely gives you nothing to judge (dead link, blocked scrape, empty capture), **leave it and report it** rather than guessing; it is a deletion candidate, not a tagging one.
    Strictly **add-only**: insert the `tags:` block (or replace an empty key), append to it otherwise, and touch nothing else — never edit, reorder or remove existing tags, other frontmatter, or the body. Stamp **`ai_tagged: <yyyy-MM-dd>`** so the morning briefing lists it for review; when the note already carries an older `ai_tagged:` from a previous pass, **overwrite it with today's date** (it is an AI-owned field, and a stale date hides the note from the review greps — 25 notes slipped through that way on [[2026-08-11]]). Parse the **whole** frontmatter before deciding (Media DB notes hide `tags:` below long `plot:` fields), and handle **all three `tags:` shapes**: block list, `[a, b]`, and the **inline scalar** `tags: knowledge-management media articles` that older wallabag imports use. Obsidian splits that scalar on commas *and* spaces, so never restructure it into a list — append in place (`tags: knowledge-management media articles, work`), or you silently merge several real tags into one bogus tag. After any bulk pass, **audit the diff for deleted lines** instead of trusting the script's own success count; that is what caught the 24 collapsed notes on [[2026-08-11]].
    Excluded from all three layers: `ai_chats/`, `templates/`, `attachments/`, `diary/`, `KOReader/`, dotfolders, `.trash/` — plus, for the domain tag specifically, anything per-day or machine-owned where it carries no meaning (`diary/daily/`, the `ai_chats/` diaries and briefings, `calendar_events` are tagged but daily notes are not, dashboards, `bases/`, `tests/`, `_spaced_repetition/`). `temporary/` is the triage inbox and is deliberately left domain-less until its notes are filed. The morning briefing runs this daily over the last 24 h of new **and modified** notes (its step 4c); bulk backfills over the whole vault happen only on explicit request.

## Inputs (when called by another agent or the user)
- `title` — note title (required for a new note).
- `content` — the markdown body to write (already-synthesized; this skill doesn't research).
- `target` — `notes` (default → new `ai_chats/notes/` note) **or** an exact path to an existing note outside `ai_chats/` (→ the `# AI Generated` append path).
- `links` — wikilinks to related notes/sources to include.
- `source` — optional path to a source artifact to summarize/link (e.g. a lorite-paper-reader markdown at `~/.config/paper-scout/notes/<x>.md`). Read it, then write the note; **link**, don't dump verbatim.

## Mechanism: CLI-first, file-fallback
**1. Try the Obsidian CLI** (preferred — keeps templates/Bases/links consistent; needs the desktop app running with the vault open). Probe with a harmless command, e.g. `obsidian aliases total`; if it errors, the app isn't running → use the file fallback (step 2). Canonical CLI commands:
- New AI note: `obsidian create path="ai_chats/notes/YYYY-MM-DD <Title>.md" template=ai_note`
- Append: `obsidian append path="..." content="..."`  (multi-line is flaky — prefer small appends, or create then edit)
- Structure first: `obsidian outline path="..."` — call before `read` for any note longer than ~1 screen; heading tree shows which section to read.
- Read/search: `obsidian read path="..."` · `obsidian search:context query="..." path="..."` (matching lines + context in one call; prefer over `search` + `read`) · `obsidian search query="..."` (file paths only)
- Single field: `obsidian property:read name=<field> path="..."` — fast path for one frontmatter value (e.g. `status`, `type`, `projects`) without reading the whole file.

**2. File fallback** (app/CLI unavailable, e.g. headless/container). Write the markdown file directly under `~/git/lorite-obsidian-notes/`, following Obsidian Flavored Markdown (see the `lorite-obsidian-markdown` skill for wikilinks/callouts/properties).
- New AI note → write `ai_chats/notes/YYYY-MM-DD <Title>.md` using the template below.
- Append outside `ai_chats/` → read the target file, append the `# AI Generated` block at the end, write back unchanged otherwise.

### `ai_note` template (use verbatim in the file fallback)
```markdown
---
created: "YYYY-MM-DD HH:mm"
source: ai
---

# <Title>

## Context

## Prompt

## AI Generated Answer

## Follow-ups
- [ ]

## Links
-

## Sources
- Obsidian CLI:
  -
- Bases:
  -
- Web:
  -
```

### Task-note journal entry (notes with `type: task`, in `tasks/`)
```markdown
## [[YYYY-MM-DD]]

### AI generated

<the AI-written content>
```
Insert at the **top** of the `# 📓 Journal / Work Log` section (newest-first), leaving existing dated entries intact. Use a **direct file edit** for this positioned insert — the CLI `append` only adds to the end of the file, which is the wrong place.

### `# AI Generated` append block (for other notes outside `ai_chats/`)
```markdown

# AI Generated

## Prompt

<the request/prompt>

## AI Generated Answer

<the answer>
```

## Images & diagrams (embedding visual output the agent created)
When the work produced a visual — an architecture/flow diagram, a data plot, a screenshot, a schematic — put it **inside** the note, don't just describe it or leave it in another repo. Choose the path by type:

- **Text-expressible diagrams → embed inline as a fenced code block, no file.** Obsidian renders **Mermaid** natively: drop a fenced ` ```mermaid ` flowchart / sequence / graph / class / state block straight into the note. This is the **default** for agent-drawn diagrams — editable, diffable, theme-aware, and it survives git. Prefer it over exporting an image whenever the diagram can be expressed as Mermaid. Use the `lorite-mermaid-gantt` skill for gantt/roadmap styling and the `lorite-obsidian-markdown` skill for Mermaid syntax.
- **Binary images (matplotlib/plot `.pdf`·`.png`, screenshots, exported `.svg`/draw.io) → save into the vault attachment folder, then embed with a wikilink.** The vault's attachment root is `attachments/` (`attachmentFolderPath`); **AI-generated figures go in its `attachments/ai_chats/` subfolder** (kept out of the hand-managed attachment root). Embeds are **wikilink-style** (Obsidian default — matches every existing embed):
  1. Write the file into `~/git/lorite-obsidian-notes/attachments/ai_chats/` with a **descriptive, collision-safe name** — `YYYY-MM-DD <task-slug> <what-it-shows>.png` — **not** a random hash or "Pasted image …", so it's identifiable at a glance. Prefer **vector** (`.pdf`/`.svg`) for plots/figures, `.png` for screenshots.
  2. Embed it where the detail refers to it with a bare-filename wikilink — `![[<filename>.png]]` (the wikilink resolves across folders) — and add a one-line *italic caption* under it stating the takeaway, so the figure is a standalone argument.
  - **draw.io** (`obsidian-diagrams-net`) and **Excalidraw** (`obsidian-excalidraw-plugin`) are both installed and render in-app — save the `.drawio`/`.svg` / `.excalidraw.md` under `attachments/ai_chats/` and embed the same way.
- **Never** paste base64 image data into a note, and never embed a path *outside* the vault (`![[/home/…]]` won't resolve) — copy the file into `attachments/ai_chats/` first. Figures a data/analysis run left in another repo (e.g. the robotics `results/<timestamp>_*/`) must be **copied into `attachments/ai_chats/`** to appear in the note.
- **Mechanism:** the image file itself is always a **direct file write** (the `obsidian` CLI writes note text, not binaries); the `![[…]]` embed line goes into the note via the same positioned edit you use for the journal entry — on both the CLI and file-fallback paths.

## Conventions
- Use wikilinks `[[Note]]` for everything linkable; link liberally. Use callouts/properties per the `lorite-obsidian-markdown` skill. Put sources under `## Sources` (CLI/Bases/Web).
- **YAML-safe frontmatter — quote first, don't rely on rewording.** Any free-text field (`description`, `short_description`, `title`, `summary`, `aliases` items, …) breaks the note's *entire* property block if its value contains a **colon-then-space (`: `)** or **begins with** `"` `'` `[` `{` `-` `>` `|` `@` `` ` `` `#`. **Default: single-quote-wrap every free-text value you write and double each internal `'`** (`Tracy's` → `'…Tracy''s…'`). Do that mechanically rather than eyeballing whether a given sentence "needs" it — prose fields of 3+ sentences hit this constantly, and the whole note's properties disappear from Obsidian when they do. Rewording (em dash ` — ` in place of a colon) is a nicety on top, never the safeguard.
  - **Verify after writing** — don't assume; the note renders fine as text while its properties are dead:
    ```bash
    python3 -c "import sys,yaml;t=open(sys.argv[1]).read();yaml.safe_load(t[4:t.find(chr(10)+'---',3)]);print('OK',sys.argv[1])" "<note path>"
    ```
  - To sweep the whole vault for already-broken notes, see `scripts/check_frontmatter.py` (skips `templates/`, whose unrendered Templater/Clipper syntax is not valid YAML by design).
- Keep titles human-readable and filesystem-safe; date prefix `YYYY-MM-DD` for `ai_chats/notes/` notes.
- Pre-2026-07-13 notes in `ai_chats/notes/` keep their historical `YYYY-MM-DD AI Brain - <Title>` names (from the retired `ai_brain/` folder) — don't rename them; new notes drop the "AI Brain" prefix.

## Output
Report: the note path written/appended, the mechanism used (CLI or file fallback), and a one-line summary of what was written. If the target was outside `ai_chats/`, confirm only an `# AI Generated` append was made.
