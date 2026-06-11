#!/usr/bin/env bash
# in-tex.sh — run a command inside the CLAWAR LaTeX (texlive) dev container, from the host.
#
# Same rationale as in-ros2.sh: the editor / Claude Code live on the HOST (to reach
# the Obsidian vault + dotfiles), while the texlive toolchain (latexmk, biber) lives
# inside the Dev Container. The paper repo is bind-mounted by the Dev Container, so
# .tex/.bib edits made on the host are already visible inside — this wrapper only
# *runs* the container-side build tools.
#
# Usage:
#   in-tex.sh                                                  # interactive login shell
#   in-tex.sh latexmk -pdf -interaction=nonstopmode main.tex   # build the PDF
#   in-tex.sh latexmk -C                                       # clean aux files
#
# Override the workspace with TEX_WS_DIR=/path/to/paper.
#
# Note: CLAWAR's Dev Container is a build-type container (no fixed container_name),
# so this always goes through the devcontainer CLI, which finds / builds / starts it
# as needed. The first run after a clean checkout may build the image (slow once).
set -euo pipefail

WS="${TEX_WS_DIR:-$HOME/git/Drone-localization-support-from-a-quadruped-robot-CLAWAR-2026-}"

# No args → open an interactive login shell.
[ "$#" -eq 0 ] && set -- bash -l

if ! command -v devcontainer >/dev/null 2>&1; then
    echo "in-tex.sh: the devcontainer CLI is not on PATH." >&2
    echo "  Install it with: npm i -g @devcontainers/cli" >&2
    exit 1
fi
devcontainer up --workspace-folder "$WS" >/dev/null
exec devcontainer exec --workspace-folder "$WS" "$@"
