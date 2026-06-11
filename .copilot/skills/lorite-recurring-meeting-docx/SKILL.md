---
name: lorite-recurring-meeting-docx
description: Update (never recreate) the rolling Word file of a recurring meeting series — default the "1-1 Andrés - Alejandro" doc in OneDrive — by inserting a new dated meeting section that mirrors the most recent meeting's structure. Use when preparing the next 1-1/3-1 meeting agenda/notes in Word. Content gathering is vault-first (pairs with lorite-meeting-prep); editing is done live via the mcp-libre MCP server (LibreOffice must be open).
argument-hint: "date=<YYYY-MM-DD> [series=<folder name>] [topics=<what the meeting must decide>]"
---

# lorite-recurring-meeting-docx — update the rolling meeting Word file in place

Alejandro keeps **one rolling `.docx` per recurring meeting series** and types live notes into
it during the meeting. To prep the next meeting, **edit that file in place** — never generate a
new document, never overwrite the file wholesale, never touch past meeting sections.

## The files

Folder-per-series under `/home/lori/OneDrive/Documents/PhD project/`, docx named like the folder:

| Series | Path (quote it — spaces + accents) |
|---|---|
| **1-1 Andrés (default)** | `/home/lori/OneDrive/Documents/PhD project/1-1 Andrés - Alejandro/1-1 Andrés - Alejandro.docx` |
| 1-1 Rasmus | `/home/lori/OneDrive/Documents/PhD project/1-1 Rasmus - Alejandro/1-1 Rasmus - Alejandro.docx` |
| 3-1 NN-ITU | `/home/lori/OneDrive/Documents/PhD project/Alejandro's PhD project 3-1 meetings NN-ITU/Alejandro's PhD project 3-1 meetings NN-ITU.docx` |

Files ending in `-safeBackup-NNNN.docx` are OneDrive conflict artifacts — **never edit or delete**.

## Document anatomy (1-1 Andrés file, canonical example)

1. **TOC** (Word field — never hand-edit; the user refreshes it in Word).
2. `# Thesis objective` — short standing project description.
3. `# Timeline` — key hard dates; the user strikes through past ones himself. Add with a new line
   when a new hard date was agreed (deadline, midway date, stay start); and edit existing lines as needed.
4. `# 2026-MM-dd` — the **blank template section** (Status: Past / Present / Future + Actions).
   Leave it untouched; it marks the insertion point.
5. Dated meeting sections `# YYYY-MM-DD`, **newest first**, directly after the template section.

## Prerequisites

mcp-libre is installed and registered by `install.sh` in the dotfiles repo (handles cloning,
building the `.oxt`, Python 3.12 venv, and `claude mcp add`). If the `libreoffice` MCP server
is missing, re-run `install.sh`.

Each session, LibreOffice must be open with the document and the in-app MCP server started:

1. **Open the file**:
   ```bash
   xdg-open "/home/lori/OneDrive/Documents/PhD project/1-1 Andrés - Alejandro/1-1 Andrés - Alejandro.docx"
   ```
2. In LibreOffice: **Tools → MCP Server → Start MCP Server**.
3. **Verify**: `document(action="status")` returns success; `document(action="list")` shows the file.

## Procedure

1. **Read the document structure**: `structure(action="outline")` to get all headings with paragraph
   numbers; `document(action="content")` to read the full text. The **most recent dated section is
   the canonical format to mirror** — practices evolve, and the latest meeting reflects the current
   preference. (As of 2026-06-12 that is: `## Purpose` → `## Agenda` table (Min · Item · Decision
   sought) → one `##` section per numbered topic, each with `### Pre-meeting notes` (concise bullets)
   + `### Notes and decision` containing `- TODO` → an action-items section. If the latest section
   instead uses the older Status(Past/Present/Future)+Actions form, mirror that.)

2. **Gather content vault-first**: `lorite-meeting-prep` skill / Bases, the relevant project +
   task notes, and `ai_chats/diary/daily/` since the previous meeting. Pre-meeting bullets are
   *context to decide from*, 1–2 lines each; decisions stay as `- TODO` to be filled live.

3. **Back up** to `/tmp` before editing:
   ```bash
   cp "<file>.docx" "/tmp/$(date +%Y%m%d_%H%M%S)_backup.docx"
   ```
   Ask the user to close the file in Word/OneDrive sync first if possible.

4. **Find the insertion point**: use `search(action="find", query="2026-MM-dd")` to locate the
   template section heading and get its paragraph number. The new section goes **after** this
   template heading and **before** the previous newest meeting heading.

5. **Insert the new section**: 
   - `cursor(action="goto_paragraph", n=<template_para_n>)` to move to the template heading.
   - `cursor(action="context")` to confirm position.
   - `text(action="insert", content="\n<full new section text>")` to insert after the cursor.
     Build the content string with the complete new section (heading + subsections + bullets).

   > **Heading style note**: mcp-libre's `text` tool inserts at the current paragraph style and
   > does not expose a paragraph-style API. After insertion, run `structure(action="outline")` to
   > verify the new heading appears in the outline. If it does not, the heading paragraph is
   > missing Heading 1 style — tell the user to apply it manually in LibreOffice (click the
   > heading, select "Heading 1" from the Styles dropdown).

6. **Save**: `save(action="save")` — preserves the .docx format since the file was opened as docx.

7. **Validate**: re-run `structure(action="outline")` to confirm the new section appears at the
   right position between the template and the previous meeting. Report to the user.

8. **Log** the prep via `lorite-ai-chat-diary` (diary entry + detail in the meeting's vault notes).

## Style rules (user feedback, 2026-06-11)

- **No tab characters and no tab stops** — plain text only; dates/durations go in normal text.
- **No empty spacer paragraphs and no empty headings** — let the styles' spacing do the work.
- Simple tables only, matching the formatting already used in the doc.
- Concise: the file is read *during* the meeting; pre-meeting bullets are prompts, not prose.
- Never renumber, restyle, or "clean up" older sections — append-only mindset, like the vault.

## Gotchas

- The path contains spaces and accented characters (`Andrés`) — always quote, prefer absolute paths.
- OneDrive sync: if the file changes on disk mid-session (sync conflict), re-open it in LibreOffice
  rather than continuing to edit a stale in-memory copy.
- The TOC will show the new section only after the user refreshes fields in Word — say so in the
  hand-off message rather than trying to regenerate the TOC.
- LibreOffice must be running and the MCP server started before any tool calls; if
  `document(action="status")` fails, walk the user through the setup steps above.
