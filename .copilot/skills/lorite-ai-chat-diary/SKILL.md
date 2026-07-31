---
name: lorite-ai-chat-diary
description: Log the current work to the daily Obsidian AI-chat diary (ai_chats/diary/daily/AI Chat - yyyy-MM-dd) — a lightweight time-stamped entry with wikilinks — and write the full detail into each linked note where its type dictates (task notes → a dated "### AI generated" entry inside their "# 📓 Journal / Work Log"; other notes → a "# AI Generated" section). The shared work-logging procedure used by lorite-obsidian-ai-brain, the pipeline agents, and the user.
argument-hint: "<short summary of what was done> + which notes to link (task / paper / project)"
---

# lorite-ai-chat-diary — log work to the daily AI-chat diary

The **single, canonical way** to record what was worked on, so any later session can reconstruct context fast. Used by `lorite-obsidian-ai-brain`, every PhD-pipeline agent (`lorite-paper-scout`, `lorite-paper-reader`, `lorite-task-manager`, `lorite-experiment-designer`, …), and the user directly. Two parts: a lightweight **diary entry** (the index) and the **full detail in the linked note(s)**.

> [!important] **The split is the whole point — get it right (a common failure).** The **corresponding *task note* Journal is where the full detail lives** (findings, decisions + *why*, numbers, commit hashes, replicate commands, next steps — written to stand alone). The **daily AI-chat diary gets ONLY a short high-level entry** — 2–4 sentences + `[[wikilinks]]`. It is an *index that points at the task notes*, not the record. **Never write long detail into the diary while leaving the task note thin.** And write the task note **as you go**, not just at wrap-up — during long debugging sessions especially, log each substantive step to the task note when it happens.

Vault: `~/git/lorite-obsidian-notes`. Dates are `yyyy-MM-dd`, times `HH:mm` (current local time — get it from the `time` tool or `date "+%H:%M"`).

## When to use
Log **as you work, not only at the end**: at the start of a work session (open/create today's diary note) and after each substantive exchange or finished piece of work.

## What a good entry is (the notes outlive the chat)
- **Written for a reader who didn't see the chat** — a future session (human or AI) must be able to resume from the note alone: outcome first, then decisions **with their why**, open threads, and next steps. Spell things out; no chat-local shorthand or unexplained codenames.
- **Grounded.** Log only outcomes backed by this session's actual tool output; anything unverified is logged as unverified ("fix applied, not yet tested in a fresh session"), never as done.
- **Reproducible.** The `Replicate manually` block (below) captures the exact commands.

## Write policy (never violate)
- The `ai_chats/diary/daily/` folder is **AI-writable** (explicit user grant) — diary notes may be created and appended freely.
- In **every other note**, only **append**, never rewrite hand-written content — and **where** the append goes is note-type-specific (see Part 2): **task notes** get a dated `### AI generated` entry inside their `# 📓 Journal / Work Log`; **all other notes** get a top-level `# AI Generated` section. Three task-note exceptions: **subtask checkboxes may be ticked** (`- [ ]` → `- [x]`) when the logged work verifiably completes them (box state only, never the item text); an **AI-owned `## High Level TODOs` subsection** at the end of `# 🎯 Task Description` may be freely maintained — add `- [ ]` (nestable), complete `- [ ]` → `- [x]`, and remove by striking `~~like this~~` (never delete the line), keeping the user's hand-written checklist separate (see Part 2); the **`status` frontmatter may be set** to todo / investigating / in-progress / blocked / pending-review / cancelled (never `done`) as the logged work changes the task's state; and when you set **`pending-review`**, **fill the `# ✅ Outcome & Learnings` subsections** (`## Outcome` / `## Learnings` / `## Next Steps`) by distilling the note's Journal — replacing their `- TODO` placeholders (see Part 2). Defer to the **`lorite-obsidian-note`** skill for the per-note append mechanics and the **`lorite-obsidian-markdown`** skill for syntax (wikilinks, callouts).
- **Inline-maintenance exception (user grant [[2026-07-31]]):** reference notes **wikilinked from the task note driving the current session** may additionally be kept factually current in their hand-written body — add a short sentence/bullet, or strike-and-replace an outdated fact with a date (`~~old~~ new ([[<yyyy-MM-dd>]])`), **never deleting or rewording** the original. Only facts verified by this session's tool output, and **every inline edit is logged in the task note's journal entry**. The AI also **maintains the linking itself**: an AI-owned `## Related notes` subsection in the task note lists the reference notes the task touches (found by keyword search over note names, `aliases:`, and `tags`). And when a verified thing has **no note at all**, the AI may **create** one anywhere in the vault — provided it first proves nothing covers it (names *and* aliases, whole vault), writes only what it verified, and stamps `ai_created: <yyyy-MM-dd>` in the frontmatter so the morning briefing surfaces it for the user's review. Full rules and exclusions in the `lorite-obsidian-note` skill's *Related-notes*, *Inline-maintenance*, and *Creation* exceptions.
- Never write secrets.

## Part 1 — the daily diary note (lightweight index)
Path: `ai_chats/diary/daily/AI Chat - <yyyy-MM-dd>.md`.
1. **Ensure it exists.** If not:
   - `mkdir -p ~/git/lorite-obsidian-notes/ai_chats/diary/daily` **first** — the Obsidian CLI
     `create` does not make parent folders (it errors "Folder already exists" only once the folder is
     present, and otherwise creates nothing).
   - `obsidian create path="ai_chats/diary/daily/AI Chat - <yyyy-MM-dd>.md" content="# 📓 Journal / Work Log\n"`
     (auto-adds `created`/`updated` frontmatter). There is **no `--help` flag** — `obsidian create
     --help` literally creates an `Untitled.md`; don't run it.
   - File-fallback (app down): write the file directly with a `# 📓 Journal / Work Log` header.
2. **Append a new entry at the END of the file** (newest last) under `# 📓 Journal / Work Log`:
   ```
   ## <HH:mm> — <one-line title>

   <2–4 sentence summary of what was done / decided>

   Detail → [[Linked Note A]] · [[Linked Note B]]
   ```
   Multi-line CLI `append` is flaky → **edit the file directly** to insert the entry (create-then-edit).

## Part 2 — full detail in each linked note
For every note wikilinked in the entry, file the same detail you gave the user in chat. **Where it lands depends on the note type** — defer to the `lorite-obsidian-note` skill for the exact mechanics:

- **Task notes** (`type: task`, in `tasks/`): the detail *is* a work-log entry, so it goes **inside the note's existing `# 📓 Journal / Work Log` section**, not in a separate top-level section. Add a dated entry **newest-first**, leaving existing entries intact:
  ```
  ## [[<yyyy-MM-dd>]]

  ### AI generated

  <full detail; link the diary with [[AI Chat - <yyyy-MM-dd>]] and wikilink liberally>
  ```
  **Ordering is strict and the opposite of the diary file: the most recent date heading is always at the TOP of the section, above all older ones.** Insert a new `## [[<date>]]` heading **immediately under the `# 📓 Journal / Work Log` header**, never at the end of the file. So a journal spanning two days reads top-to-bottom **newest → oldest** — e.g. `## [[2026-06-25]]` *above* `## [[2026-06-24]]`. If today's date heading already exists, just add your `### AI generated` entry under it (it's already on top). Demote any sub-headings in the detail to `####`+ so they nest under `### AI generated`. Use a **direct file edit** for this positioned insert — the CLI `append` only writes to the end of the file, which is the **wrong place here** (that is exactly the bug that puts a new date below older ones).
  - **Replicate manually (whenever the work ran commands).** Make the log *reproducible*, not just
    descriptive: add a `**Replicate manually:**` line followed by a fenced `bash` block with the
    **exact commands** the user can paste to reproduce the result — environment/setup (the venv, or
    `docker exec ros2_humble_dev zsh -c 'source …/setup.zsh && …'`), build/run/test commands, key
    file paths, and any `gh` / CLI calls, in order. **Redact secrets.** Omit only for pure
    prose/decision work that ran nothing.
  - **Embed the figures — a visual is the default, not a bonus.** The journal is how the user keeps up with AI work they did not watch, and how they show it to supervisors and stakeholders; a wall of prose fails at both. So **show the result, don't just claim it**. Mermaid diagrams go inline as a fenced ` ```mermaid ` block; image files (matplotlib `.pdf`/`.png`, screenshots, draw.io/Excalidraw exports) go in `attachments/ai_chats/` and are embedded with `![[…]]` + a caption. **Defer the mechanics** (folder, naming, wikilink vs inline, copying figures out of another repo) to the **`lorite-obsidian-note`** skill's *Images & diagrams* section — the same applies to the `# AI Generated` detail written into project/paper notes.
    - **These triggers mean a figure is expected, and its absence needs an excuse:** perception / detector / segmentation work → an **annotated frame** (mask, bbox, centroid overlay), for a good case *and* a failure case; a flight or trajectory → the **trajectory plot against ground truth**; calibration → the **residual / error figure**; an incident or crash → the **offending frame** plus a timeline; an eval or metric sweep → the **plot**, not only the table; a change to how components talk → a **mermaid** dataflow diagram; anything whose state is visible in RViz → a **screenshot**.
    - **Two or three figures beat one.** A good/bad pair, or before/after, carries more than any paragraph. Don't ration them.
    - **Get them cheaply — never render a forensics video just to have a picture.** Grab a frame from the perception node's debug overlay topic, screenshot RViz2 or PlotJuggler, or reuse what the analysis scripts in the robotics repo's `experiments/common/scripts/` already emit. If a figure costs a long render, log the note without it and say so.
    - **Write captions that stand alone**, because these get shared out of context: what it shows, the one number that matters, and which trial/date it came from — e.g. *"Mask overlay, hover06 +7.50 s: the in-mask depth median grabs the mat ~1 m behind the drone — the poisoned sample that caused crash 2."*
    - **If the work hit a trigger and you still have no figure, say why in one italic line** (`_No figure: the Orin was offline, nothing rendered._`). A silent omission reads as "there was nothing to see", which is usually false.
  - **Refresh the High Level TODOs (whenever the work changed the plan).** After writing the journal entry, bring the task note's AI-owned `## High Level TODOs` up to date so it always shows the *current* forward plan: create the subsection at the end of `# 🎯 Task Description` if it's missing, **add** `- [ ]` items for newly-surfaced work (nest with indentation), **complete** `- [ ]` → `- [x]` the ones this session verifiably finished (same evidence bar as ticking a subtask), and **strike** `~~like this~~` any that are now abandoned or superseded (never delete the line). This is the AI's own list — keep it separate from the user's hand-written checklist above it, and never migrate the user's subtasks into it. Journal = what happened (dated, append-only); High Level TODOs = what's left (living, rewritten). Use a **direct file edit** — the CLI `append` writes to the wrong place.
  - **Fill Outcome & Learnings (when the task reaches `pending-review`).** The moment you set `status: pending-review` — the task's deliverable is finished — write the note's `# ✅ Outcome & Learnings` section, whose three subsections ship as `- TODO` placeholders. **Synthesize them from this note's own `# 📓 Journal / Work Log`** (distill the accumulated record — don't re-derive the work or re-read the chat): **`## Outcome`** = what was delivered and the end state; **`## Learnings`** = the load-bearing findings, decisions + *why*, and gotchas worth carrying forward; **`## Next Steps`** = what remains / follow-ups (mirror the still-open `## High Level TODOs`). Same grounding bar as the journal — only claims backed by the journal/session output, unverified marked as such. **Replace the `- TODO` placeholder only**; if a subsection already has the user's hand-written text, append beneath it under an `_(AI generated)_` line — never overwrite the user's content. Add any missing section/subsection under the template's headings. Use a **direct file edit** for this positioned fill. This is the closing act of finishing a task: journal entry → status `pending-review` → Outcome & Learnings filled, all in the same wrap-up.

- **Any other note** (project note, paper literature note, etc.): append at the **END**:
  ```
  # AI Generated

  ## [[<yyyy-MM-dd>]] - [[AI Chat - <yyyy-MM-dd>]]

  <full detail: what was done, decisions, findings, exact numbers, next steps — wikilink liberally>
  ```
  If the note **already has** a `# AI Generated` H1, add **only** the `## [[<date>]] - [[AI Chat - <date>]]` subsection under it (don't duplicate the H1). For a brand-new `ai_chats/notes/` note, the detail can be the note body itself (use the `lorite-obsidian-note` skill's `ai_note` template) and the diary entry just links to it.

- **Diary = index; linked notes = full detail.** Don't put the long detail in the diary note; the linked note should stand on its own without re-reading the chat.

## Mechanism
CLI-first / file-fallback, exactly like `lorite-obsidian-note`: Obsidian CLI when the desktop app is running (use direct file edits for positioned inserts), direct file-write when it isn't.

## Output
Report: today's diary note path, the entry added, and which linked notes received a detail section (and via which mechanism). When the work ran commands, confirm the task-note entry includes a `Replicate manually` block capturing them.
