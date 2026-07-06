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
(pypdf is installed there).
"""
import argparse
import json
import sys

from pypdf import PdfReader

TEXT_MARKUP = {"/Highlight", "/Underline", "/Squiggly"}
NOTE_TYPES = {"/Text", "/FreeText"}


def rect_text(page, quads):
    """Recover the highlighted text from QuadPoints via word positions."""
    words = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            words.append((tm[4], tm[5], text))

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        return ""
    out = []
    # QuadPoints come as groups of 8 floats (x1 y1 ... x4 y4), one group per line.
    for i in range(0, len(quads), 8):
        q = quads[i:i + 8]
        x_min, x_max = min(q[0::2]), max(q[0::2])
        y_min, y_max = min(q[1::2]), max(q[1::2])
        line = [t for (x, y, t) in words
                if y_min - 2 <= y <= y_max + 2 and x_min - 2 <= x <= x_max + 2]
        out.append("".join(line))
    return " ".join(" ".join(out).split())


def extract(pdf_path):
    reader = PdfReader(pdf_path)
    results = []
    for pnum, page in enumerate(reader.pages, start=1):
        for ref in page.get("/Annots") or []:
            a = ref.get_object()
            sub = a.get("/Subtype")
            if sub not in TEXT_MARKUP | NOTE_TYPES:
                continue
            comment = (a.get("/Contents") or "").strip()
            entry = {"page": pnum, "type": sub[1:], "comment": comment}
            if sub in TEXT_MARKUP:
                quads = [float(v) for v in (a.get("/QuadPoints") or [])]
                entry["text"] = rect_text(page, quads) if quads else ""
            results.append(entry)
    return results


def to_markdown(annots):
    lines = []
    for a in annots:
        if a["type"] in ("Highlight", "Underline", "Squiggly"):
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
