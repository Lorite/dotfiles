# CLAUDE.md - Global Instructions

This file provides global instructions for Claude Code, OpenCode, and GitHub Copilot.

## Agents

Custom agents are located in `~/.claude/agents/`.

## Skills

Custom skills are located in `~/.claude/skills/`. These are automatically detected by Claude Code, OpenCode, and GitHub Copilot.

## Obsidian note sync (PhD-pipeline agents)

The Obsidian vault (`~/git/lorite-obsidian-notes`) is the running record of every task, paper,
experiment, and project. Pipeline agents (`paper-scout`, `paper-reader`, `task-manager`,
`experiment-designer`, `ai-brain`, …) treat it as **both their first source of context and their
running log** — read-first, log-often:

- **Read the corresponding note first.** Before acting, find and read the relevant vault note for the
  task / paper / experiment / project; it holds the latest human + AI context (status, decisions,
  prior findings). Locate it via the `obsidian-bases` skill (Bases) and `obsidian` CLI search. Don't
  re-derive context the note already has, and don't redo work it shows is already done.
- **Log to it frequently.** Write findings, shortlists, decisions, and progress back as you go (not
  only at the very end) via the **`obsidian-note`** skill — the canonical safe-write procedure
  (`ai_brain/`-only writes; elsewhere append under `# AI Generated`, or a task-note journal
  `### AI generated` entry; never rewrite hand-written content).
- **"Corresponding note"**, in order: the task note (`tasks/`, `type: task`) driving the work; else
  the paper's literature note; else the project note (e.g. the Conference Paper project). When
  unsure, ask, or default to an `ai_brain/` note that wikilinks to the others.

## Git

- Always create feature branches instead of committing directly to main/master
- Use conventional commit messages: `type(scope): description`
- Run lint/typecheck before committing when available

## Code Style

- Use 4-space indentation for shell scripts
- Keep lines under 120 characters
- Follow existing project conventions
