---
name: lorite-meeting-prep
description: Stage 1 of the meeting workflow — gather recent work updates/tasks (Bases-first, Calendar if available) AND author the structured Obsidian meeting note (Purpose + agenda table + per-item sections with ^prep ids + scaffolded # Meeting Notes embeds) that the slidev deck reads. Use to prepare a recurring or one-off PhD meeting.
argument-hint: "meeting=<title or id> [start=<YYYY-MM-DD> end=<YYYY-MM-DD>]"
---

# Meeting Prep — author the structured meeting note (stage 1)

## What this skill does
Prepares a meeting by (a) gathering what you've worked on since the last meeting from vault evidence, then (b) **writing the structured meeting note** that is the single **source of truth** for the deck.

> **Pipeline:** this is **step 1** — author/structure the Obsidian meeting note. The user then edits
> it by hand, and it feeds **`lorite-slidev-meeting-deck`** (step 2, note → slides → PDF). Author the
> note in *exactly* the shape step 2 reads (below), so the deck maps 1:1 onto it.

## Inputs
Resolve the meeting interval one of two ways:
1. Preferred: Google Calendar (MCP) — resolve the title/id and the interval (previous occurrence → next, for a recurring series; or the event's own start/end for a one-off).
2. Fallback (Calendar auth often expires): the `start`/`end` arguments. The skill must still work from vault evidence alone.

## Procedure (Obsidian-first)

1. **Resolve the interval** (Calendar, else `start`/`end`).

2. **Identify stakeholders** (optional): Calendar attendees + the previous occurrence's attendees; map to `people/` notes for context where possible.

3. **Collect vault evidence (Bases first).** The Obsidian CLI base commands act on the *active* base file, so `obsidian open path="bases/<BASE>.base" newtab` before querying.
   - Recently edited work notes: `bases/NOTES RECENTLY MODIFIED.base` → view `Recently Edited Work Notes`.
   - Recently created work notes: `bases/NOTES RECENTLY CREATED.base` → view `Recently Created Work Notes`.
   - `obsidian base:query view="<view>" format=tsv` (or `format=json` + filter by `updated`/`created`
     for strict interval filtering). Then open the most relevant notes to confirm content/timestamps.
   - Also read the **previous meeting note** and any **paper repo(s)** being reported (real numbers,
     not approximations).

4. **Write the structured meeting note** (the source of truth for step 2). The note normally already exists in `calendar_events/<date> <title>.md` (created by the calendar sync: `type: calendar_event`, with template sections `# Details` / `# Description` / `# Pre-meeting Tasks and Notes` / `# Meeting Notes` / `# Other Notes` / `# LLM Summary` / `# Tasks`). Fill it **in place**; if it doesn't exist, create it from the meeting template first.

   Fill `# Pre-meeting Tasks and Notes` in exactly this shape:

   ```markdown
   %% Agenda for <meeting> on [[<date>]]. Source: vault evidence since the last meeting + <links>. %%

   - **Purpose:** <one line — what this meeting must produce>.

   | # | Item | Goal / decision sought |
   |---|---|---|
   | 1 | <Agenda item> | <what you want from it> |
   | 2 | <Agenda item> 👥💬 | <discussion → feedback sought> |
   | … | … | … |

   ### 1. <Agenda item>
   - **Goal / decision sought:** <…> ^prep1
   - Pre-meeting notes:
       - <bullet grounded in the vault evidence / previous meeting / paper repo>

   ### 2. <Agenda item> 👥💬
   - **Goal / decision sought:** <…> ^prep2
   - Pre-meeting notes:
       - <bullet>
   ```

   - **One `^prepN` per agenda item** (on the Goal/decision-sought line) — step 2 makes one
     `layout: agenda` deck section per item.
   - Mark discussion items with **👥💬** in the table and the heading; step 2 carries it onto the slide.

   Then scaffold `# Meeting Notes` (one embed per item, filled live during the meeting):

   ```markdown
   ![[#^prep1]]
   - TODO outcome.

   ![[#^prep2]]
   - TODO outcome.
   ```

   Optionally seed `# Tasks` with carried-over actions (TaskNotes `- [ ]` checkboxes; wikilink the `[[#^prepN]]` they came from).

   Mechanics: use the **`lorite-obsidian-note`** skill (Obsidian CLI when the app is up, file-write fallback). Multi-line CLI `append` is fragile → create/edit the file directly for these blocks.

## Write policy
- The **meeting note is the sanctioned exception** to the AI "ai_brain-only" rule: fill its `# Pre-meeting Tasks and Notes` and scaffold `# Meeting Notes` directly (the note template's `%%` comment invites it). **Never** rewrite the user's hand-written outcomes, `# Other Notes`, or other sections; never touch other notes outside `ai_brain/`.
- No secrets (never copy from `obsidian-web-clipper-settings.json` etc.).

## Troubleshooting
- "Active file is not a base file …" → `obsidian open path="bases/<BASE>.base" newtab`, then retry.
- Obsidian CLI failing → ensure the desktop app is running with this vault open.
- Calendar MCP unavailable (expired tokens) → fall back to `start`/`end` + vault evidence.
