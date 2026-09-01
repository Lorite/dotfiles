#!/usr/bin/env python3
"""Turn substantially-watched YouTube videos into capture stubs for the inbox watcher.

The clipping half of this pipeline is already solved: `youtube-enrich.py` renders a full
Obsidian note from a URL, and `inbox-watcher.py` picks any URL-bearing stub out of
<vault>/ai_chats/inbox/ and files the result under media/videos. What was missing is
DISCOVERY: nothing told the pipeline which videos were actually watched, so the only
trigger was a manual capture from the phone.

This fills that gap from ActivityWatch, which already records every YouTube tab with its
URL, title and dwell time. Note there is no alternative here rather than a preference:
the YouTube Data API deprecated the watch-history playlist in 2016 and exposes no OAuth
scope for history at all, so the official API cannot answer "what did I watch". Google
Takeout can, but only in periodic manual exports and WITHOUT watch duration, which is the
one signal that separates a talk worth a note from a music video left playing.

Dwell is intersected with the afk watcher, so a tab left open overnight does not qualify.

    ./aw-youtube-capture.py --dry-run          # show what would be captured
    ./aw-youtube-capture.py --days 7           # look back a week
    ./aw-youtube-capture.py --min-minutes 10   # only longer watches

Idempotent: every candidate is checked against the notes already in media/videos and the
stubs already in the inbox (including processed/ and failed/), so re-running captures
nothing twice and a failed clip is not retried in a loop.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

VAULT = os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/git/lorite-obsidian-notes"))
INBOX = os.path.join(VAULT, "ai_chats", "inbox")
VIDEO_DIR = os.path.join(VAULT, "media", "videos")
AW_SERVER = os.environ.get("AW_SERVER", "http://localhost:5600")

# The 11-character id is the dedup key: the same video reaches us as watch?v=, youtu.be/
# and /shorts/, with tracking parameters attached, and those must not become three notes.
ID_RES = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
)


def video_id(url):
    for rx in ID_RES:
        m = rx.search(url)
        if m:
            return m.group(1)
    return None


def aw_get(path):
    with urllib.request.urlopen(AW_SERVER + path, timeout=10) as r:
        return json.load(r)


def aw_query(timeperiod, statements):
    body = json.dumps({"timeperiods": [timeperiod], "query": statements}).encode()
    req = urllib.request.Request(
        AW_SERVER + "/api/0/query/", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)[0]


def collect(days):
    """Aggregate afk-filtered dwell per video id across every browser bucket on this host."""
    buckets = aw_get("/api/0/buckets/")
    web = sorted(b for b in buckets if b.startswith("aw-watcher-web-"))
    afk = sorted(b for b in buckets if b.startswith("aw-watcher-afk_"))
    if not web:
        return None, "no aw-watcher-web-* buckets on %s" % AW_SERVER

    end = datetime.datetime.now().astimezone()
    start = end - datetime.timedelta(days=days)
    period = "%s/%s" % (start.isoformat(), end.isoformat())

    seen = {}
    for bucket in web:
        stmts = ['web = flood(query_bucket("%s"));' % bucket]
        if afk:
            # Without this, a YouTube tab left focused while the machine is idle counts
            # its whole idle stretch as watch time and trips any threshold.
            stmts = [
                'afk = flood(query_bucket("%s"));' % afk[0],
                'not_afk = filter_keyvals(afk, "status", ["not-afk"]);',
            ] + stmts + ["web = filter_period_intersect(web, not_afk);"]
        stmts.append("RETURN = web;")
        try:
            events = aw_query(period, stmts)
        except Exception as exc:  # one bad bucket must not lose the others
            print("warning: query failed for %s: %s" % (bucket, exc), file=sys.stderr)
            continue
        for e in events:
            url = e.get("data", {}).get("url", "")
            vid = video_id(url) if "youtube.com" in url or "youtu.be" in url else None
            if not vid:
                continue
            rec = seen.setdefault(vid, {"seconds": 0.0, "title": "", "url": ""})
            rec["seconds"] += e.get("duration", 0.0)
            title = (e.get("data", {}).get("title") or "").strip()
            if len(title) > len(rec["title"]):
                rec["title"] = title
            rec["url"] = "https://www.youtube.com/watch?v=%s" % vid
    return seen, None


def known_ids():
    """Video ids already represented by a note or by a stub, in any inbox state."""
    ids = set()
    if os.path.isdir(VIDEO_DIR):
        for name in os.listdir(VIDEO_DIR):
            if not name.endswith(".md"):
                continue
            try:
                with open(os.path.join(VIDEO_DIR, name), encoding="utf-8", errors="replace") as fh:
                    head = fh.read(2000)
            except OSError:
                continue
            for line in head.split("\n"):
                if line.startswith("url:"):
                    vid = video_id(line)
                    if vid:
                        ids.add(vid)
                    break
    for sub in ("", "processed", "failed"):
        d = os.path.join(INBOX, sub) if sub else INBOX
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            path = os.path.join(d, name)
            if not os.path.isfile(path) or not name.lower().endswith((".md", ".txt", ".url")):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    vid = video_id(fh.read(2000))
            except OSError:
                continue
            if vid:
                ids.add(vid)
    return ids


def clean_title(title):
    """Browser tab titles carry an unread count and a site suffix; neither is the title."""
    title = re.sub(r"^\(\d+\)\s*", "", title)
    return re.sub(r"\s*-\s*YouTube\s*$", "", title).strip()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--days", type=float, default=2.0, help="look-back window (default: 2)")
    ap.add_argument("--min-minutes", type=float, default=5.0,
                    help="minimum afk-filtered dwell to qualify (default: 5)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        seen, err = collect(args.days)
    except (urllib.error.URLError, OSError) as exc:
        # A timer must not go red because ActivityWatch happens to be down.
        print("ActivityWatch not reachable at %s (%s) — nothing captured." % (AW_SERVER, exc),
              file=sys.stderr)
        return 0
    if err:
        print(err, file=sys.stderr)
        return 0

    known = known_ids()
    threshold = args.min_minutes * 60
    candidates = sorted(
        ((v, r) for v, r in seen.items() if r["seconds"] >= threshold),
        key=lambda kv: -kv[1]["seconds"],
    )
    below = len(seen) - len(candidates)
    fresh = [(v, r) for v, r in candidates if v not in known]

    print("%d distinct video(s) in the last %g day(s); %d below %g min, %d already known."
          % (len(seen), args.days, below, args.min_minutes, len(candidates) - len(fresh)))
    if not fresh:
        print("nothing new to capture.")
        return 0

    if not args.dry_run:
        os.makedirs(INBOX, exist_ok=True)
    for vid, rec in fresh:
        stub = os.path.join(INBOX, "capture-yt-%s.md" % vid)
        title = clean_title(rec["title"]) or "(title unknown)"
        body = (
            "%s\n\n"
            "<!-- captured from ActivityWatch on %s\n"
            "     watched %.1f min (afk-filtered) | %s -->\n"
            % (rec["url"], datetime.date.today().isoformat(), rec["seconds"] / 60.0, title)
        )
        print("%s  %5.1f min  %s" % ("would capture" if args.dry_run else "captured    ",
                                     rec["seconds"] / 60.0, title[:70]))
        if not args.dry_run:
            with open(stub, "w", encoding="utf-8") as fh:
                fh.write(body)
    print("%d stub(s) %s in %s"
          % (len(fresh), "would be written" if args.dry_run else "written",
             os.path.relpath(INBOX, VAULT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
