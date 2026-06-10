#!/usr/bin/env python3
"""
simple_time_tracker.py — start/stop/add a SimpleTimeTracker activity via Automate.

Drives the Android **SimpleTimeTracker** app through a **LlamaLab Automate** flow, using
Automate's **Cloud Messaging** API. Mirrors the working
``android_automate_app_cloud_message_script.sh`` (the window-logger's sender): the same
endpoint, the same envelope, and the same ``start`` / ``stop`` / ``add_record`` actions —
so a chat/work session can be timed live (``start`` … ``stop``) or back-filled (``add_record``).

Transport (do not invent a per-flow webhook URL — there isn't one):
  POST https://llamalab.com/automate/cloud/message   (override with $AUTOMATE_CLOUD_MESSAGE_URL)
  Content-Type: application/json
  body = {
    "secret":   "<your Automate account secret>",
    "to":       "<the Google account the device is registered to>",
    "device":   "<destination device name>",   # optional; omitted-if-empty
    "priority": "normal" | "high",
    "payload":  { ...action object... }          # NESTED OBJECT, not a string
  }

payload by action:
  start:       {"action":"start",      "extra_activity_name": A, "extra_record_comment": C}
  stop:        {"action":"stop",       "extra_activity_name": A, "extra_record_comment": C}
  add_record:  {"action":"add_record", "extra_activity_name": A, "extra_record_comment": C,
                "extra_record_time_started": "YYYY-MM-DD HH:MM:SS",
                "extra_record_time_ended":   "YYYY-MM-DD HH:MM:SS"}

For activity "Task" the comment is the task-note name (the vault renders it as a [[wikilink]]).

Config resolution (env first, then an optional KEY=VALUE env file):
  AUTOMATE_ANDROID_APP_SECRET   (required)   — Automate › Settings › Cloud secret
  AUTOMATE_ANDROID_APP_TO       (required)   — the registered Google account email
  AUTOMATE_ANDROID_APP_DEVICE   (optional)   — device name; empty ⇒ all devices on the account
  env file: $AUTOMATE_ENV_FILE, else <vault>/.secrets/automate.env
            (vault = $LORITE_VAULT / $OBSIDIAN_VAULT, else ~/git/lorite-obsidian-notes)
The secret is never printed (redacted in --dry-run and errors).

Usage:
  simple_time_tracker.py start --comment "Improve my Obsidian workflow to use AI LLM agents"
  simple_time_tracker.py start --activity Code --comment "dotfiles agents"
  simple_time_tracker.py stop
  simple_time_tracker.py add_record --comment "..." --start "2026-06-10 13:00:00" --end "2026-06-10 14:30:00"
  simple_time_tracker.py start --comment "..." --dry-run   # print envelope (secret redacted), send nothing

Exit codes: 0 success · 2 config/usage error · 3 transport/HTTP error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

CLOUD_MESSAGE_URL = "https://llamalab.com/automate/cloud/message"
DEFAULT_VAULT = Path.home() / "git" / "lorite-obsidian-notes"
ENV_FILE_RELPATH = Path(".secrets") / "automate.env"
RECORD_TIME_FMT = "%Y-%m-%d %H:%M:%S"
REQUEST_TIMEOUT_SEC = 20


def _err(msg: str) -> None:
    print(f"simple_time_tracker: {msg}", file=sys.stderr)


def _vault_path() -> Path:
    vault = os.environ.get("LORITE_VAULT") or os.environ.get("OBSIDIAN_VAULT")
    return Path(vault).expanduser() if vault else DEFAULT_VAULT


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE file (ignores blanks/#comments, strips quotes)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def resolve_config() -> dict[str, str]:
    """Return {secret, to, device} from env, falling back to the env file.

    Raises SystemExit(2) (secret never echoed) if a required value is missing.
    """
    env_file = os.environ.get("AUTOMATE_ENV_FILE")
    file_vals = _load_env_file(Path(env_file).expanduser() if env_file else _vault_path() / ENV_FILE_RELPATH)

    def pick(name: str) -> str:
        return (os.environ.get(name) or file_vals.get(name) or "").strip()

    secret = pick("AUTOMATE_ANDROID_APP_SECRET")
    to = pick("AUTOMATE_ANDROID_APP_TO")
    device = pick("AUTOMATE_ANDROID_APP_DEVICE")

    missing = [n for n, v in (("AUTOMATE_ANDROID_APP_SECRET", secret), ("AUTOMATE_ANDROID_APP_TO", to)) if not v]
    if missing:
        where = env_file or (_vault_path() / ENV_FILE_RELPATH)
        _err(
            f"missing required config: {', '.join(missing)}. "
            f"Export them or put them in {where} (KEY=VALUE)."
        )
        raise SystemExit(2)
    return {"secret": secret, "to": to, "device": device}


def build_payload(args: argparse.Namespace) -> dict:
    payload: dict[str, str] = {
        "action": args.command,
        "extra_activity_name": args.activity,
        "extra_record_comment": args.comment or "",
    }
    if args.command == "add_record":
        payload["extra_record_time_started"] = _norm_time(args.start)
        payload["extra_record_time_ended"] = _norm_time(args.end)
    return payload


def _norm_time(value: str) -> str:
    """Accept an epoch, an ISO string, or already-formatted 'YYYY-MM-DD HH:MM:SS'."""
    value = value.strip()
    if value.isdigit():
        return datetime.fromtimestamp(int(value)).strftime(RECORD_TIME_FMT)
    try:
        return datetime.fromisoformat(value).strftime(RECORD_TIME_FMT)
    except ValueError:
        return value  # assume it is already in the expected format


def build_envelope(config: dict[str, str], payload: dict, priority: str) -> dict:
    envelope = {
        "secret": config["secret"],
        "to": config["to"],
        "priority": priority,
        "payload": payload,
    }
    if config.get("device"):
        envelope["device"] = config["device"]
    return envelope


def post(envelope: dict) -> None:
    url = os.environ.get("AUTOMATE_CLOUD_MESSAGE_URL", CLOUD_MESSAGE_URL)
    data = json.dumps(envelope).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as response:
            if 200 <= response.status < 300:
                return
            _err(f"Automate cloud message returned HTTP {response.status}.")
            raise SystemExit(3)
    except SystemExit:
        raise
    except Exception as exc:  # urllib.error.URLError, socket.timeout, …
        _err(f"could not reach the Automate cloud endpoint: {exc}")
        raise SystemExit(3)


def _redacted(envelope: dict) -> dict:
    safe = dict(envelope)
    safe["secret"] = "***" if safe.get("secret") else ""
    return safe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start/stop/add a SimpleTimeTracker activity via the Automate cloud message API.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the envelope (secret redacted) and exit without sending.",
    )
    parser.add_argument(
        "--priority", choices=["normal", "high"], default="normal", help='message priority (default "normal").'
    )

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--activity", default="Task", help='activity name (default "Task").')
        p.add_argument(
            "--comment",
            default="",
            help='comment; for activity "Task" use the task-note name (rendered as [[wikilink]]).',
        )

    sub = parser.add_subparsers(dest="command", required=True)
    add_common(sub.add_parser("start", help="start a running activity now."))
    add_common(sub.add_parser("stop", help="stop the running activity now."))
    p_add = sub.add_parser("add_record", help="add a finished record with explicit start/end.")
    add_common(p_add)
    p_add.add_argument("--start", required=True, help="start time (epoch, ISO, or 'YYYY-MM-DD HH:MM:SS').")
    p_add.add_argument("--end", required=True, help="end time (epoch, ISO, or 'YYYY-MM-DD HH:MM:SS').")

    args = parser.parse_args(argv)
    payload = build_payload(args)

    if args.dry_run:
        # Build with whatever config is available, but never block a dry-run on missing secrets.
        try:
            config = resolve_config()
        except SystemExit:
            config = {"secret": "", "to": "", "device": ""}
        print(json.dumps(_redacted(build_envelope(config, payload, args.priority)), indent=2))
        return 0

    envelope = build_envelope(resolve_config(), payload, args.priority)
    post(envelope)

    label = f'{payload["extra_activity_name"]} — {payload["extra_record_comment"]}'.rstrip(" —")
    print(f"{args.command}: {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
