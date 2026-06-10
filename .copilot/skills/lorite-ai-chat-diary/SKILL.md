---
name: lorite-ai-chat-diary
description: Log the current work to the daily Obsidian AI-chat diary (ai_chats/diary/daily/AI Chat - yyyy-MM-dd) — a lightweight time-stamped entry with wikilinks — and write the full detail into each linked note under a "# AI Generated → ## [[date]] - [[AI Chat - date]]" section. The shared work-logging procedure used by lorite-obsidian-ai-brain, the pipeline agents, and the user.
argument-hint: "<short summary of what was done> + which notes to link (task / paper / project)"
---

# lorite-ai-chat-diary — log work to the daily AI-chat diary

The **single, canonical way** to record what was worked on, so any later session can reconstruct
context fast. Used by `lorite-obsidian-ai-brain`, every PhD-pipeline agent (`lorite-paper-scout`, `lorite-paper-reader`,
`lorite-task-manager`, `lorite-experiment-designer`, …), and the user directly. Two parts: a lightweight **diary
entry** (the index) and the **full detail in the linked note(s)**.

Vault: `~/git/lorite-obsidian-notes`. Dates are `yyyy-MM-dd`, times `HH:mm` (current local time — get
it from the `time` tool or `date "+%H:%M"`).

## When to use
Log **as you work, not only at the end**: at the start of a work session (open/create today's diary
note) and after each substantive exchange or finished piece of work.

## Write policy (never violate)
- The `ai_chats/diary/daily/` folder is **AI-writable** (explicit user grant) — diary notes may be
  created and appended freely.
- In **every other note**, only **append** under `# AI Generated`; never rewrite hand-written
  content. Defer to the **`lorite-obsidian-note`** skill for the per-note append mechanics and the
  **`lorite-obsidian-markdown`** skill for syntax (wikilinks, callouts).
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
For every note wikilinked in the entry (a task note, a paper's literature note, the project note),
append at the END the same detail you gave the user in chat:
```
# AI Generated

## [[<yyyy-MM-dd>]] - [[AI Chat - <yyyy-MM-dd>]]

<full detail: what was done, decisions, findings, exact numbers, next steps — wikilink liberally>
```
- If the note **already has** a `# AI Generated` H1, add **only** the
  `## [[<date>]] - [[AI Chat - <date>]]` subsection under it (don't duplicate the H1).
- For a brand-new `ai_brain/` note, the detail can be the note body itself (use the `lorite-obsidian-note`
  skill's `ai_brain` template) and the diary entry just links to it.
- **Diary = index; linked notes = full detail.** Don't put the long detail in the diary note; the
  linked note should stand on its own without re-reading the chat.

## Mechanism
CLI-first / file-fallback, exactly like `lorite-obsidian-note`: Obsidian CLI when the desktop app is running
(use direct file edits for positioned inserts), direct file-write when it isn't.

## Output
Report: today's diary note path, the entry added, and which linked notes received a detail section
(and via which mechanism).
