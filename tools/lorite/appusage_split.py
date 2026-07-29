#!/usr/bin/env python3
"""Split an App Usage (AUM) phone export into the per-day files the daily note reads.

The app exports one big file covering months; the vault expects one folder per day:

    _android-appusage/<device>/daily/<D+1>/AUM_V4_Activity_<D+1>_<HH-MM-SS>.csv
    _android-appusage/<device>/daily/<D+1>/AUM_V4_DailyUsage_<D+1>_<HH-MM-SS>.csv

NOTE THE OFF-BY-ONE, it is not a mistake: the folder is named after the day the export
was *taken*, and holds the *previous* day's data — `scripts/daily/app_usage.js` looks up
`nextDayFileTitle`. Confirmed against a known-good folder: TCL11/daily/2025-04-30 contains
"Activity history, 29 April 2025".

DailyUsage is DERIVED, not copied. The export contains only one DailyUsage snapshot (today
plus rolling periods), so past days cannot be copied from it — but the Activity rows carry
every session, so per-app totals and session counts are reconstructed by aggregation. That
is exactly what the note's "Most Used Apps" table shows: Summary / Usage time / Checked
phone.

    ./appusage_split.py <export-dir>            # e.g. .../_android-appusage/OnePlus
    ./appusage_split.py <export-dir> --dry-run
"""
import argparse
import collections
import csv
import datetime as dt
import glob
import os
import re
import sys

ACTIVITY_GLOB = "AUM_V4_Activity_*.csv"
# The activity log interleaves screen-state pseudo-entries with real apps. They must not
# count as usage: including "Screen off (locked)" put 2026-07-29 at 11:24:32 when the app
# itself reports 5:03:52. The unlock count is what the app calls "Checked phone" — its own
# export said 65 where "Screen on (unlocked)" appears 66 times, i.e. the same measure.
SCREEN_PREFIX = "Screen "
UNLOCK_ENTRY = "Screen on (unlocked)"
HEADER = ["App name", "Date", "Time", "Duration"]


def parse_date(text):
    """App Usage writes M/D/YY; be liberal, the export locale has bitten this before."""
    text = (text or "").strip()
    for fmt in ("%m/%d/%y", "%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def hms_to_seconds(text):
    parts = (text or "").strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def seconds_to_hms(sec):
    return "%d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)


def newest(pattern, root):
    files = sorted(glob.glob(os.path.join(root, pattern)))
    return files[-1] if files else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export_dir")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace days that already have a folder (default: skip them)")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.export_dir))
    activity = newest(ACTIVITY_GLOB, root)
    if not activity:
        sys.exit("No %s found in %s" % (ACTIVITY_GLOB, root))

    # Time suffix: reuse the export's own, so the pair of files matches and the JS's
    # _getTimeFileNameFromFolder finds it.
    m = re.search(r"_(\d{2}-\d{2}-\d{2})\.csv$", activity)
    suffix = m.group(1) if m else "00-00-00"

    by_day = collections.defaultdict(list)
    with open(activity, encoding="utf-8", errors="replace") as fh:
        for row in csv.reader(fh):
            # Section banners ("Activity history, 29 April 2025") and blanks have <4 cells.
            if len(row) < 4 or row[0].strip() == "App name":
                continue
            day = parse_date(row[1])
            if day:
                by_day[day].append(row[:4])

    if not by_day:
        sys.exit("Parsed no dated rows from %s — has the export format changed?" % activity)

    daily_root = os.path.join(root, "daily")
    written = skipped = 0
    for day in sorted(by_day):
        folder_day = day + dt.timedelta(days=1)      # see the note at the top
        name = folder_day.isoformat()
        out_dir = os.path.join(daily_root, name)
        act_path = os.path.join(out_dir, "AUM_V4_Activity_%s_%s.csv" % (name, suffix))
        use_path = os.path.join(out_dir, "AUM_V4_DailyUsage_%s_%s.csv" % (name, suffix))

        existing = glob.glob(os.path.join(out_dir, "AUM_V4_Activity_*.csv"))
        # --overwrite replaces only what a previous run of THIS export wrote (same time
        # suffix). A genuine app export for that day has a different suffix and is
        # authoritative — clobbering it, or adding a second file beside it, would leave
        # _getTimeFileNameFromFolder picking between two sources at random.
        ours = [f for f in existing if f.endswith("_%s.csv" % suffix)]
        if existing and not (args.overwrite and len(ours) == len(existing)):
            skipped += 1
            continue

        rows = by_day[day]
        totals = collections.OrderedDict()
        unlocks = 0
        for app, _d, _t, dur in rows:
            app = app.strip()
            if app.startswith(SCREEN_PREFIX):
                unlocks += 1 if app == UNLOCK_ENTRY else 0
                continue
            sec, count = totals.get(app, (0, 0))
            totals[app] = (sec + hms_to_seconds(dur), count + 1)
        ranked = sorted(totals.items(), key=lambda kv: -kv[1][0])

        print("  %s  ->  daily/%s  (%d sessions, %d apps)" % (day, name, len(rows), len(ranked)))
        written += 1
        if args.dry_run:
            continue

        os.makedirs(out_dir, exist_ok=True)
        with open(act_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, quoting=csv.QUOTE_ALL)
            w.writerow(HEADER)
            w.writerows(rows)
        with open(use_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, quoting=csv.QUOTE_ALL)
            w.writerow(["Summary", "Usage time", "", "Checked phone", ""])
            w.writerow([day.strftime("%d/%m/%Y"),
                        seconds_to_hms(sum(s for s, _ in totals.values())), "",
                        str(unlocks), ""])
            for app, (sec, count) in ranked:
                w.writerow([app, seconds_to_hms(sec), "", str(count), ""])

    print("%s %d day(s)%s" % ("would write" if args.dry_run else "wrote", written,
                              ", skipped %d already present" % skipped if skipped else ""))


if __name__ == "__main__":
    main()
