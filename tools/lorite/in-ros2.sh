#!/usr/bin/env bash
# in-ros2.sh — run a command inside the ROS 2 Humble dev container, from the host.
#
# Why this exists: Claude Code / the editor run on the HOST so they can reach the
# Obsidian vault, the dotfiles, and the bind-mounted repo source all at once. The
# ROS 2 toolchain (colcon, ros2, gz, simulators) only exists INSIDE the Dev
# Container. Because the repo is bind-mounted (..:/workspaces/lorite_ros2_humble_phd
# in .devcontainer/docker-compose.yml), edits made on the host are already visible
# inside the container — this wrapper is only for *running* container-side tools.
#
# Usage:
#   in-ros2.sh                                   # interactive login shell in the container
#   in-ros2.sh ros2 topic list                   # run a single command
#   in-ros2.sh zsh -lc 'source /opt/ros/humble/setup.zsh \
#                       && source ros2_ws/install/setup.zsh \
#                       && colcon build --symlink-install --packages-select <pkg>'
#
# Overrides (env):
#   ROS2_WS_DIR     host path of the repo   (default: ~/git/lorite_ros2_humble_phd)
#   ROS2_CONTAINER  compose container_name  (default: ros2_humble_dev)
set -euo pipefail

WS="${ROS2_WS_DIR:-$HOME/git/lorite_ros2_humble_phd}"
CONTAINER="${ROS2_CONTAINER:-ros2_humble_dev}"   # container_name in docker-compose.yml
WORKDIR="/workspaces/$(basename "$WS")"           # bind-mount target inside the container

# No args → open an interactive login shell.
[ "$#" -eq 0 ] && set -- zsh -l

# Fast path: the compose service is long-running with a fixed name. If it's up,
# `docker exec` is near-instant and skips the devcontainer-CLI / node startup cost.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
    tty_flags=(-i)
    [ -t 0 ] && [ -t 1 ] && tty_flags+=(-t)
    exec docker exec "${tty_flags[@]}" -u vscode -w "$WORKDIR" "$CONTAINER" "$@"
fi

# Slow path: container not running → bring the Dev Container up (idempotent) and
# exec through the CLI, which resolves the service from .devcontainer/.
if ! command -v devcontainer >/dev/null 2>&1; then
    echo "in-ros2.sh: container '$CONTAINER' is not running and the devcontainer CLI is not on PATH." >&2
    echo "  Start the Dev Container in VS Code, or install the CLI: npm i -g @devcontainers/cli" >&2
    exit 1
fi
devcontainer up --workspace-folder "$WS" >/dev/null
exec devcontainer exec --workspace-folder "$WS" "$@"
