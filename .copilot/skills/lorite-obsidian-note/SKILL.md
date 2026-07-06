---
name: lorite-obsidian-note
description: Safely create or append an Obsidian vault note following the AI-write policy (AI writes only inside ai_brain/; outside it, append under an "AI Generated" heading and never rewrite existing content) and Obsidian Flavored Markdown conventions. The shared note-writing procedure used by lorite-obsidian-ai-brain, other pipeline agents, and you directly. Works via the Obsidian CLI when the app is running, with a direct file-write fallback when it isn't.
argument-hint: "title=<note title> [content=<markdown>] [target=ai_brain|<path-outside-ai_brain>] [links=[[A]],[[B]]]"
---

# lorite-obsidian-note — the safe vault-write procedure

This is the **single, canonical way** to write notes into the Obsidian vault
(`~/git/lorite-obsidian-notes`). `lorite-obsidian-ai-brain` and any other agent that needs to write a note should
follow this exact procedure so scope and formatting stay consistent. Reading/querying the vault is
out of scope here — use the `lorite-obsidian-bases` skill (Bases) and `obsidian` CLI search for that.

## The write policy (never violate)
- **AI writes only inside `ai_brain/`.** The default action is to create/append an `ai_brain/` note.
- **Outside `ai_brain/` you may only *append*, never rewrite** existing content (the rest of the
  vault is hand-maintained by the user):
  - **Task notes** (`type: task`, in `tasks/`): put AI content under `# 📓 Journal / Work Log` →
    `## [[YYYY-MM-DD]]` (today) → `### AI generated`. New dated entries go at the **top** of the
    Journal section (newest-first); leave existing entries untouched.
  - **Checkbox exception (task notes):** you may tick a `- [ ]` → `- [x]` checkbox in a task
    note's `# 🎯 Task Description` when the subtask is **verifiably done** (evidence stated in the
    journal entry you write alongside). Toggle only the checkbox state — never edit, reword, or
    reorder the item text, and never untick a box the user checked.
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
- `target` — `ai_brain` (default → new `ai_brain/` note) **or** an exact path to an existing note
  outside `ai_brain/` (→ the `# AI Generated` append path).
- `links` — wikilinks to related notes/sources to include.
- `source` — optional path to a source artifact to summarize/link (e.g. a lorite-paper-reader markdown at
  `~/.config/paper-scout/notes/<x>.md`). Read it, then write the note; **link**, don't dump verbatim.

## Mechanism: CLI-first, file-fallback
**1. Try the Obsidian CLI** (preferred — keeps templates/Bases/links consistent; needs the desktop
app running with the vault open). Probe with a harmless command, e.g. `obsidian aliases total`; if it
errors, the app isn't running → use the file fallback (step 2). Canonical CLI commands:
- New `ai_brain` note: `obsidian create path="ai_brain/YYYY-MM-DD AI Brain - <Title>.md" template=ai_brain`
- Append: `obsidian append path="..." content="..."`  (multi-line is flaky — prefer small appends,
  or create then edit)
- Structure first: `obsidian outline path="..."` — call before `read` for any note longer than ~1 screen; heading tree shows which section to read.
- Read/search: `obsidian read path="..."` · `obsidian search:context query="..." path="..."` (matching lines + context in one call; prefer over `search` + `read`) · `obsidian search query="..."` (file paths only)
- Single field: `obsidian property:read name=<field> path="..."` — fast path for one frontmatter value (e.g. `status`, `type`, `projects`) without reading the whole file.

**2. File fallback** (app/CLI unavailable, e.g. headless/container). Write the markdown file directly
under `~/git/lorite-obsidian-notes/`, following Obsidian Flavored Markdown (see the
`lorite-obsidian-markdown` skill for wikilinks/callouts/properties).
- New `ai_brain` note → write `ai_brain/YYYY-MM-DD AI Brain - <Title>.md` using the template below.
- Append outside `ai_brain/` → read the target file, append the `# AI Generated` block at the end,
  write back unchanged otherwise.

### `ai_brain` note template (use verbatim in the file fallback)
```markdown
---
created: "YYYY-MM-DD HH:mm"
source: ai_brain
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
Insert at the **top** of the `# 📓 Journal / Work Log` section (newest-first), leaving existing dated
entries intact. Use a **direct file edit** for this positioned insert — the CLI `append` only adds to
the end of the file, which is the wrong place.

### `# AI Generated` append block (for other notes outside `ai_brain/`)
```markdown

# AI Generated

## Prompt

<the request/prompt>

## AI Generated Answer

<the answer>
```

## Conventions
- Use wikilinks `[[Note]]` for everything linkable; link liberally. Use callouts/properties per the
  `lorite-obsidian-markdown` skill. Put sources under `## Sources` (CLI/Bases/Web).
- Keep titles human-readable and filesystem-safe; date prefix `YYYY-MM-DD` for `ai_brain` notes.

## Output
Report: the note path written/appended, the mechanism used (CLI or file fallback), and a one-line
summary of what was written. If the target was outside `ai_brain/`, confirm only an `# AI Generated`
append was made.
