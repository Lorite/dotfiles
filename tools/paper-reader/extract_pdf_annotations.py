#!/usr/bin/env python3
"""Extract embedded PDF annotations (highlights/underlines/notes) as compact markdown.

Headless complement to the vault's `obsidian-extract-pdf-annotations` plugin (same
output shape as its configured compact template), for agents writing literature notes
directly. Works on any PDF path (e.g. the Zotero linked files in ~/nextcloud/zotero).

Usage:
    extract_pdf_annotations.py <pdf> [--json]

Output (markdown, default):
    > highlighted text *(p. 3)*
    - comment attached to the highlight (if any)
    - 📝 standalone note text *(p. 5)*

Run with the shared agents venv: ~/.local/share/dotfiles-agents/venv/bin/python
(pymupdf is installed there).

Text recovery uses PyMuPDF's clip-based extraction rather than reconstructing words
from QuadPoints by hand. The old pypdf implementation matched a word only when its
text-matrix origin fell inside the quad, so any run starting just outside the
highlight was dropped and the whole quad often came back empty (9 of 23 highlights
on a Papers-annotated report). It also emitted quads in file order, which reversed
multi-line highlights.
"""
import argparse
import json
import sys

import pymupdf

TEXT_MARKUP = {"Highlight", "Underline", "Squiggly"}
NOTE_TYPES = {"Text", "FreeText"}

# Quads whose tops fall within this many points are treated as the same visual line.
LINE_TOLERANCE = 5

# A word counts as highlighted once this fraction of its box falls inside a quad.
# Low enough to keep words the user only partly dragged over, high enough to reject
# the neighbours that a quad grazes at either end.
MIN_WORD_OVERLAP = 0.3

# Expand ligatures, so a highlight over "scientific" does not come back as "scientiﬁc".
WORD_FLAGS = pymupdf.TEXTFLAGS_WORDS & ~pymupdf.TEXT_PRESERVE_LIGATURES


def quad_rects(annot):
    """Quad rectangles of a text-markup annotation, ordered top-to-bottom, left-to-right."""
    verts = annot.vertices or []
    rects = []
    # Vertices arrive as groups of 4 corner points, one group per highlighted line.
    for i in range(0, len(verts) - 3, 4):
        # Pad vertically: glyph boxes routinely overshoot the quad by a fraction of a point.
        r = pymupdf.Quad(*verts[i:i + 4]).rect
        rects.append(pymupdf.Rect(r.x0, r.y0 - 1, r.x1, r.y1 + 1))
    # PyMuPDF page space puts y0 at the top, so ascending y0 is reading order. Quads
    # are not guaranteed to arrive in that order, hence the explicit sort.
    rects.sort(key=lambda r: (round(r.y0 / LINE_TOLERANCE), r.x0))
    return rects


def rect_text(words, rects):
    """Recover the highlighted text covered by a set of quad rectangles.

    Matched against a page's word boxes rather than clipped out of the page per quad:
    `Page.get_textbox` costs ~75 ms per call regardless of any textpage cache, which
    adds up to ten seconds on a heavily highlighted paper. Word boxes also keep the
    trailing punctuation that clipping tends to shave off.
    """
    picked = {}
    for r in rects:
        hit = False
        best = None
        for w in words:
            box = pymupdf.Rect(w[:4])
            area = box.get_area()
            if area <= 0:
                continue
            overlap = (box & r).get_area()
            if overlap <= 0:
                continue
            if overlap / area >= MIN_WORD_OVERLAP:
                # Key by (block, line, word) so overlapping quads cannot double-count
                # and sorting restores reading order across the whole annotation.
                picked[(w[5], w[6], w[7])] = w[4]
                hit = True
            elif best is None or overlap > best[0]:
                best = (overlap, (w[5], w[6], w[7]), w[4])
        # A quad narrower than the word beneath it (a stray tap highlighting a single
        # character) clears no ratio, so fall back to the word it overlaps most.
        if not hit and best is not None:
            picked[best[1]] = best[2]
    return " ".join(picked[k] for k in sorted(picked))


def extract(pdf_path):
    results = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            words = None
            for annot in page.annots() or []:
                kind = annot.type[1]
                if kind not in TEXT_MARKUP | NOTE_TYPES:
                    continue
                comment = (annot.info.get("content") or "").strip()
                entry = {"page": page.number + 1, "type": kind, "comment": comment}
                if kind in TEXT_MARKUP:
                    if words is None:  # parsed once per page, only if it has highlights
                        words = page.get_text("words", flags=WORD_FLAGS)
                    entry["text"] = rect_text(words, quad_rects(annot))
                results.append(entry)
    return results


def to_markdown(annots):
    lines = []
    for a in annots:
        if a["type"] in TEXT_MARKUP:
            if a.get("text"):
                lines.append(f"> {a['text']} *(p. {a['page']})*")
            if a["comment"]:
                lines.append(f"- {a['comment']}")
            lines.append("")
        else:
            if a["comment"]:
                lines.append(f"- 📝 {a['comment']} *(p. {a['page']})*")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = ap.parse_args()
    annots = extract(args.pdf)
    if not annots:
        print("(no annotations found)", file=sys.stderr)
        return 1
    if args.json:
        json.dump(annots, sys.stdout, indent=1, ensure_ascii=False)
    else:
        sys.stdout.write(to_markdown(annots))
    return 0


if __name__ == "__main__":
    sys.exit(main())
