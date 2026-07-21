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
  - **Any other note**: append a top-level `# AI Generated` section containing exactly `## Prompt`
    and `## AI Generated Answer`.
- **Never write secrets** into notes (e.g. nothing from `obsidian-web-clipper-settings.json`).

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
- **YAML-safe frontmatter.** Unquoted text fields (`description`, `short_description`, `title`, `aliases`, …) break the note's frontmatter if they contain a **colon-then-space (`: `)** or **begin with** `"` `'` `[` `{` `-` `>` `|` `@` `` ` `` `#`. Write an em dash ` — ` where you'd use a colon (incl. book/paper subtitles), and reword so a value never opens with a quoted phrase. If a `: ` or leading quote is unavoidable, single-quote-wrap the whole value and double every internal `'`.
- Keep titles human-readable and filesystem-safe; date prefix `YYYY-MM-DD` for `ai_chats/notes/` notes.
- Pre-2026-07-13 notes in `ai_chats/notes/` keep their historical `YYYY-MM-DD AI Brain - <Title>` names (from the retired `ai_brain/` folder) — don't rename them; new notes drop the "AI Brain" prefix.

## Output
Report: the note path written/appended, the mechanism used (CLI or file fallback), and a one-line summary of what was written. If the target was outside `ai_chats/`, confirm only an `# AI Generated` append was made.
