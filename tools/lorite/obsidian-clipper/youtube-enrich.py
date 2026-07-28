#!/usr/bin/env python3
"""Clip a YouTube video into a full Obsidian note: obsidian-clipper + yt-dlp.

The headless CLI alone is not enough for YouTube. The page's JSON-LD (all a plain
fetch sees, since the CLI runs no JavaScript) contains only name / thumbnailUrl /
uploadDate — no embedUrl, author or duration — so the template's `url`, `channel` and
`duration` come out EMPTY. And `{{transcript}}` is a browser-extension variable that
does not exist in the CLI at all, so the Transcript section renders blank.

So: let obsidian-clipper build the note from your real template (frontmatter, headings,
description, the AI-summary prompt), then fill the gaps from yt-dlp.

    ./youtube-enrich.py <url> [-o note.md] [--lang en] [--no-transcript]

Requires: yt-dlp, and obsidian-clipper-cli built by ./build-cli.sh.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CLIPPER = os.path.expanduser("~/.local/bin/obsidian-clipper-cli")
TEMPLATES = os.path.expanduser("~/.config/obsidian-clipper-cli/templates")
PROPERTY_TYPES = os.path.expanduser("~/.config/obsidian-clipper-cli/property-types.json")
# Frontmatter keys the CLI cannot fill from YouTube's JSON-LD, mapped to yt-dlp fields.
GAP_FIELDS = {"url": "webpage_url", "channel": "channel", "duration": "duration_string"}


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe(url):
    try:
        out = run(["yt-dlp", "--skip-download", "--dump-json", url]).stdout
    except subprocess.CalledProcessError as exc:
        # Private/removed/age-gated videos land here. Report yt-dlp's own message rather
        # than a Python traceback — this runs unattended in the capture pipeline.
        msg = (exc.stderr or "").strip().split("\n")[-1] if exc.stderr else "yt-dlp failed"
        sys.exit("yt-dlp could not read %s\n  %s" % (url, msg))
    return json.loads(out)


def fetch_transcript(url, lang, workdir):
    """Return the subtitle track as '[mm:ss](url&t=Ns) text' lines, or None."""
    base = os.path.join(workdir, "sub")
    for flag in ("--write-subs", "--write-auto-subs"):
        try:
            run(["yt-dlp", "--skip-download", flag, "--sub-langs", lang,
                 "--sub-format", "vtt", "-o", base, url])
        except subprocess.CalledProcessError:
            continue
        files = glob.glob(base + "*.vtt")
        if files:
            return parse_vtt(files[0], url)
    return None


TIMESTAMP = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.\d{3}\s+-->")
TAGS = re.compile(r"<[^>]+>")


def parse_vtt(path, url):
    """VTT -> deduped, timestamped lines.

    Auto-captions roll: each cue repeats the previous line plus a new word, so a naive
    dump is several times longer than the real transcript and useless to an LLM. Emit a
    line only when its text differs from the last one kept.
    """
    lines, seconds, last = [], None, None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.rstrip("\n")
            m = TIMESTAMP.match(raw)
            if m:
                h, mi, s = (int(x) for x in m.groups())
                seconds = h * 3600 + mi * 60 + s
                continue
            if not raw or raw.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                continue
            text = TAGS.sub("", raw).strip()
            if not text or text == last or seconds is None:
                continue
            last = text
            stamp = "%d:%02d" % (seconds // 60, seconds % 60)
            sep = "&" if "?" in url else "?"
            lines.append("[%s](%s%st=%d) %s" % (stamp, url, sep, seconds, text))
    return "\n".join(lines) if lines else None


def clip(url):
    cmd = [CLIPPER, url, "-t", TEMPLATES]
    if os.path.exists(PROPERTY_TYPES):
        cmd += ["--property-types", PROPERTY_TYPES]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.exit("obsidian-clipper failed:\n" + (proc.stderr or "(no output)"))
    return proc.stdout


def fill_frontmatter(note, meta):
    """Fill only frontmatter keys that rendered empty. Never overwrite a real value."""
    if not note.startswith("---\n"):
        return note, []
    end = note.find("\n---\n", 4)
    if end == -1:
        return note, []
    head, body = note[4:end], note[end:]
    channel = meta.get("channel")
    filled = []
    out = []
    for line in head.split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*$", line)
        if m and m.group(1) in GAP_FIELDS:
            value = meta.get(GAP_FIELDS[m.group(1)])
            if value:
                out.append('%s: "%s"' % (m.group(1), str(value).replace('"', "'")))
                filled.append(m.group(1))
                continue
        # The alias is built as "{{author}} — {{name}}", and author is empty for the same
        # reason `channel` is, so every note would start its alias with a dangling "— ".
        # Repair it with the channel we just resolved.
        dangling = re.match(r'^(\s*-\s*)"—\s*(.*)"\s*$', line)
        if dangling and channel:
            out.append('%s"%s — %s"' % (dangling.group(1), channel, dangling.group(2)))
            if "aliases" not in filled:
                filled.append("aliases")
            continue
        out.append(line)
    return "---\n" + "\n".join(out) + body, filled


def insert_transcript(note, transcript):
    """Put the transcript under the template's own '# Transcript' heading."""
    marker = "\n# Transcript\n"
    idx = note.find(marker)
    if idx == -1:
        return note.rstrip() + "\n\n# Transcript\n\n" + transcript + "\n", True
    cut = idx + len(marker)
    return note[:cut] + "\n" + transcript + "\n" + note[cut:].lstrip("\n"), True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("-o", "--output", help="write to this .md file (default: stdout)")
    ap.add_argument("--lang", default="en", help="subtitle language (default: en)")
    ap.add_argument("--no-transcript", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(CLIPPER):
        sys.exit("%s not found — run ./build-cli.sh first." % CLIPPER)
    if not shutil.which("yt-dlp"):
        sys.exit("yt-dlp not found.")

    note = clip(args.url)
    meta = probe(args.url)
    note, filled = fill_frontmatter(note, meta)

    got_transcript = False
    if not args.no_transcript:
        workdir = tempfile.mkdtemp(prefix="yt-enrich-")
        try:
            transcript = fetch_transcript(args.url, args.lang, workdir)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        if transcript:
            note, got_transcript = insert_transcript(note, transcript)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(note)
        print("Wrote %s" % args.output, file=sys.stderr)
    else:
        sys.stdout.write(note)

    print("Filled from yt-dlp: %s | transcript: %s"
          % (", ".join(filled) or "(none)", "yes" if got_transcript else "NO"), file=sys.stderr)


if __name__ == "__main__":
    main()
