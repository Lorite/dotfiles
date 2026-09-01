#!/usr/bin/env python3
"""Turn substantially-watched YouTube videos, on laptop OR phone, into capture stubs.

The clipping half of this pipeline is already solved: `youtube-enrich.py` renders a full
Obsidian note from a URL, and `inbox-watcher.py` picks any URL-bearing stub out of
<vault>/ai_chats/inbox/ and files the result under media/videos. What was missing is
DISCOVERY: nothing told the pipeline which videos were actually watched.

There is no API alternative here rather than a preference: the YouTube Data API
deprecated the watch-history playlist in 2016 and exposes no OAuth scope for history at
all. Google Takeout can export history, but only in periodic manual batches and WITHOUT
watch duration, which is the one signal that separates a talk worth a note from a music
video left playing.

## Which buckets, and why each

ActivityWatch records the same viewing three different ways, and no single bucket is
enough:

- **`currently-playing`** (laptop `aw-watcher-media-player`) knows real PLAYBACK time but
  only carries a title, no URL.
- **`media.playback`** (`aw-watcher-android-media`, synced from the phone) likewise: app,
  title, channel in `artist`, and a `state`, but no URL. This is the only source of phone
  viewing at all, and it is substantial.
- **`web.tab.current`** (`aw-watcher-web-*`) is the only source of URLs, but it measures
  TAB FOCUS, not playback, so a video playing while you work elsewhere is invisible to it.

So playback time comes from the media buckets and the URL comes from the web buckets,
matched by title. Measured on real data: the same talk was 15.1 min of tab dwell and
31.3 min of actual playback, and the single most-watched video on the phone (47.8 min)
had no web-bucket presence whatsoever.

Buckets are matched by TYPE, never by name, so this works unchanged on the laptop and on
the home server, where every bucket arrives suffixed `-synced-from-<host>`. Run it on the
home server: that is the only machine that sees the phone's buckets as well as the
laptop's.

## afk filtering: yes for tabs, no for playback

Tab dwell is intersected with the afk watcher, or a tab left open overnight would qualify.
Playback is deliberately NOT afk-filtered: watching a video involves no keyboard input, so
afk filtering discards exactly the viewing we are looking for. Measured: it cut one talk
from 37.6 to 23.8 minutes.

    ./aw-youtube-capture.py --dry-run          # show what would be captured
    ./aw-youtube-capture.py --days 7           # look back a week
    ./aw-youtube-capture.py --min-minutes 10   # only longer watches
    ./aw-youtube-capture.py --no-search        # never resolve a title via yt-dlp

Idempotent: every candidate is checked against the notes already in media/videos and the
stubs already in the inbox (including processed/ and failed/), so re-running captures
nothing twice and a failed clip is not retried in a loop.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request

VAULT = os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/git/lorite-obsidian-notes"))
INBOX = os.path.join(VAULT, "ai_chats", "inbox")
VIDEO_DIR = os.path.join(VAULT, "media", "videos")
AW_SERVER = os.environ.get("AW_SERVER", "http://localhost:5600")

BROWSER_PLAYERS = {"brave", "chrome", "chromium", "firefox", "vivaldi", "edge"}
# Placeholder the media watcher emits when a page plays media it cannot name.
JUNK_TITLES = {"", "a site is playing media"}

ID_RES = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
)


def video_id(text):
    for rx in ID_RES:
        m = rx.search(text or "")
        if m:
            return m.group(1)
    return None


def norm(s):
    """Casefold, strip accents and punctuation, collapse spaces. For title comparison."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"^\(\d+\)\s*", "", s)
    s = re.sub(r"\s*-\s*YouTube\s*$", "", s, flags=re.I)
    s = re.sub(r"[^\w\s]", " ", s.casefold())
    return re.sub(r"\s+", " ", s).strip()


def aw_get(path):
    with urllib.request.urlopen(AW_SERVER + path, timeout=15) as r:
        return json.load(r)


def aw_query(period, statements):
    body = json.dumps({"timeperiods": [period], "query": statements}).encode()
    req = urllib.request.Request(AW_SERVER + "/api/0/query/", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)[0]


def buckets_by_type(buckets, *types):
    return sorted(k for k, v in buckets.items() if v.get("type") in types)


def events(bucket, period, afk_bucket=None):
    """Raw events, optionally intersected with not-afk. Never raises for one bad bucket."""
    stmts = ['b = flood(query_bucket("%s"));' % bucket]
    if afk_bucket:
        stmts = ['afk = flood(query_bucket("%s"));' % afk_bucket,
                 'na = filter_keyvals(afk, "status", ["not-afk"]);'] + stmts + \
                ["b = filter_period_intersect(b, na);"]
    stmts.append("RETURN = b;")
    try:
        return aw_query(period, stmts)
    except Exception as exc:
        print("warning: query failed for %s: %s" % (bucket, exc), file=sys.stderr)
        return []


def collect(days):
    """Return {normalized_title: {...}} of YouTube playback, and a title -> video id index."""
    buckets = aw_get("/api/0/buckets/")
    end = datetime.datetime.now().astimezone()
    period = "%s/%s" % ((end - datetime.timedelta(days=days)).isoformat(), end.isoformat())

    plays = {}

    def add(title, seconds, channel, source):
        key = norm(title)
        if not key or key in JUNK_TITLES:
            return
        rec = plays.setdefault(key, {"seconds": 0.0, "title": title, "channel": "",
                                     "sources": set()})
        rec["seconds"] += seconds
        rec["sources"].add(source)
        if channel and not rec["channel"]:
            rec["channel"] = channel
        if len(title) > len(rec["title"]):
            rec["title"] = title

    # 1. Laptop browser playback. NOT afk-filtered, on purpose (see module docstring).
    for b in buckets_by_type(buckets, "currently-playing"):
        for e in events(b, period):
            d = e.get("data", {})
            if (d.get("player") or "").casefold() not in BROWSER_PLAYERS:
                continue        # VLC and friends are local files, not YouTube
            add(d.get("title", ""), e.get("duration", 0.0), "", "laptop")

    # 2. Phone playback. Only `playing` counts: the watcher also emits paused, stopped and
    #    buffering events with real durations, and none of those are watching.
    for b in buckets_by_type(buckets, "media.playback"):
        for e in events(b, period):
            d = e.get("data", {})
            if d.get("app") != "YouTube" or d.get("state") != "playing":
                continue
            add(d.get("title", ""), e.get("duration", 0.0), d.get("artist", ""), "phone")

    # 3. URL index from every web bucket. Tab focus is the wrong duration signal but the
    #    only place a URL appears, so these are used purely to resolve title -> id.
    afk = (buckets_by_type(buckets, "afkstatus") or [None])[0]
    index = {}
    for b in buckets_by_type(buckets, "web.tab.current"):
        for e in events(b, period, afk_bucket=afk):
            d = e.get("data", {})
            vid = video_id(d.get("url", ""))
            if vid:
                index.setdefault(norm(d.get("title", "")), vid)
    return plays, index


def search_youtube(title, channel):
    """Resolve a title to a video id via yt-dlp, or None when the match is not convincing.

    Only ever used for phone viewing, where no URL exists anywhere. The guard matters more
    than the lookup: a confidently wrong video would file a note about something the user
    never watched, which is worse than filing nothing.
    """
    query = ("%s %s" % (title, channel)).strip()
    try:
        out = subprocess.run(["yt-dlp", "--skip-download", "--dump-json", "--no-warnings",
                              "ytsearch1:" + query],
                             capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        meta = json.loads(out.stdout.splitlines()[0])
    except ValueError:
        return None

    got_title, got_channel = norm(meta.get("title", "")), norm(meta.get("channel", ""))
    want_title, want_channel = norm(title), norm(channel)

    # The phone reports a shortened title ("Why Robotics Still Isn't Solved - But Could Be
    # Soon" for "... | YC Paper Club"), and sometimes a differently-worded one, so exact
    # equality is too strict. Require instead that every word we saw appears in the real
    # title, which holds for both of those and fails for an unrelated video.
    tokens_ok = want_title and set(want_title.split()) <= set(got_title.split())
    if want_channel:
        return meta.get("id") if (tokens_ok and want_channel == got_channel) else None
    # With no channel to corroborate, demand the stronger title match.
    return meta.get("id") if want_title and want_title == got_title else None


CHANNELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "video-capture-channels.json")


def load_channels():
    """Read the allow/deny lists. A missing file means capture nothing but report all."""
    try:
        with open(CHANNELS_FILE, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        print("warning: %s unreadable (%s), treating every channel as unknown"
              % (CHANNELS_FILE, exc), file=sys.stderr)
        cfg = {}
    return ({norm(c) for c in cfg.get("allow", [])},
            {norm(c) for c in cfg.get("deny", [])},
            cfg.get("default_for_unknown", "report"))


_CHANNEL_CACHE = {}


def channel_for_id(vid):
    """Channel name for a video id, via yt-dlp. Cached; empty string when unavailable.

    The laptop's `currently-playing` bucket carries no channel at all, so laptop viewing
    would otherwise always land in the unknown bucket and never be capturable. The URL is
    already known by then, so one metadata lookup recovers what the gate needs.
    """
    if vid in _CHANNEL_CACHE:
        return _CHANNEL_CACHE[vid]
    ch = ""
    try:
        out = subprocess.run(
            ["yt-dlp", "--skip-download", "--dump-json", "--no-warnings",
             "https://www.youtube.com/watch?v=" + vid],
            capture_output=True, text=True, timeout=90)
        if out.returncode == 0 and out.stdout.strip():
            ch = json.loads(out.stdout.splitlines()[0]).get("channel") or ""
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    _CHANNEL_CACHE[vid] = ch
    return ch


def known_ids():
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=float, default=2.0, help="look-back window (default: 2)")
    ap.add_argument("--min-minutes", type=float, default=2.0,
                    help="floor to drop accidental plays (default: 2). The channel\n                          lists do the real filtering, since a 3-minute Fireship video\n                          deserves a note and a 40-minute stream does not")
    ap.add_argument("--limit", type=int, default=10,
                    help="max stubs to write per run (default: 10)")
    ap.add_argument("--no-search", action="store_true",
                    help="never resolve a title with yt-dlp; web-bucket URLs only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        plays, index = collect(args.days)
    except (urllib.error.URLError, OSError) as exc:
        # A nightly job must not go red because ActivityWatch happens to be down.
        print("ActivityWatch not reachable at %s (%s), nothing captured." % (AW_SERVER, exc),
              file=sys.stderr)
        return 0

    threshold = args.min_minutes * 60
    over = sorted(((k, r) for k, r in plays.items() if r["seconds"] >= threshold),
                  key=lambda kv: -kv[1]["seconds"])
    known = known_ids()

    print("%d distinct video(s) played in the last %g day(s); %d over %g min."
          % (len(plays), args.days, len(over), args.min_minutes))

    allow, deny, default_unknown = load_channels()
    fresh, unresolved, dupes = [], [], 0
    denied, unknown = [], {}
    for key, rec in over:
        # Gate on the channel before resolving, so a denied video (always from the phone,
        # which does report a channel) never costs a lookup. Laptop playback reports no
        # channel, so for those the URL is resolved first and the channel recovered from it.
        vid = index.get(key)
        if not rec["channel"] and vid and not args.no_search:
            rec["channel"] = channel_for_id(vid)
        ch = norm(rec["channel"])
        if ch and ch in deny:
            denied.append(rec)
            continue
        if not ch or ch not in allow:
            label = rec["channel"] or "(no channel reported)"
            slot = unknown.setdefault(label, {"seconds": 0.0, "titles": []})
            slot["seconds"] += rec["seconds"]
            if len(slot["titles"]) < 2:
                slot["titles"].append(rec["title"])
            if default_unknown != "capture":
                continue
        how = "web-bucket"
        if not vid and not args.no_search:
            vid = search_youtube(rec["title"], rec["channel"])
            how = "yt-dlp search"
        if not vid:
            unresolved.append(rec)
            continue
        if vid in known:
            dupes += 1
            continue
        rec["_id"], rec["_how"] = vid, how
        fresh.append(rec)
        known.add(vid)          # guard against two titles resolving to the same video
        if len(fresh) >= args.limit:
            break

    print("  %d on denied channels (already in the Day Log, no note), %d already captured, "
          "%d unresolvable, %d to write."
          % (len(denied), dupes, len(unresolved), len(fresh)))
    if unknown:
        print("\n  new channels seen, neither allowed nor denied. Add each to the \"allow\" or")
        print("  \"deny\" list in video-capture-channels.json:")
        for ch, d in sorted(unknown.items(), key=lambda kv: -kv[1]["seconds"]):
            print("     %6.1f min  %-28s e.g. %s" % (d["seconds"] / 60, ch[:28], d["titles"][0][:44]))
        print()
    for rec in unresolved:
        print("     unresolved: %5.1f min  %s%s"
              % (rec["seconds"] / 60, rec["title"][:60],
                 " [%s]" % rec["channel"] if rec["channel"] else ""))

    if not fresh:
        print("nothing new to capture.")
        return 0

    if not args.dry_run:
        os.makedirs(INBOX, exist_ok=True)
    for rec in fresh:
        vid = rec["_id"]
        stub = os.path.join(INBOX, "capture-yt-%s.md" % vid)
        body = ("https://www.youtube.com/watch?v=%s\n\n"
                "<!-- captured from ActivityWatch on %s\n"
                "     played %.1f min on %s | resolved via %s\n"
                "     %s%s -->\n"
                % (vid, datetime.date.today().isoformat(), rec["seconds"] / 60,
                   "+".join(sorted(rec["sources"])), rec["_how"], rec["title"],
                   " [%s]" % rec["channel"] if rec["channel"] else ""))
        print("%s %5.1f min  %-6s  %s"
              % ("would capture" if args.dry_run else "captured    ",
                 rec["seconds"] / 60, "+".join(sorted(rec["sources"])), rec["title"][:58]))
        if not args.dry_run:
            with open(stub, "w", encoding="utf-8") as fh:
                fh.write(body)
    print("%d stub(s) %s in %s"
          % (len(fresh), "would be written" if args.dry_run else "written",
             os.path.relpath(INBOX, VAULT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
