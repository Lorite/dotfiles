#!/usr/bin/env bash
# Canonical copy of the on-demand headless-Obsidian wrapper.
# Lives on the always-on server at ~/.local/bin/with-headless-obsidian.sh.
#
# Runs a command with a working Obsidian CLI available, WITHOUT keeping Obsidian
# running 24/7 (which would fight the laptop's live instance over the
# Syncthing-synced .obsidian/ state — workspace.json, plugin data.json — and
# spew .sync-conflict files). Instead it is "on-demand per run":
#
#   * If the Obsidian CLI is ALREADY responsive (e.g. run on the laptop where
#     the GUI app is up, or a concurrent wrapper already started it), it just
#     runs the command and manages nothing.
#   * Otherwise it launches Obsidian headlessly under Xvfb, waits for the CLI
#     socket to answer, runs the command, and stops the instance it started.
#
# This is what lets the server's pipeline steps (obsidian_daily_note.py,
# refresh-stt + Media DB creation, morning briefing, …) use the real in-app
# tooling — Virtual Linker, Bases, the Media DB API — instead of the file-only
# fallback. See CLAUDE.md -> "On-the-go access (home server)" and the task note
# "Set up headless Obsidian on the home server for the pipeline".
#
# Prereqs on the server (one-time): the `obsidian` CLI binary in ~/.local/bin,
# and "cli":true in ~/.config/obsidian/obsidian.json (the built-in CLI toggle,
# global/per-machine — not synced from the laptop).
#
# Usage:
#   with-headless-obsidian.sh <command> [args...]
#   with-headless-obsidian.sh obsidian eval code='app.vault.getName()'
#
# Env knobs:
#   OBSIDIAN_BIN        Obsidian binary            (default /opt/Obsidian/obsidian)
#   OBS_READY_TIMEOUT   seconds to wait for the CLI (default 90)
set -u

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PATH="$HOME/.local/bin:$PATH"

OBS_BIN="${OBSIDIAN_BIN:-/opt/Obsidian/obsidian}"
CLI="$HOME/.local/bin/obsidian"
LOG="$HOME/.cache/headless-obsidian.log"
READY_TIMEOUT="${OBS_READY_TIMEOUT:-90}"
SELF=$$

cli_ready() { "$CLI" eval code='1' >/dev/null 2>&1; }

# Already up? Just run — don't touch a lifecycle we didn't create.
if cli_ready; then
    exec "$@"
fi

# No way to launch a headless display → just run the command; anything that needs
# Obsidian degrades to its own file-only fallback (e.g. refresh-stt inserts plain
# lines and skips enrichment). This keeps the wrapper safe to put in front of a
# command on ANY host, including a laptop without Xvfb where Obsidian is closed.
if ! command -v xvfb-run >/dev/null 2>&1; then
    echo "with-headless-obsidian: xvfb-run not installed — running without headless Obsidian" >&2
    exec "$@"
fi

mkdir -p "$(dirname "$LOG")"
# Clear stale Electron singletons that block a restart after a crash.
rm -f "$HOME/.config/obsidian/SingletonLock" \
      "$HOME/.config/obsidian/SingletonSocket" \
      "$HOME/.config/obsidian/SingletonCookie" 2>/dev/null

# Launch detached, in its own Xvfb display. --no-sandbox --disable-gpu
# --disable-software-rasterizer are required for Electron under Xvfb.
setsid bash -c "exec xvfb-run -a '$OBS_BIN' --no-sandbox --disable-gpu \
    --disable-software-rasterizer --disable-gpu-compositing --disable-dev-shm-usage" \
    >"$LOG" 2>&1 &

# Stop exactly what we started, on any exit. Match Obsidian by its binary path
# (never `pkill -f Xvfb/obsidian` — that also matches THIS script's own shell
# and would kill us; use pgrep+PID excluding $SELF, and `pkill -x Xvfb` which
# matches the process *name* only, not our cmdline).
cleanup() {
    local pids
    pids=$(pgrep -f "$OBS_BIN" | grep -vw "$SELF")
    [ -n "$pids" ] && kill -TERM $pids 2>/dev/null
    for _ in 1 2 3 4 5; do
        pgrep -f "$OBS_BIN" | grep -vqw "$SELF" || break
        sleep 1
    done
    pids=$(pgrep -f "$OBS_BIN" | grep -vw "$SELF")
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null
    pkill -x Xvfb 2>/dev/null
}
trap cleanup EXIT INT TERM

# Wait for the CLI to answer.
ready=0
for _ in $(seq 1 "$READY_TIMEOUT"); do
    if cli_ready; then ready=1; break; fi
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    # Couldn't bring Obsidian up — run anyway (the command degrades to file-only),
    # rather than failing the whole timer run. cleanup() still stops any partial start.
    echo "with-headless-obsidian: Obsidian not ready in ${READY_TIMEOUT}s — running command degraded; last log:" >&2
    tail -n 20 "$LOG" >&2
fi

"$@"
