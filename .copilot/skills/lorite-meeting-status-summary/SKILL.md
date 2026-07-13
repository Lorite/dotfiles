---
name: lorite-meeting-status-summary
description: Create a meeting update in Past/Present/Future + Actions format by combining Google Calendar context (date range + attendees) with vault info (Bases first, then Obsidian CLI search).
argument-hint: "meeting=<title or id> start=<YYYY-MM-DD> end=<YYYY-MM-DD>"
---

# Meeting Status Summary

## What this skill does

Creates a structured status update for a specified meeting interval:

- **Status**
  - Past: bullet points of what happened since the last meeting
  - Present: bullet points of what is currently in progress
  - Future: bullet points of what will happen next
- **Actions**
  - action bullet points (owner if known)

Output must use exactly these Markdown headers:

- `## Status`
- `### Past`
- `### Present`
- `### Future`
- `## Actions`

## Inputs

You may get the date range in one of these ways:

1. Preferred: use Google Calendar (MCP) to resolve meeting title/id and determine `start` and `end` boundaries.
2. If not available: use the `start`/`end` arguments provided by the user.

Notes from real usage:
- Google Calendar MCP may be unavailable (expired auth tokens). This skill should still work using vault evidence only.
- Obsidian CLI `base:views` / `base:query` operate on the *currently active base file* in Obsidian. In practice, passing `file=` did not select the base; you must `obsidian open path="bases/<BASE>.base"` first.

## Procedure (Obsidian-first)

1. Resolve meeting dates
   - If Google Calendar access is available: fetch the meeting event and compute the interval (last meeting → next meeting).
   - Otherwise, use the user-provided `start` and `end` dates.

  If Google Calendar fails (auth/error), skip it and proceed with Bases + search.

2. Identify stakeholders
   - From calendar attendees (if available), map people to notes in `people/`.
   - If no attendees are available, ask the user for stakeholder names.

3. Collect vault evidence (Bases first)
   - Prefer querying existing Bases with Obsidian CLI:
     - Open the base file first (required):
       - `obsidian open path="bases/MEETINGS.base" newtab`
       - `obsidian base:views`
       - `obsidian base:query view="Recent Meetings" format=md`
     - For calendar events:
       - `obsidian open path="bases/CALENDAR EVENTS.base" newtab`
       - `obsidian base:views`
       - `obsidian base:query view="Calendar events" format=tsv | grep -i "andres" | head`
     - Any task base you already use (for example tasknotes-related bases).
   - If a needed slice is not available via Bases, propose a Base improvement/new Base.

   Practical pattern for “last meetings with X (1-1s)” without Google Calendar:
   - Use `MEETINGS.base` to identify the meeting rows (date + title).
   - Then locate the corresponding note(s) under `calendar_events/` (or wherever you store event notes):
     - `obsidian search query="<YYYY-MM-DD> 1-1 <Name>" path="calendar_events"`
     - `obsidian read path="calendar_events/<matched file>.md"`

4. Fill gaps with Obsidian CLI search
   - Use constrained searches:
     - `obsidian search query="..." path="tasks"`
     - `obsidian search query="..." path="work"`
     - `obsidian search query="..." path="diary"`

5. Write output into `ai_chats/notes/`
   - Create a new AI note using the `ai_note` template and append the meeting summary.
   - File naming:
     - `ai_chats/notes/YYYY-MM-DD Meeting Summary - <Meeting Title>.md`

   Implementation tip (CLI ergonomics):
   - Multi-line `obsidian append ... content="..."` can be fragile due to shell quoting and special characters.
   - Prefer either:
     - Appending smaller chunks, or
     - Editing the file directly (agent/tool) after creation to insert the summary under `## AI Generated Answer`.

## Output format (required)

```
## Status
### Past
- ...

### Present
- ...

### Future
- ...

## Actions
- ...
```

## Notes

- Never modify notes outside `ai_chats/`.
- If you must write outside `ai_chats/`, append under `AI Generated` with `## Prompt` and `## AI Generated Answer` only.
- Do not include secrets (avoid copying anything from `obsidian-web-clipper-settings.json`).

## Troubleshooting

- If Bases commands say “Active file is not a base file …”:
  - Run `obsidian open path="bases/<BASE>.base" newtab` and retry `obsidian base:views` / `obsidian base:query`.
- If Obsidian CLI commands behave inconsistently:
  - Ensure the Obsidian desktop app is running with this vault open.
