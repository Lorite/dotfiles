# CLAUDE.md - Global Instructions

This file provides global instructions for Claude Code, OpenCode, and GitHub Copilot.

## Agents

Custom agents are located in `~/.claude/agents/`. These agents are symlinked to `~/.config/opencode/agents/` for OpenCode compatibility.

## Skills

Custom skills are located in `~/.claude/skills/`. These are automatically detected by Claude Code, OpenCode, and GitHub Copilot.

## Git

- Always create feature branches instead of committing directly to main/master
- Use conventional commit messages: `type(scope): description`
- Run lint/typecheck before committing when available

## Code Style

- Use 4-space indentation for shell scripts
- Keep lines under 120 characters
- Follow existing project conventions
