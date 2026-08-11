#!/usr/bin/env python3
"""Declare "what I am actually doing" straight into ActivityWatch.

The intent layer that ActivityWatch cannot observe: which task is being worked on, and
anything else that has to be *stated* rather than measured. Everything else (which app,
which video, which site) AW already derives on its own, so this deliberately covers only
the part that needs declaring.

WHY THIS REPLACES THE SimpleTimeTracker HOP
    Today a declaration travels Claude/phone -> Automate Cloud Message -> Automate flow ->
    SimpleTimeTracker, purely because STT has no API. aw-server has one, so the same
    declaration is a single HTTP call and the Automate flows can be deleted rather than
    maintained. It also makes the entries editable: aw-server routes POST, GET, GET-by-id
    and DELETE-by-id, which is what lets an LLM add, correct and remove entries afterwards.

WHY IT TALKS TO THE *LOCAL* aw-server
    The home server publishes aw-server on 127.0.0.1:5600 only (deliberately - aw-server
    has no auth of its own, so it is never exposed), and it is therefore unreachable across
    Tailscale. Rather than punching a hole or adding an API key to a Coolify-managed
    config, declarations are written to whichever aw-server is local and ride the sync path
    that already exists: aw-sync -> Syncthing -> the home server's aw-sync pull loop. The
    same route every laptop bucket already takes, and the one the phone now uses too.

CATEGORISATION COMES FREE
    Events carry `app` and `title` as well as `task`, because aw-server's own categorize()
    matches rules against those fields. Declared intent is therefore classified by the very
    same rules as observed activity, with no separate matcher to drift.

    lorite_intent.py start --task "Write the second PhD Conference Paper"
    lorite_intent.py stop
    lorite_intent.py list --date 2026-08-11
    lorite_intent.py edit 42 --task "Something else"
    lorite_intent.py rm 42
    lorite_intent.py add --task "Reading" --start "2026-08-11 09:00" --end "2026-08-11 09:45"
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

AW_SERVER = os.environ.get("AW_SERVER", "http://localhost:5600")
BUCKET_CLIENT = "aw-intent"
BUCKET_TYPE = "intent.declared"
DEFAULT_ACTIVITY = "Task"

# Where a running declaration is remembered between `start` and `stop`. Local-only state:
# the event itself is not written until `stop`, so an abandoned start costs nothing.
STATE_PATH = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")
) / "lorite" / "intent.json"


def _err(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def _req(method, path, payload=None):
    url = "%s%s" % (AW_SERVER.rstrip("/"), path)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        _err("aw-server %s %s -> HTTP %s: %s" % (method, path, exc.code, exc.read()[:200]))
    except urllib.error.URLError as exc:
        _err("Cannot reach aw-server at %s (%s). Is ActivityWatch running?" % (AW_SERVER, exc))


def server_info():
    return _req("GET", "/api/0/info") or {}


def bucket_id():
    return "%s_%s" % (BUCKET_CLIENT, server_info().get("hostname", "unknown"))


def ensure_bucket(bid):
    """Create the bucket if absent. Idempotent: aw-server returns 304 when it exists."""
    if bid in (_req("GET", "/api/0/buckets/") or {}):
        return
    # hostname "!local" tells aw-server to fill in its own hostname and device_id, so this
    # works unchanged on the laptop, the server, or anywhere else it is run.
    _req("POST", "/api/0/buckets/%s" % bid,
         {"client": BUCKET_CLIENT, "type": BUCKET_TYPE, "hostname": "!local"})
    print("created bucket %s" % bid)


def _iso(when):
    return when.astimezone().isoformat()


def parse_when(value):
    """Accept 'YYYY-MM-DD HH:MM[:SS]', an ISO string, or 'HH:MM' meaning today."""
    value = value.strip()
    if len(value) <= 5 and ":" in value:
        today = dt.date.today().isoformat()
        value = "%s %s" % (today, value)
    value = value.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(value, fmt).astimezone()
        except ValueError:
            pass
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        _err("Cannot parse time %r (want 'YYYY-MM-DD HH:MM', 'HH:MM', or ISO)" % value)
    return parsed if parsed.tzinfo else parsed.astimezone()


def event_data(activity, task, comment, source):
    # `app` and `title` exist so aw-server's categorize() can classify these events with the
    # same rules as observed activity; `task` keeps the note name machine-readable for the
    # daily-note export, which renders it as a [[wikilink]].
    data = {"app": activity, "title": task or comment or activity, "source": source}
    if task:
        data["task"] = task
    if comment:
        data["comment"] = comment
    return data


def insert_event(bid, start, duration, data, dry):
    payload = [{"timestamp": _iso(start), "duration": round(duration, 3), "data": data}]
    if dry:
        print(json.dumps(payload[0], indent=2, ensure_ascii=False))
        return None
    ensure_bucket(bid)
    created = _req("POST", "/api/0/buckets/%s/events" % bid, payload)
    if isinstance(created, list) and created:
        return created[0]
    # aw-server only started returning the created events (Json<Vec<Event>>) after the
    # version deployed here (v0.13.2 answers a bare `null`), and the id is needed so that
    # `edit` knows what it wrote and an LLM can address the entry afterwards. Look it up by
    # the timestamp we just asked for rather than assuming the newest event is ours - it is
    # not, when the block being recorded is in the past.
    return find_event(bid, start)


def find_event(bid, start):
    """The event in `bid` starting at `start`, or None."""
    target = start.astimezone(dt.timezone.utc)
    for e in day_events(bid, start.astimezone().date().isoformat()):
        ts = dt.datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        if abs((ts - target).total_seconds()) < 1:
            return e
    return None


def read_state():
    if not STATE_PATH.is_file():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except (ValueError, OSError):
        return None


def write_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def clear_state():
    if STATE_PATH.is_file():
        STATE_PATH.unlink()


def fmt_event(e):
    start = dt.datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
    end = start + dt.timedelta(seconds=e.get("duration", 0))
    d = e.get("data", {})
    label = d.get("task") or d.get("comment") or d.get("title") or ""
    return "%6s  %s-%s  %-8s %s" % (
        e.get("id", "?"), start.strftime("%H:%M"), end.strftime("%H:%M"),
        d.get("app", ""), label,
    )


def day_events(bid, date):
    """Events overlapping `date`, oldest first."""
    start = dt.datetime.combine(dt.date.fromisoformat(date), dt.time.min).astimezone()
    end = start + dt.timedelta(days=1)
    path = ("/api/0/buckets/%s/events?limit=-1&start=%s&end=%s"
            % (bid, urllib.request.quote(_iso(start)), urllib.request.quote(_iso(end))))
    return sorted(_req("GET", path) or [], key=lambda e: e["timestamp"])


# --- commands ---------------------------------------------------------------------

def cmd_start(args):
    if read_state():
        _err("A declaration is already running. `stop` it first, or `status` to see it.")
    now = dt.datetime.now().astimezone()
    write_state({"start": _iso(now), "activity": args.activity, "task": args.task,
                 "comment": args.comment, "source": args.source})
    print("start: %s — %s" % (args.activity, args.task or args.comment or ""))


def cmd_stop(args):
    state = read_state()
    if not state:
        _err("Nothing running. Use `add` to record a block that already finished.")
    start = dt.datetime.fromisoformat(state["start"])
    duration = (dt.datetime.now().astimezone() - start).total_seconds()
    if duration < 0:
        _err("Recorded start is in the future (%s); refusing to write a negative duration."
             % state["start"])
    data = event_data(state["activity"], state.get("task"), state.get("comment"),
                      state.get("source", "cli"))
    created = insert_event(bucket_id(), start, duration, data, args.dry_run)
    if not args.dry_run:
        clear_state()
    print("stop: %s — %s (%d min)%s"
          % (state["activity"], state.get("task") or "", round(duration / 60),
             "" if not created else " [id %s]" % created.get("id")))


def cmd_status(args):
    state = read_state()
    if not state:
        print("nothing running")
        return
    start = dt.datetime.fromisoformat(state["start"])
    mins = round((dt.datetime.now().astimezone() - start).total_seconds() / 60)
    print("running since %s (%d min): %s — %s"
          % (start.strftime("%H:%M"), mins, state["activity"],
             state.get("task") or state.get("comment") or ""))


def cmd_add(args):
    start, end = parse_when(args.start), parse_when(args.end)
    if end <= start:
        _err("--end must be after --start")
    data = event_data(args.activity, args.task, args.comment, args.source)
    created = insert_event(bucket_id(), start, (end - start).total_seconds(), data,
                           args.dry_run)
    print("added %s-%s %s — %s%s"
          % (start.strftime("%H:%M"), end.strftime("%H:%M"), args.activity,
             args.task or args.comment or "",
             "" if not created else " [id %s]" % created.get("id")))


def cmd_list(args):
    events = day_events(bucket_id(), args.date)
    if not events:
        print("no declarations on %s" % args.date)
        return
    print("    id  time         activity task")
    total = 0
    for e in events:
        print(fmt_event(e))
        total += e.get("duration", 0)
    print("%s total declared: %d h %02d m" % (" " * 6, total // 3600, total % 3600 // 60))


def cmd_edit(args):
    bid = bucket_id()
    old = _req("GET", "/api/0/buckets/%s/events/%d" % (bid, args.id))
    if not old:
        _err("No event %d in %s" % (args.id, bid))
    d = dict(old.get("data", {}))
    start = (parse_when(args.start) if args.start
             else dt.datetime.fromisoformat(old["timestamp"].replace("Z", "+00:00")))
    duration = old.get("duration", 0)
    if args.end:
        duration = (parse_when(args.end) - start).total_seconds()
        if duration <= 0:
            _err("--end must be after the start")
    activity = args.activity or d.get("app", DEFAULT_ACTIVITY)
    task = args.task if args.task is not None else d.get("task")
    comment = args.comment if args.comment is not None else d.get("comment")
    data = event_data(activity, task, comment, d.get("source", "cli"))

    # aw-server has no update verb, so an edit is insert-then-delete. Deliberately in that
    # order: if the delete fails the day has a duplicate, which is visible and fixable,
    # whereas delete-first would silently lose the entry when the insert fails.
    created = insert_event(bid, start, duration, data, args.dry_run)
    if args.dry_run:
        print("(dry-run) would delete event %d after inserting the replacement" % args.id)
        return
    _req("DELETE", "/api/0/buckets/%s/events/%d" % (bid, args.id))
    print("edited %d -> %s" % (args.id, created.get("id") if created else "?"))


def cmd_rm(args):
    bid = bucket_id()
    old = _req("GET", "/api/0/buckets/%s/events/%d" % (bid, args.id))
    if not old:
        _err("No event %d in %s" % (args.id, bid))
    if args.dry_run:
        print("(dry-run) would delete:\n%s" % fmt_event(old))
        return
    _req("DELETE", "/api/0/buckets/%s/events/%d" % (bid, args.id))
    print("deleted %d" % args.id)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be written; send nothing")
    ap.add_argument("--source", default=os.environ.get("LORITE_INTENT_SOURCE", "cli"),
                    help="who declared this (cli, claude, phone). Recorded in data.source")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_fields(p, task_default=None):
        p.add_argument("--activity", default=DEFAULT_ACTIVITY,
                       help="activity name (default: %s)" % DEFAULT_ACTIVITY)
        p.add_argument("--task", default=task_default,
                       help="task note basename, rendered as a [[wikilink]]")
        p.add_argument("--comment", default=None, help="free-text detail")

    p = sub.add_parser("start", help="begin a declaration (written on stop)")
    add_fields(p)
    sub.add_parser("stop", help="end the running declaration and write it")
    sub.add_parser("status", help="show the running declaration, if any")

    p = sub.add_parser("add", help="record a block that already finished")
    add_fields(p)
    p.add_argument("--start", required=True, help="'YYYY-MM-DD HH:MM', 'HH:MM', or ISO")
    p.add_argument("--end", required=True, help="same formats as --start")

    p = sub.add_parser("list", help="list declarations for a day")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD")

    p = sub.add_parser("edit", help="change a declaration (insert-then-delete)")
    p.add_argument("id", type=int)
    p.add_argument("--activity", default=None)
    p.add_argument("--task", default=None)
    p.add_argument("--comment", default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)

    p = sub.add_parser("rm", help="delete a declaration")
    p.add_argument("id", type=int)

    args = ap.parse_args()
    {"start": cmd_start, "stop": cmd_stop, "status": cmd_status, "add": cmd_add,
     "list": cmd_list, "edit": cmd_edit, "rm": cmd_rm}[args.cmd](args)


if __name__ == "__main__":
    main()
