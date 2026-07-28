#!/usr/bin/env python3
"""Watch the vault capture inbox and enrich URL stubs into full Obsidian notes.

The phone side (Automate) only has to write a tiny file into a Syncthing-synced folder:

    <vault>/ai_chats/inbox/capture-<anything>.md   containing a URL on any line

This watcher picks the stub up, clips the URL headlessly (youtube-enrich.py for YouTube,
obsidian-clipper-cli for everything else), files the note where the matched template's
`path` says (media/videos, media/websites, ...), and moves the stub to processed/ (or
failed/ with a .reason file). Idempotent and safe to run from a timer.

Transport rationale: a synced *file* needs no server endpoint, no auth secret on the
phone, and works offline — the capture just arrives when Syncthing next connects. The
cost is latency (seconds on the same network, longer offline), which is fine: capture is
fire-and-forget, the enriched note is read later.

Usage:
    ./inbox-watcher.py            # process everything currently in the inbox
    ./inbox-watcher.py --dry-run  # say what would happen
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

VAULT = os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/git/lorite-obsidian-notes"))
INBOX = os.path.join(VAULT, "ai_chats", "inbox")
TEMPLATES = os.path.expanduser("~/.config/obsidian-clipper-cli/templates")
PROPERTY_TYPES = os.path.expanduser("~/.config/obsidian-clipper-cli/property-types.json")
HERE = os.path.dirname(os.path.abspath(__file__))
CLIPPER = os.path.expanduser("~/.local/bin/obsidian-clipper-cli")
YT_ENRICH = os.path.join(HERE, "youtube-enrich.py")

URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+")
YOUTUBE_RE = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)")
STUB_EXTS = (".md", ".txt", ".url")
# Where notes go when the matched template couldn't be determined.
FALLBACK_DIR = "media/websites"


def find_url(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        m = URL_RE.search(fh.read())
    return m.group(0).rstrip(".,;") if m else None


def frontmatter(note):
    """Tiny YAML-subset parser: top-level `key: value` pairs only — all we need."""
    if not note.startswith("---\n"):
        return {}
    end = note.find("\n---\n", 4)
    if end == -1:
        return {}
    fields = {}
    for line in note[4:end].split("\n"):
        m = re.match(r'^([A-Za-z0-9_-]+):\s*"?(.*?)"?\s*$', line)
        if m and m.group(2):
            fields[m.group(1)] = m.group(2)
    return fields


def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|]', "-", name).strip(" .-")
    return name[:180] or "capture"


def note_filename(fields, template_dir):
    """Approximate the template's noteNameFormat from the rendered frontmatter.

    The real formats use selectors and filters we cannot re-run here, so this mirrors the
    two conventions that matter: videos are '<date> VIDEO <channel> - <title>', everything
    else is '<title> - <author>' (or just '<title>').
    """
    title = fields.get("title") or fields.get("name") or "capture"
    if template_dir == "media/videos":
        parts = [fields.get("published", ""), "VIDEO", fields.get("channel", ""), "-", title]
        return safe_name(" ".join(p for p in parts if p))
    author = fields.get("author", "")
    author = re.sub(r"[\[\]\"']", "", author).strip()
    return safe_name("%s - %s" % (title, author) if author else title)


def default_template():
    """The extension's no-trigger fallback ('Website Default') never matches in the CLI:
    matchTemplate only considers URL/schema triggers, and errors when none match. Find it
    by name so a plain article URL still clips."""
    for f in sorted(os.listdir(TEMPLATES)):
        if "website-default" in f:
            return os.path.join(TEMPLATES, f)
    return None


def run_clipper(url, template_path):
    cmd = [CLIPPER, url, "-t", template_path]
    if os.path.exists(PROPERTY_TYPES):
        cmd += ["--property-types", PROPERTY_TYPES]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def clip_generic(url):
    """Run the clipper CLI; return (note_text, template_target_dir or None)."""
    proc = run_clipper(url, TEMPLATES)
    if proc.returncode == 0 and proc.stdout.strip():
        target = None
        m = re.search(r"Matched template: (.*\.json)", proc.stderr or "")
        if m and os.path.exists(m.group(1)):
            target = json.load(open(m.group(1))).get("path") or None
        return proc.stdout, target
    if "No template matched" in (proc.stderr or ""):
        fallback = default_template()
        if fallback:
            proc = run_clipper(url, fallback)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout, json.load(open(fallback)).get("path") or None
    raise RuntimeError("clipper failed: %s" % (proc.stderr.strip()[-400:] or "no output"))


def clip_youtube(url):
    proc = subprocess.run([YT_ENRICH, url], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError("youtube-enrich failed: %s" % (proc.stderr.strip()[-400:] or "no output"))
    return proc.stdout, "media/videos"


def unique_path(directory, base):
    path = os.path.join(directory, base + ".md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(directory, "%s (%d).md" % (base, n))
        n += 1
    return path


def process(stub, dry):
    url = find_url(stub)
    if not url:
        raise RuntimeError("no URL found in stub")
    if YOUTUBE_RE.search(url):
        note, target = clip_youtube(url)
    else:
        note, target = clip_generic(url)
    target = target or FALLBACK_DIR
    dest_dir = os.path.join(VAULT, target)
    fields = frontmatter(note)
    dest = unique_path(dest_dir, note_filename(fields, target))
    if dry:
        return url, dest
    os.makedirs(dest_dir, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(note)
    return url, dest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(INBOX):
        os.makedirs(os.path.join(INBOX, "processed"), exist_ok=True)
        os.makedirs(os.path.join(INBOX, "failed"), exist_ok=True)
        print("Created %s — nothing to process yet." % INBOX)
        return

    processed_dir = os.path.join(INBOX, "processed")
    failed_dir = os.path.join(INBOX, "failed")
    stubs = sorted(
        os.path.join(INBOX, f) for f in os.listdir(INBOX)
        if f.lower().endswith(STUB_EXTS) and os.path.isfile(os.path.join(INBOX, f))
    )
    if not stubs:
        return

    ok = err = 0
    for stub in stubs:
        name = os.path.basename(stub)
        try:
            url, dest = process(stub, args.dry_run)
            ok += 1
            print("✓ %s\n    %s\n    -> %s" % (name, url, os.path.relpath(dest, VAULT)))
            if not args.dry_run:
                os.makedirs(processed_dir, exist_ok=True)
                shutil.move(stub, os.path.join(processed_dir, name))
        except Exception as exc:
            err += 1
            print("✗ %s: %s" % (name, exc), file=sys.stderr)
            if not args.dry_run:
                os.makedirs(failed_dir, exist_ok=True)
                shutil.move(stub, os.path.join(failed_dir, name))
                with open(os.path.join(failed_dir, name + ".reason"), "w") as fh:
                    fh.write("%s\n%s\n" % (datetime.datetime.now().isoformat(), exc))
    print("done: %d ok, %d failed%s" % (ok, err, " (dry run)" if args.dry_run else ""))
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
