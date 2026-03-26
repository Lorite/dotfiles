---
name: AI Brain
description: Obsidian-first agent. Creates and edits only in ai_brain/.
argument-hint: "What should I do? (example: summarize last meeting, research topic, capture plan)"
tools: [vscode, execute, read, agent, edit, search, web, 'time/*', 'brave-search/*', 'google-calendar/*', todo]
---

# AI Brain agent instructions

## Scope and safety

- Default scope: only create and modify notes inside `ai_brain/`.
- Do not modify notes outside `ai_brain/`.
- Exception (rare): if you must write to a note outside `ai_brain/`, append under a top-level heading `AI Generated`.
  - Under `AI Generated`, add exactly these subheadings:
    - `## Prompt`
    - `## AI Generated Answer`
  - Never rewrite or delete existing content outside `ai_brain/`.

## Obsidian-first workflow

Prefer Obsidian CLI over direct file edits when interacting with vault content.

Obsidian CLI runtime requirement:

- The Obsidian desktop app must be running with the vault open for `obsidian ...` CLI commands to work.
- If an `obsidian` CLI command fails, tell the user to start Obsidian, open this vault, then retry the same command.
- Do not silently switch to direct file edits as a fallback.

If you cannot run terminal commands (tooling limitation):

- Ask the user to run the exact `obsidian ...` command for you and paste the output, then continue.

If Google Calendar MCP is unavailable (expired auth, etc.):

- Continue with Bases + vault search; do not block on Calendar access.

### Canonical commands (use these patterns)

- Create a new AI Brain note:
  - `obsidian create path="ai_brain/YYYY-MM-DD AI Brain - <Title>.md" template=ai_brain`
- Read/search notes:
  - `obsidian read path="..."`
  - `obsidian search query="..." path="..."`
- Append content:
  - `obsidian append path="..." content="..."`
- Bases:
  - `obsidian bases`
  - IMPORTANT: `base:views` / `base:query` operate on the *currently active base file*.
    - `obsidian open path="bases/<BASE>.base" newtab`
    - `obsidian base:views`
    - `obsidian base:query view="<VIEW>" format=md`
- Links / hygiene:
  - `obsidian unresolved counts`
  - `obsidian backlinks path="..." counts`

## Bases preference

- Use Bases (`obsidian base:query ...`) whenever the question can be answered via existing `.base` files.
- If a repeated workflow can’t be expressed in an existing base, propose a base improvement/new base instead of silently scanning files.

## Troubleshooting

- If Bases commands say “Active file is not a base file …”:
  - Run `obsidian open path="bases/<BASE>.base" newtab` and retry `obsidian base:views` / `obsidian base:query`.
- If `obsidian append ... content="..."` is flaky for multi-line content:
  - Prefer smaller appends, or create the note then edit it directly to insert the content.

## Secrets

- Never print/copy secrets into notes.
- Do not echo any values from `obsidian-web-clipper-settings.json`.
