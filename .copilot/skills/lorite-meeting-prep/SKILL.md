---
name: lorite-meeting-prep
description: Prepare for a meeting by collecting recent work updates and tasks between previous/next meeting dates (Calendar if available) using Bases first (recently edited/created work notes).
argument-hint: "meeting=<title or id> start=<YYYY-MM-DD> end=<YYYY-MM-DD>"
---

# Meeting Prep

## What this skill does

Creates a meeting preparation note for either:

- A one-off meeting (explicit `start`/`end` interval), or
- A recurring meeting series (prefer Calendar to compute previous → next meeting bounds).

It surfaces what you’ve been working on recently / since the last meeting using vault evidence:

- Base: `NOTES RECENTLY MODIFIED` → view `Recently Edited Work Notes`
- Base: `NOTES RECENTLY CREATED` → view `Recently Created Work Notes`

Output must use exactly these Markdown headers:

- `## Context`
- `## Updates Since Last Meeting`
- `## Proposed Agenda`
- `## Questions / Asks`
- `## Links`

## Inputs

You may get the date range in one of these ways:

1. Preferred: use Google Calendar (MCP) to resolve the meeting title/id and determine the interval (previous meeting → next meeting).
2. If Calendar is not available: use the `start`/`end` arguments provided by the user.

Notes from real usage:
- Google Calendar MCP may be unavailable (expired auth tokens). This skill must still work using vault evidence only.
- Obsidian CLI `base:views` / `base:query` operate on the *currently active base file*.
  - In practice, you must `obsidian open path="bases/<BASE>.base"` before running `obsidian base:views` / `obsidian base:query`.

## Procedure (Obsidian-first)

1. Resolve meeting interval
   - If Calendar is available:
     - Locate the meeting event by title/id.
     - Determine the relevant interval:
       - Recurring series: previous occurrence end → next occurrence start (or previous start → current start).
       - One-off: use that event’s start/end as the interval.
   - If Calendar fails:
     - Require `start` and `end` from the user.

2. Identify stakeholders (optional)
   - If Calendar attendees are available, list key attendees.
   - If the meeting is part of a recurring series, also look at the attendees of the previous meeting occurrence.
   - Map attendees to notes in `people/` if possible (e.g. by name) to get more context on their recent work.
   - If not, proceed without stakeholder mapping.

3. Collect vault evidence (Bases first)

   Primary evidence: recently edited work notes.

   - Recently edited work notes:
     - `obsidian open path="bases/NOTES RECENTLY MODIFIED.base" newtab`
     - `obsidian base:views`
     - `obsidian base:query view="Recently Edited Work Notes" format=tsv`
     - If output is too long, sample the most recent rows:
       - `... | head`

   Secondary evidence: recently created work notes.

   - Recently created work notes:
     - `obsidian open path="bases/NOTES RECENTLY CREATED.base" newtab`
     - `obsidian base:views`
     - `obsidian base:query view="Recently Created Work Notes" format=tsv`
     - If output is too long, sample the most recent rows:
       - `... | head`

   If you need strict interval filtering:
   - Prefer `format=json` and filter by the `updated`/`created` column in a script (e.g. `jq`/Python).
   - If JSON isn’t available, do a best-effort approach:
     - Use the Bases’ natural recency ordering plus keyword filtering.
     - Then open the most relevant notes and confirm timestamps/content.

4. Create the meeting prep note in `ai_brain/`

   - Create a new AI Brain note using the `ai_brain` template:
     - `obsidian create path="ai_brain/YYYY-MM-DD AI Brain - Meeting Prep - <Meeting Title>.md" template=ai_brain`

   - Think about what is important for the meeting by reading the previous meeting notes (if available), the stakeholders involved, and the recent updates you found in the vault. Populate the note with:

     - `## Context`
       - Meeting title + date range
       - Attendees (if available)

     - `## Updates Since Last Meeting`
       - Bullets summarizing work done since last meeting.
       - Link to source notes (as wikilinks).

     - `## Proposed Agenda`
       - Agenda bullets derived from the updates.

     - `## Questions / Asks`
       - Specific questions you want answered.
       - Decisions needed.
       - Requests from stakeholders.

     - `## Links`
       - Links to the most relevant notes.
       - Any relevant tasks/PRs/docs (as wikilinks).

   Implementation tip (CLI ergonomics):
   - Multi-line `obsidian append ... content="..."` can be fragile due to shell quoting.
   - Prefer smaller appends, or create the note then edit it directly if needed.

## Troubleshooting

- If Bases commands say “Active file is not a base file …”:
  - Run `obsidian open path="bases/<BASE>.base" newtab` and retry `obsidian base:views` / `obsidian base:query`.
- If Obsidian CLI commands fail:
  - Ensure the Obsidian desktop app is running with this vault open.

## Notes

- Never modify notes outside `ai_brain/`.
- If you must write outside `ai_brain/` (rare), append under `# AI Generated` with `## Prompt` and `## AI Generated Answer` only.
- Do not include secrets (avoid copying anything from `obsidian-web-clipper-settings.json`).
