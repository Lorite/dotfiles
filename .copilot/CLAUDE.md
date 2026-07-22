# CLAUDE.md - Global Instructions

This file provides global instructions for Claude Code, OpenCode, and GitHub Copilot.

## Operating profile — Claude Opus 4.8 (calibrates every agent and skill here)

These agents and skills are tuned for **Claude Opus 4.8** (they degrade gracefully on other models). Opus 4.8 follows instructions literally, under-reaches for tools/subagents/memory unless told *when* to use them, narrates more, and asks more often than earlier models. The rules below calibrate that for how this workflow is meant to run: **the AI does the work; the user steers at decision points; the Obsidian vault keeps both able to resume.**

- **Human-in-the-loop, calibrated: ask at decision points, act between them.** For minor choices (naming, formatting, which of two equivalent approaches, read-only lookups, retry strategy), pick a reasonable option and note it — don't ask. Stop and confirm at the **named decision points**: the approval gates each agent defines (saving to Zotero, GitHub/calendar writes, paper edits, repo scaffolding, real hardware, anything destructive or outward-facing), scope changes, and genuine "which direction do we go" forks. When you stop, present a **concrete proposal with your recommendation first** — one batched confirmation beats a series of small asks.
- **The vault is your memory surface — read it before acting, write it as you go.** Treat the notes (see "Obsidian note sync" below) as **resumable state shared between the user and future AI sessions**: read the corresponding note first so you don't re-derive or redo; log findings, decisions *and the why behind them*, and exact replication commands via `lorite-ai-chat-diary` as you work — so a later session (human or AI) can continue exactly where this one stopped, or audit the process that was followed.
  - **Where detail goes (get this right — it's a common failure):** the **full detail always lives in the corresponding *task note* Journal** (`### AI generated` under `# 📓 Journal / Work Log`) — findings, decisions + why, numbers, commit hashes, replicate commands, next steps. The **daily AI-chat diary gets only a SHORT high-level entry** (2–4 sentences + `[[wikilinks]]` to the task notes) — it is an *index*, not the record. **Never dump long detail into the diary and leave the task note thin.** Log to the task note **as you go**, not just at wrap-up; if a chunk of work has no obvious task note, that's a signal to find/create one, not to pile detail into the diary.
- **Ground every progress claim in a tool result.** Before reporting that something is done, works, or passed, point to the output from this session that shows it; if it isn't verified yet, say so explicitly. This applies doubly to vault logs — the notes outlive the chat.
- **Capabilities have triggers, not vibes.** Each agent lists tools/skills/subagents with *when to use them*; when a listed condition matches, use that capability rather than working around it (read the note before acting; search vendor docs the moment a vendor component fails opaquely; route work to the matching `lorite-*` agent per the `/lorite` table; delegate to a subagent when work fans out across independent items).
- **Ground external facts with web search, not memory — but vault/repo first.** Before asserting a claim about the *outside* world — a vendor/hardware spec, a standard or API, a definition, a published statistic, what a cited paper says, or anything time-sensitive ("latest", "current") — **WebSearch/WebFetch an authoritative source and prefer it over training-data recall**, then link/cite it; if you can't confirm it, say so or mark `[VERIFY: …]` rather than assert it. This is a *trigger*, not a frequency dial: the vault, the repo, and papers already read stay the primary source — don't web-search what they already answer, and don't let a search replace reading your own notes. When a vendor/library component fails opaquely, go to its official docs + GitHub issues immediately rather than guessing.
- **Narration: brief signposts while working, a re-grounding summary at the end.** One line when you find something load-bearing or change direction; skip play-by-play. The final summary leads with the outcome and is written for a reader who didn't watch the session — the same standard as the vault log.
- **Full spec up front.** When handing work to a subagent, pass the complete task spec plus the corresponding vault note in the first message — don't drip-feed context across turns.

## Agents

Custom agents are located in `~/.claude/agents/`.

## Skills

Custom skills are located in `~/.claude/skills/`. These are automatically detected by Claude Code, OpenCode, and GitHub Copilot.

## Obsidian note sync (PhD-pipeline agents)

The Obsidian vault (`~/git/lorite-obsidian-notes`) is the running record of every task, paper, experiment, and project. Pipeline agents (`lorite-paper-scout`, `lorite-paper-reader`, `lorite-task-manager`, `lorite-experiment-designer`, `lorite-obsidian-ai-brain`, …) treat it as **both their first source of context and their running log** — read-first, log-often:

- **Read the corresponding note first.** Before acting, find and read the relevant vault note for the task / paper / experiment / project; it holds the latest human + AI context (status, decisions, prior findings). Locate it via the `lorite-obsidian-bases` skill (Bases) and `obsidian` CLI search. Don't re-derive context the note already has, and don't redo work it shows is already done. Use efficient CLI read patterns:
  - `obsidian outline path="..."` — structure before committing to a full `read`; the heading tree shows which section matters.
  - `obsidian search:context query="..." path="..."` — finds content and returns matching lines + context in one call; prefer over `search` (paths only) followed by `read`.
  - `obsidian property:read name=<field> path="..."` — single frontmatter field (e.g. `status`, `type`, `projects`) without reading the whole file.
- **Log to it frequently.** Record findings, decisions, and progress as you go (not only at the end) via the **`lorite-ai-chat-diary`** skill — it writes a dated entry in `ai_chats/diary/daily/AI Chat - <date>` and files the full detail in the linked note(s) where their type dictates (task notes → a dated `### AI generated` entry inside `# 📓 Journal / Work Log`; other notes → a `# AI Generated` section), on top of the `lorite-obsidian-note` safe-write policy (`ai_chats/`-only writes; elsewhere append-only, never rewriting hand-written content — with four task-note exceptions: **subtask checkboxes may be ticked** when the work is verifiably done (box only, never the item text); an **AI-owned `## High Level TODOs` subsection** at the end of `# 🎯 Task Description` may be freely maintained (add / complete / strike-through `~~removed~~` its own items — kept separate from the user's hand-written checklist, holding the living forward plan vs. the Journal's dated history); the **`status` frontmatter may be set** to todo / investigating / in-progress / blocked / **pending-review** / cancelled as the work state changes — `pending-review` when the deliverable is finished and awaits the user's review; **never `done`**, that's the user's call; and when `pending-review` is set, the **`# ✅ Outcome & Learnings` subsections** (`## Outcome` / `## Learnings` / `## Next Steps`) are **filled from the note's Journal**, replacing their `- TODO` placeholders (the closing act of finishing a task). Evidence logged either way).
- **"Corresponding note"**, in order: the task note (`tasks/`, `type: task`) driving the work; else the paper's literature note; else the project note (e.g. the Conference Paper project). When unsure, ask, or default to an `ai_chats/notes/` note that wikilinks to the others.

## Git

- Default to feature branches instead of committing directly to main/master — unless the repo's own `CLAUDE.md`/`AGENTS.md` says otherwise (e.g. the dotfiles and paper repos commit directly to `main`)
- Use conventional commit messages: `type(scope): description`
- Run lint/typecheck before committing when available

## Parallel subagent limits (critical)

**Never spawn more than **3** `task` / `Agent` subagents in parallel.** The engine silently drops or rejects excess concurrent spawns — all of them fail with zero output, wasting your time and context window. When a task naturally decomposes into a large batch (e.g. "process 400 articles"), always do it **sequentially** or with at most **2–3 concurrent batches**. If a single subagent can handle the work inline, prefer that over parallelism.

## Code Style

- Use 4-space indentation for shell scripts
- Follow existing project conventions

### Prose in source files (README, LaTeX, Markdown, docs)

- Never hard-wrap a sentence across multiple source lines ("semantic line breaks" / one-sentence-per-line style). Write one line per paragraph and let it soft-wrap; do not insert manual newlines mid-sentence.
