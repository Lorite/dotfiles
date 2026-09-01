#!/usr/bin/env python3
"""List video notes whose AI Summary or Flashcards section is still empty.

The headless clipper cannot fill those two sections: they are `{{"prompt"}}` interpreter
variables in the Web Clipper template, executed by the browser extension's LLM, and
`obsidian-clipper-cli` has no interpreter. So every note clipped headlessly (and every
one captured from the phone) arrives with both sections blank, while notes clipped in
the browser have them filled.

This is the shared definition of "pending" used by both `video_note_summary.sh` (to skip
the nightly LLM run when there is nothing to do) and the `lorite-video-note-summary`
skill (to pick what to work on). Keeping it in one place stops the two disagreeing.

    ./video-notes-pending.py                 # paths, one per line, oldest first
    ./video-notes-pending.py --count         # just the number
    ./video-notes-pending.py --verbose       # what each note is missing, and its source
    ./video-notes-pending.py --limit 5       # cap the list
"""
import argparse
import os
import re
import sys

VAULT = os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/git/lorite-obsidian-notes"))
VIDEO_DIR = os.path.join(VAULT, "media", "videos")

# A card is any line carrying one of the plugin's separators or a cloze. `?`/`??` alone on
# a line are the multi-line separators, so they count too.
CARD_RE = re.compile(r"(::|==.+==|^\?\??$)", re.M)

# A section holding fewer real words than this is treated as blank. Filled sections run to
# hundreds of words, so the gap is wide and the exact value is not delicate.
MIN_SECTION_WORDS = 15


def section(note, heading):
    """Text between `heading` and the next heading of the same or higher level, or a rule."""
    m = re.search(r"^%s[ \t]*$" % re.escape(heading), note, re.M)
    if not m:
        return None
    rest = note[m.end():]
    level = len(heading) - len(heading.lstrip("#"))
    stop = re.search(r"^(#{1,%d}[ \t]|---[ \t]*$)" % level, rest, re.M)
    return rest[:stop.start()] if stop else rest


def transcript_len(note):
    body = section(note, "# Transcript")
    return len(body.split()) if body else 0


def about_len(note):
    body = section(note, "# About")
    return len(body.split()) if body else 0


def inspect(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        note = fh.read()
    summary = section(note, "# AI Summary")
    cards = section(note, "## Flashcards")
    missing = []
    # Pending means EMPTY, not "structured differently".
    #
    # This originally tested for the template's "## Summary" subheading, on the premise
    # that a filled section always has it. Wrong: notes predating the current template
    # carry real summaries (518 and 638 words in the two that tripped it) pasted in from
    # elsewhere, with no such subheading. The headless run refused to overwrite them,
    # correctly, since rewriting published prose to satisfy a formatting technicality is
    # exactly what the vault's never-rewrite policy forbids. Word count is the honest
    # signal: an unfilled section is literally blank.
    if summary is not None and len(summary.split()) < MIN_SECTION_WORDS:
        missing.append("summary")
    if cards is not None and not CARD_RE.search(cards):
        missing.append("flashcards")
    return missing, transcript_len(note), about_len(note)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-words", type=int, default=200,
                    help="skip notes with less source text than this (default: 200)")
    args = ap.parse_args()

    if not os.path.isdir(VIDEO_DIR):
        print("no %s" % VIDEO_DIR, file=sys.stderr)
        return 0

    rows = []
    skipped = 0
    for name in sorted(os.listdir(VIDEO_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(VIDEO_DIR, name)
        try:
            missing, tw, aw = inspect(path)
        except OSError:
            continue
        if not missing:
            continue
        # Without enough source text an LLM would be inventing rather than summarizing,
        # so those notes are reported as skipped rather than silently queued forever.
        if max(tw, aw) < args.min_words:
            skipped += 1
            continue
        rows.append((path, missing, "transcript" if tw >= aw else "description", max(tw, aw)))

    rows.sort(key=lambda r: os.path.getmtime(r[0]))
    if args.limit:
        rows = rows[:args.limit]

    if args.count:
        print(len(rows))
        return 0
    for path, missing, src, words in rows:
        if args.verbose:
            print("%-6s %5d words  missing: %-20s %s"
                  % (src, words, ",".join(missing), os.path.relpath(path, VAULT)))
        else:
            print(path)
    if args.verbose and skipped:
        print("\n%d note(s) skipped: under %d words of source text (nothing to summarize from)."
              % (skipped, args.min_words), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
