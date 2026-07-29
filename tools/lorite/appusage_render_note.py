#!/usr/bin/env python3
"""Fill the Android App Usage sections of an already-processed daily note.

Why this exists: the daily-note pipeline runs the Run-plugin blocks and then STRIPS the
script code, so a processed note is a snapshot, not a live view. Days processed before the
App Usage export existed hold empty headings and no generator to re-run — backfilling the
CSVs cannot fix them. This renders exactly what those blocks would have produced and puts
it under the existing headings.

The output deliberately mirrors `scripts/daily/app_usage.js` character for character,
including two quirks that must NOT be "fixed" here or the backfilled days would look
different from the organically generated ones:
  * the end time is formatted with moment's `SS`, which is FRACTIONAL seconds — so it
    always renders as :00 (e.g. "07:18:55–07:22:00").
  * Time Logs keep the "Screen off (locked)" entries; only the usage TABLE omits them.

    ./appusage_render_note.py 2026-07-15            # one day
    ./appusage_render_note.py 2026-07-15 --dry-run
"""
import argparse
import csv
import datetime as dt
import glob
import os
import re
import sys

VAULT = os.path.expanduser(os.environ.get("LORITE_VAULT", "~/git/lorite-obsidian-notes"))
DEVICE_DIR = os.path.join(VAULT, "_android-appusage/OnePlus/daily")
NOTE_DIR = os.path.join(VAULT, "diary/daily")
APPS_HEADING = "## 📈 Most Used Apps"
LOGS_HEADING = "## 📊 Time Logs"
SECTION_H1 = "# 📱 [[Android App Usage App]] Logs"
MIN_LOG_SECONDS = 180          # the JS filters at 00:03:00


def hms_to_seconds(text):
    try:
        p = [int(x) for x in (text or "").strip().split(":")]
    except ValueError:
        return 0
    while len(p) < 3:
        p.insert(0, 0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def read_csv(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def render(day):
    """Return (apps_table, time_logs) for the given date, or (None, None)."""
    folder = os.path.join(DEVICE_DIR, (day + dt.timedelta(days=1)).isoformat())
    usage = sorted(glob.glob(os.path.join(folder, "AUM_V4_DailyUsage_*.csv")))
    activity = sorted(glob.glob(os.path.join(folder, "AUM_V4_Activity_*.csv")))
    if not usage or not activity:
        return None, None

    skip = ("Top apps", "Daily usage digest", "Created by App Usage")
    table = ["| App\t| Usage Time\t| Times Accessed\t|",
             "|------------|------------|----------------|"]
    for row in read_csv(usage[-1]):
        name = (row.get("Summary") or "").strip()
        if not name or any(k in name for k in skip):
            continue
        table.append("| %s\t| %s\t| %s\t\t|"
                     % (name, row.get("Usage time", ""), row.get("Checked phone", "")))

    logs = []
    for row in read_csv(activity[-1]):
        dur = hms_to_seconds(row.get("Duration"))
        if dur < MIN_LOG_SECONDS:
            continue
        start = row.get("Time", "").strip()
        try:
            t0 = dt.datetime.strptime(start, "%H:%M:%S")
        except ValueError:
            continue
        t1 = t0 + dt.timedelta(seconds=dur)
        # `SS` in the JS is fractional seconds, so the end always shows :00 — matched here
        # on purpose so backfilled days are indistinguishable from generated ones.
        logs.append("- %s–%s:00 — %s." % (start, t1.strftime("%H:%M"),
                                          (row.get("App name") or "").strip()))
    logs.reverse()
    return "\n".join(table), "\n".join(logs)


def fill(note_path, apps, logs, dry):
    with open(note_path, encoding="utf-8") as fh:
        text = fh.read()
    if SECTION_H1 not in text:
        return "no Android section"

    def put(body, heading, content):
        i = body.index(heading)
        j = i + len(heading)
        # Only fill when the heading is empty — never overwrite existing rendered output.
        rest = body[j:]
        nxt = re.search(r"\n#{1,2} ", rest)
        existing = rest[:nxt.start()] if nxt else rest
        if existing.strip():
            return None
        return body[:j] + "\n\n" + content + "\n" + rest[len(existing):]

    for heading, content in ((APPS_HEADING, apps), (LOGS_HEADING, logs)):
        if heading not in text:
            return "missing heading %s" % heading
        out = put(text, heading, content)
        if out is None:
            return "already filled (%s) — left untouched" % heading
        text = out

    if not dry:
        with open(note_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dates", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for d in args.dates:
        day = dt.date.fromisoformat(d)
        note = os.path.join(NOTE_DIR, "%s.md" % d)
        if not os.path.exists(note):
            print("  %s: no daily note" % d); continue
        apps, logs = render(day)
        if apps is None:
            print("  %s: no export folder" % d); continue
        problem = fill(note, apps, logs, args.dry_run)
        print("  %s: %s (%d table rows, %d log lines)"
              % (d, problem or ("would fill" if args.dry_run else "FILLED"),
                 apps.count("\n") - 1, logs.count("\n") + 1 if logs else 0))


if __name__ == "__main__":
    main()
