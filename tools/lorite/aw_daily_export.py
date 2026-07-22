#!/usr/bin/env python3
"""Export ActivityWatch active-window data into the Obsidian daily-note CSVs.

Reproduces the two CSVs the daily note's `listLaptopMostUsedApps` /
`listLaptopTimeLogs` (scripts/daily/app_usage.js) already read, so the
"💻 Laptop Usage Logs" section works again — now sourced from ActivityWatch
instead of the retired `linux-simple-app-logger`/window_logger.sh.

Per date it writes into  <vault>/_android-appusage/LaptopITU/daily/<date>/ :
  - LORI_Activity_<date>.csv   (App name, Window Title, Date, Time, Duration)  chronological
  - LORI_DailyUsage_<date>.csv (Summary, Usage time, Access count)             per-app totals

"Active" = window events intersected with aw-watcher-afk not-afk periods
(the canonical ActivityWatch query). Times are converted to system local time.

Usage:
  aw_daily_export.py                 # export yesterday and today
  aw_daily_export.py --date 2026-07-22
  aw_daily_export.py --backfill 7    # last 7 days incl. today
Exits 0 even if aw-server is unreachable (logs a note) so it never blocks the
daily-note pipeline.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.request
import urllib.error

AW_BASE = os.environ.get("AW_SERVER", "http://localhost:5600")
VAULT = os.environ.get(
    "LORITE_VAULT", os.path.expanduser("~/git/lorite-obsidian-notes")
)
SUBPATH = "_android-appusage/LaptopITU/daily"


def _get(url):
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.load(r)


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def find_host_suffix():
    """Return the host suffix shared by this machine's aw buckets, e.g.
    '_lori-ThinkPad-P15-Gen-2i', by inspecting the window bucket id."""
    buckets = _get(f"{AW_BASE}/api/0/buckets/")
    for bid in buckets:
        if bid.startswith("aw-watcher-window_"):
            return bid[len("aw-watcher-window") :]  # includes leading '_host'
    raise RuntimeError("no aw-watcher-window bucket found")


def friendly_app(wm_class: str) -> str:
    """com.anthropic.Claude -> Claude ; org.gnome.SystemMonitor -> SystemMonitor
    ; brave-browser -> brave-browser (left as-is when not reverse-DNS)."""
    if not wm_class:
        return "Unknown"
    if "." in wm_class and " " not in wm_class:
        return wm_class.rsplit(".", 1)[-1]
    return wm_class


def local_day_period(day: dt.date):
    """(start_iso, end_iso) local-tz ISO strings spanning the local day."""
    tz = dt.datetime.now().astimezone().tzinfo
    start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    end = start + dt.timedelta(days=1)
    return start.isoformat(), end.isoformat()


def query_active_events(day: dt.date):
    """Active (window ∩ not-afk) events for the local day, sorted by time."""
    start_iso, end_iso = local_day_period(day)
    q = [
        'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
        'win = flood(query_bucket(find_bucket("aw-watcher-window_")));',
        'active = filter_period_intersect(win, '
        'filter_keyvals(afk, "status", ["not-afk"]));',
        "RETURN = sort_by_timestamp(active);",
    ]
    res = _post(
        f"{AW_BASE}/api/0/query/",
        {"query": q, "timeperiods": [f"{start_iso}/{end_iso}"]},
    )
    return res[0] if res else []


def hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def build_rows(events):
    """Merge adjacent same app+title into segments; return (activity_rows,
    per-app totals). activity_rows: list of dicts for LORI_Activity."""
    segments = []
    for e in events:
        app = friendly_app(e.get("data", {}).get("app", ""))
        title = e.get("data", {}).get("title", "") or ""
        ts = dt.datetime.fromisoformat(e["timestamp"]).astimezone()
        dur = float(e.get("duration", 0) or 0)
        if segments and segments[-1]["app"] == app and segments[-1]["title"] == title:
            segments[-1]["duration"] += dur
        else:
            segments.append(
                {"app": app, "title": title, "start": ts, "duration": dur}
            )

    totals = {}
    for s in segments:
        t = totals.setdefault(s["app"], {"dur": 0.0, "count": 0})
        t["dur"] += s["duration"]
        t["count"] += 1
    return segments, totals


def write_csvs(day: dt.date, segments, totals):
    date_str = day.isoformat()
    out_dir = os.path.join(VAULT, SUBPATH, date_str)
    os.makedirs(out_dir, exist_ok=True)

    activity_path = os.path.join(out_dir, f"LORI_Activity_{date_str}.csv")
    with open(activity_path, "w", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["App name", "Window Title", "Date", "Time", "Duration"])
        for s in segments:
            w.writerow(
                [
                    s["app"],
                    s["title"],
                    date_str,
                    s["start"].strftime("%H:%M:%S"),
                    hms(s["duration"]),
                ]
            )

    usage_path = os.path.join(out_dir, f"LORI_DailyUsage_{date_str}.csv")
    ranked = sorted(totals.items(), key=lambda kv: kv[1]["dur"], reverse=True)
    with open(usage_path, "w", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["Summary", "Usage time", "Access count"])
        for app, t in ranked:
            w.writerow([app, hms(t["dur"]), t["count"]])

    return activity_path, usage_path


def export_day(day: dt.date) -> bool:
    events = query_active_events(day)
    segments, totals = build_rows(events)
    a, u = write_csvs(day, segments, totals)
    print(
        f"[aw-export] {day}: {len(segments)} segments, "
        f"{len(totals)} apps → {a}",
        file=sys.stderr,
    )
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (single day)")
    ap.add_argument(
        "--backfill", type=int, help="export the last N days including today"
    )
    args = ap.parse_args()

    today = dt.date.today()
    if args.date:
        days = [dt.date.fromisoformat(args.date)]
    elif args.backfill:
        days = [today - dt.timedelta(days=i) for i in range(args.backfill)]
    else:
        days = [today - dt.timedelta(days=1), today]  # yesterday + today

    try:
        find_host_suffix()  # fail fast if aw-server is down
    except (urllib.error.URLError, OSError, RuntimeError) as e:
        print(f"[aw-export] aw-server unavailable ({e}); nothing written.", file=sys.stderr)
        return 0

    for day in days:
        try:
            export_day(day)
        except Exception as e:  # noqa: BLE001 — never block the pipeline
            print(f"[aw-export] {day} failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
