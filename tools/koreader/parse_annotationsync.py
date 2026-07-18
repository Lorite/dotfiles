#!/usr/bin/env python3
"""Parse KOReader **AnnotationSync** JSON → emit only the NEW highlights as structured JSON.

Source of truth for the lorite-koreader-highlights import (architecture B′, decided 2026-07-18):
the AnnotationSync.koplugin sync folder, which is what's actually Nextcloud-synced to the laptop
AND the headless home server (the book files and `.sdr` sidecars are NOT synced there). Each file
is `<document>.json`, a dict keyed by an annotation position-id → annotation object with
text / color / page / chapter / datetime / drawer (and optional note).

This tool is deterministic: it reads those JSONs, deduplicates against a state file, maps each
highlight's COLOUR to a vault category (gray/unknown → "gray", left for the AI to classify), and
prints the new highlights grouped by document. The `lorite-koreader-highlights` skill then routes
each document to the right vault note (media/research | media/books | media/articles | inbox) and
formats/enriches it.

Colour → category (see the vault's "Notes color highlighting" note):
  yellow → general | red → super | green → concept | blue → quote |
  purple/violet → heading | pink/magenta → vocabulary | orange → figure | gray/unknown → "gray"

Usage:
    parse_annotationsync.py [--dir DIR] [--vault DIR] [--state FILE] [--commit] [--pretty]

    (default)   print new highlights as JSON; do NOT touch the state file (safe preview)
    --commit    also record the emitted highlights' hashes in the state file (mark processed)
    --dir       AnnotationSync folder (default: $KOREADER_ANNOTATIONSYNC_DIR, else the first of the
                known laptop/home-server Nextcloud paths that exists)
    --state     state file (default: <vault>/.koreader-highlights/state.json, shared via Syncthing)

Typical skill flow: run without --commit → write the notes → run again with --commit.
Stdlib only.
"""
import argparse
import hashlib
import json
import os
import sys

VAULT_DEFAULT = os.environ.get("VAULT") or os.path.expanduser("~/git/lorite-obsidian-notes")

# Candidate AnnotationSync dirs (laptop Nextcloud mount, then home-server data path).
DIR_CANDIDATES = [
    os.environ.get("KOREADER_ANNOTATIONSYNC_DIR", ""),
    os.path.expanduser("~/nextcloud-all/westerndigitalnvmessd/Documents/media/koreader/AnnotationSync"),
    "/westerndigitalnvmessd/Documents/media/koreader/AnnotationSync",
]

COLOUR_CATEGORY = {
    "yellow": "general", "red": "super", "green": "concept", "blue": "quote",
    "purple": "heading", "violet": "heading", "pink": "vocabulary", "magenta": "vocabulary",
    "orange": "figure", "gray": "gray", "grey": "gray",
}

DOC_EXTS = (".pdf", ".epub", ".mobi", ".cbz", ".azw3", ".fb2", ".djvu", ".html", ".txt")
SKIP_SUFFIXES = (".progress.json",)
SKIP_NAMES = {"settings_sync.json"}


def resolve_dir(arg_dir):
    for d in ([arg_dir] if arg_dir else []) + DIR_CANDIDATES:
        if d and os.path.isdir(d):
            return d
    return None


def doc_title_and_ext(filename):
    """`Foo - 2025 - Bar.pdf.json` -> ("Foo - 2025 - Bar", ".pdf")."""
    name = filename[:-5] if filename.lower().endswith(".json") else filename
    for ext in DOC_EXTS:
        if name.lower().endswith(ext):
            return name[: -len(ext)], ext
    return name, ""


def norm(a):
    """Normalise one AnnotationSync annotation dict; None if it has no text."""
    text = a.get("text")
    if not text or not str(text).strip():
        return None
    colour = str(a.get("color") or a.get("colour") or "").strip().lower()
    return {
        "text": str(text).strip(),
        "note": str(a.get("note") or "").strip(),
        "chapter": str(a.get("chapter") or "").strip(),
        "page": a.get("pageno", a.get("page", "")),
        "datetime": str(a.get("datetime") or "").strip(),
        "colour": colour,
        "drawer": str(a.get("drawer") or "").strip().lower(),
        "category": COLOUR_CATEGORY.get(colour, "gray"),
        "is_tmp": bool(a.get("is_tmp", False)),
    }


def h(book_key, hl):
    raw = f"{book_key}\x1f{hl['text']}\x1f{hl['page']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description="Emit new KOReader AnnotationSync highlights as JSON.")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--vault", default=VAULT_DEFAULT)
    ap.add_argument("--state", default=None)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    src = resolve_dir(args.dir)
    if not src:
        print(json.dumps({"error": "AnnotationSync dir not found", "tried": [d for d in DIR_CANDIDATES if d], "docs": []}))
        return 0
    state_path = args.state or os.path.join(args.vault, ".koreader-highlights", "state.json")

    state = {}
    if os.path.exists(state_path):
        try:
            state = json.load(open(state_path))
        except Exception:
            state = {}
    seen = set(state.get("seen", []))

    docs, new_hashes = [], []
    for name in sorted(os.listdir(src)):
        low = name.lower()
        if not low.endswith(".json") or low in SKIP_NAMES or low.endswith(SKIP_SUFFIXES):
            continue
        try:
            data = json.load(open(os.path.join(src, name)))
        except Exception as e:
            print(f"warn: could not parse {name}: {e}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        title, ext = doc_title_and_ext(name)
        fresh = []
        for ann in data.values():
            if not isinstance(ann, dict):
                continue
            hl = norm(ann)
            if not hl:
                continue
            hh = h(title, hl)
            if hh in seen:
                continue
            hl["hash"] = hh
            fresh.append(hl)
            new_hashes.append(hh)
        if fresh:
            # sort by page then datetime for a stable reading order
            fresh.sort(key=lambda x: (x["page"] if isinstance(x["page"], (int, float)) else 0, x["datetime"]))
            docs.append({"file": name, "title": title, "ext": ext,
                         "new_count": len(fresh), "highlights": fresh})

    if args.commit and new_hashes:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        state["seen"] = sorted(seen | set(new_hashes))
        json.dump(state, open(state_path, "w"), indent=2)

    out = {"source_dir": src, "committed": bool(args.commit),
           "total_new": len(new_hashes), "docs": docs}
    print(json.dumps(out, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
