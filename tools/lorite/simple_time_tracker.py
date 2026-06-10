#!/usr/bin/env python3
"""
simple_time_tracker.py — start/stop a *live* SimpleTimeTracker activity from the CLI.

Companion to the vault's ``scripts/daily_time_tracker.py`` (which is *retrospective*:
an LLM buckets a whole day's git+Obsidian activity into finished blocks and POSTs them
as ``add_action``). This script is *prospective*: it tells the phone to start a running
activity now, so a chat/work session is timed live, then stops it at the end.

Both talk to the same **Android Automate webhook** over HTTP POST + JSON. The webhook URL
is read from (in order):

  1. ``$AUTOMATE_WEBHOOK_URL``
  2. ``<vault>/.secrets/automate_webhook_url.txt`` — the canonical location the vault
     script already uses. The vault is ``$LORITE_VAULT`` / ``$OBSIDIAN_VAULT`` or the
     default ``~/git/lorite-obsidian-notes``.

The URL is a secret and is **never printed** (not even in --dry-run / errors).

Payloads (the Automate flow must branch on the ``payload`` discriminator — ``add_action``
is the existing finished-block case; this script adds two live cases):

  start:  {"payload": "start_action", "activity": "Task",
           "comment": "<task note name>", "start": "<ISO 8601 local>"}
  stop:   {"payload": "stop_action", "end": "<ISO 8601 local>"}

When ``activity`` is ``"Task"`` the ``comment`` is the task-note name (the vault renders it
as a ``[[wikilink]]``), matching the convention in ``daily_time_tracker.py``.

Usage:
  simple_time_tracker.py start --comment "Implement experiment-coder agent"
  simple_time_tracker.py start --activity Coding --comment "dotfiles agents"
  simple_time_tracker.py stop
  simple_time_tracker.py start --comment "..." --dry-run   # print payload, send nothing

Exit codes: 0 success · 2 config/usage error · 3 webhook/HTTP error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_VAULT = Path.home() / "git" / "lorite-obsidian-notes"
WEBHOOK_SECRET_RELPATH = Path(".secrets") / "automate_webhook_url.txt"
REQUEST_TIMEOUT_SEC = 15


def _err(msg: str) -> None:
    """Print to stderr without leaking the webhook URL."""
    print(f"simple_time_tracker: {msg}", file=sys.stderr)


def resolve_webhook_url() -> str:
    """Return the Automate webhook URL from env or the vault secret file.

    Raises SystemExit(2) with a helpful (secret-free) message if it can't be found.
    """
    env_url = os.environ.get("AUTOMATE_WEBHOOK_URL", "").strip()
    if env_url:
        return env_url

    vault = os.environ.get("LORITE_VAULT") or os.environ.get("OBSIDIAN_VAULT")
    vault_path = Path(vault).expanduser() if vault else DEFAULT_VAULT
    secret_file = vault_path / WEBHOOK_SECRET_RELPATH

    if not secret_file.is_file():
        _err(
            f"no webhook URL: set $AUTOMATE_WEBHOOK_URL or create {secret_file} "
            "(see the vault's scripts/daily_time_tracker.py)."
        )
        raise SystemExit(2)

    url = secret_file.read_text(encoding="utf-8").strip()
    if not url:
        _err(f"{secret_file} is empty.")
        raise SystemExit(2)
    if not url.startswith(("http://", "https://")):
        _err(
            f"{secret_file} is not a real URL yet (looks like a placeholder). "
            "Fill in the Automate webhook URL or set $AUTOMATE_WEBHOOK_URL."
        )
        raise SystemExit(2)
    return url


def now_iso() -> str:
    """Local time, ISO 8601 to seconds (no microseconds)."""
    return datetime.now().isoformat(timespec="seconds")


def build_payload(args: argparse.Namespace) -> dict:
    when = args.at.strip() if args.at else now_iso()
    if args.command == "start":
        return {
            "payload": "start_action",
            "activity": args.activity,
            "comment": args.comment or "",
            "start": when,
        }
    # stop
    return {"payload": "stop_action", "end": when}


def post(url: str, payload: dict) -> None:
    """POST the JSON payload; raise SystemExit(3) on any transport/HTTP failure."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as response:
            if 200 <= response.status < 300:
                return
            _err(f"webhook returned HTTP {response.status}.")
            raise SystemExit(3)
    except SystemExit:
        raise
    except Exception as exc:  # urllib.error.URLError, socket.timeout, …
        _err(f"could not reach the Automate webhook: {exc}")
        raise SystemExit(3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start or stop a live SimpleTimeTracker activity via the Automate webhook.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the JSON payload and exit without sending (never prints the URL).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="start a running activity now.")
    p_start.add_argument(
        "--activity",
        default="Task",
        help='SimpleTimeTracker activity name (default: "Task").',
    )
    p_start.add_argument(
        "--comment",
        default="",
        help='comment; for activity "Task" use the task-note name (rendered as [[wikilink]]).',
    )
    p_start.add_argument("--at", default="", help="override start time (ISO 8601); default now.")

    p_stop = sub.add_parser("stop", help="stop the running activity now.")
    p_stop.add_argument("--at", default="", help="override stop time (ISO 8601); default now.")

    args = parser.parse_args(argv)
    payload = build_payload(args)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    url = resolve_webhook_url()
    post(url, payload)

    if args.command == "start":
        label = f'{payload["activity"]} — {payload["comment"]}'.rstrip(" —")
        print(f"started: {label} @ {payload['start']}")
    else:
        print(f"stopped @ {payload['end']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
