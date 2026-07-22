#!/usr/bin/env python3
"""Bridge ActivityWatch media events -> SimpleTimeTracker.

Reads the `aw-watcher-media-player_<host>` bucket, groups consecutive segments
of the *same player* that are separated by only a short gap into one session —
so an ad in the middle of a video (which flips the MPRIS title) collapses back
into a single entry using the dominant title — and forwards each finished
session to SimpleTimeTracker via `simple_time_tracker.py add_record`.

Idempotent: a state file records the last processed session end, and only
sessions that have clearly ended (no media for SETTLE seconds) and exceed
MIN_SESSION are emitted. Runs every few minutes from a systemd timer.

  aw_media_to_stt.py            # process + send
  aw_media_to_stt.py --dry-run  # print what would be sent, send nothing
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse

AW_BASE = os.environ.get("AW_SERVER", "http://localhost:5600")
STT = os.path.expanduser("~/git/dotfiles/tools/lorite/simple_time_tracker.py")
STATE = os.path.expanduser("~/.local/state/lorite/aw_media_to_stt.json")

GAP_MERGE_SEC = 150     # segments of same player within this gap = one session
SETTLE_SEC = 150        # a session is "finished" once media has been idle this long
MIN_SESSION_SEC = 120   # ignore sessions with less than this much actual play time

# Players whose playback maps to the STT "Music" activity (substring, lowercase).
MUSIC_PLAYERS = ("spotify", "rhythmbox", "ncspot", "mpd", "tidal")
MUSIC_ACTIVITY = "Music"
VIDEO_ACTIVITY = "YouTube"   # default for browsers / video players


def _get(url):
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.load(r)


def find_media_bucket():
    for bid in _get(f"{AW_BASE}/api/0/buckets/"):
        if bid.startswith("aw-watcher-media-player_"):
            return bid
    return None


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last_end_epoch": 0}


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(state, f)


def epoch(iso):
    return dt.datetime.fromisoformat(iso).timestamp()


def fetch_events(bucket, since_epoch):
    start = dt.datetime.fromtimestamp(
        max(0, since_epoch - GAP_MERGE_SEC), dt.timezone.utc
    ).isoformat()
    end = dt.datetime.now(dt.timezone.utc).isoformat()
    url = (
        f"{AW_BASE}/api/0/buckets/{bucket}/events"
        f"?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}&limit=10000"
    )
    events = _get(url)
    events.sort(key=lambda e: e["timestamp"])
    return events


def build_sessions(events):
    """Merge same-player, small-gap segments into sessions."""
    sessions = []
    cur = None
    for e in events:
        data = e.get("data", {})
        player = (data.get("player") or "").lower()
        title = data.get("title") or ""
        artist = data.get("artist") or ""
        start = epoch(e["timestamp"])
        dur = float(e.get("duration", 0) or 0)
        end = start + dur
        if (
            cur
            and cur["player"] == player
            and start - cur["end"] <= GAP_MERGE_SEC
        ):
            cur["end"] = max(cur["end"], end)
            cur["play"] += dur
        else:
            if cur:
                sessions.append(cur)
            cur = {
                "player": player,
                "start": start,
                "end": end,
                "play": dur,
                "titles": {},
            }
        # accumulate per-title duration to pick the dominant (non-ad) title
        if title:
            t = cur["titles"].setdefault(title, {"dur": 0.0, "artist": artist})
            t["dur"] += dur
    if cur:
        sessions.append(cur)
    return sessions


def classify(session):
    dominant = max(
        session["titles"].items(), key=lambda kv: kv[1]["dur"], default=(None, None)
    )
    title = dominant[0] or session["player"] or "media"
    artist = (dominant[1] or {}).get("artist", "") if dominant[1] else ""
    if any(m in session["player"] for m in MUSIC_PLAYERS):
        activity = MUSIC_ACTIVITY
        comment = f"{artist} — {title}" if artist else title
    else:
        activity = VIDEO_ACTIVITY
        comment = title
    return activity, comment


def send(activity, comment, start_epoch, end_epoch, dry_run):
    fmt = lambda t: dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
    cmd = [
        "python3", STT, "add_record",
        "--activity", activity,
        "--comment", comment,
        "--start", fmt(start_epoch),
        "--end", fmt(end_epoch),
    ]
    if dry_run:
        cmd.insert(2, "--dry-run")  # global flag before the subcommand
    print(f"[media->stt] {activity} | {comment} | "
          f"{fmt(start_epoch)} -> {fmt(end_epoch)}", file=sys.stderr)
    subprocess.run(cmd, check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        bucket = find_media_bucket()
    except (urllib.error.URLError, OSError) as e:
        print(f"[media->stt] aw-server unavailable ({e}); skipping.", file=sys.stderr)
        return 0
    if not bucket:
        print("[media->stt] no media bucket yet; skipping.", file=sys.stderr)
        return 0

    state = load_state()
    now = dt.datetime.now().timestamp()
    events = fetch_events(bucket, state["last_end_epoch"])
    sessions = build_sessions(events)

    new_last = state["last_end_epoch"]
    sent = 0
    for s in sessions:
        finished = (now - s["end"]) >= SETTLE_SEC
        fresh = s["start"] > state["last_end_epoch"]
        long_enough = s["play"] >= MIN_SESSION_SEC
        if finished and fresh and long_enough:
            activity, comment = classify(s)
            send(activity, comment, s["start"], s["end"], args.dry_run)
            new_last = max(new_last, s["end"])
            sent += 1

    if sent and not args.dry_run:
        state["last_end_epoch"] = new_last
        save_state(state)
    print(f"[media->stt] {sent} session(s) forwarded.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
