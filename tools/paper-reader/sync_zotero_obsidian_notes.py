#!/usr/bin/env python3
"""Ensure every top-level Zotero item has an Obsidian literature note.

Creates missing `media/research/<title> - <citekey>.md` notes from Zotero metadata,
replicating the vault's `templates/media/research.md` schema (same shape the Zotero
Integration plugin produces, persist markers included). Existing notes are NEVER
touched — the script is idempotent; re-run it whenever Zotero gained items.

Reads via the Zotero LOCAL API (Zotero desktop must be running); the bibliography is
the CSL-rendered bibtex entry (`include=bib&style=bibtex`) — NOT `format=bibtex`,
which embeds child notes as `annote` fields and bloats entries by orders of magnitude.
Embedded PDF highlights (BOOX-annotated linked files) are extracted into the new
note's annotations block unless --no-highlights.

Usage (run with the shared agents venv — pypdf lives there):
    ~/.local/share/dotfiles-agents/venv/bin/python sync_zotero_obsidian_notes.py --dry-run
    ... --limit 5            # create at most 5 notes (testing)
    ... --key ABCD1234       # only this item
    ... --no-highlights      # skip PDF annotation extraction
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API = "http://localhost:23119/api/users/0"
VAULT = os.path.expanduser("~/git/lorite-obsidian-notes")
NOTES_DIR = os.path.join(VAULT, "media", "research")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def api(path):
    with urllib.request.urlopen(API + path) as r:
        return json.load(r)


def all_top_items():
    items, start = [], 0
    while True:
        batch = api(f"/items?itemType=-attachment&limit=100&start={start}&format=json")
        if not batch:
            return items
        items += batch
        start += 100


def collection_paths():
    """collection key -> 'Parent/Child' full path."""
    colls, start = {}, 0
    while True:
        batch = api(f"/collections?limit=100&start={start}")
        if not batch:
            break
        for c in batch:
            colls[c["data"]["key"]] = c["data"]
        start += 100
    def full(key):
        c = colls.get(key)
        if not c:
            return None
        parent = c.get("parentCollection")
        return (full(parent) + "/" if parent and parent in colls else "") + c["name"]
    return {k: full(k) for k in colls}


def escape_title(t):
    t = t.replace(":", " -")
    return re.sub(r"[/\\\n]", "-", t).strip()


def csl_bibliography(key):
    d = api(f"/items/{key}?format=json&include=bib&style=bibtex")
    text = html.unescape(re.sub(r"<[^>]+>", "", d.get("bib", ""))).strip()
    return " ".join(text.split())


def linked_pdf(key):
    for ch in api(f"/items/{key}/children"):
        d = ch["data"]
        if d.get("itemType") == "attachment" and d.get("contentType") == "application/pdf":
            p = d.get("path", "")
            if d.get("linkMode") == "linked_file" and os.path.exists(p):
                return p
    return None


def fmt_date(iso):
    return f"{iso[:10]} {iso[11:16]}" if iso and len(iso) >= 16 else ""


def pub_date(data):
    pd = (data.get("parsedDate") or data.get("date") or "").strip()
    m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", pd)
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2) or '01'}-{m.group(3) or '01'} 12:00"


def build_note(item, coll_paths, today, highlights_md=None):
    d = item["data"]
    citekey = d["citationKey"]
    title = escape_title(d.get("title") or d.get("nameOfAct") or citekey)
    authors = [f"{c.get('firstName','')} {c.get('lastName', c.get('name',''))}".strip()
               for c in d.get("creators", [])]
    hash_tags = [t["tag"][1:] for t in d.get("tags", []) if t["tag"].startswith("#")]
    colls = [coll_paths.get(k) for k in d.get("collections", []) if coll_paths.get(k)]
    domain = d.get("publicationTitle") or d.get("proceedingsTitle") or d.get("websiteTitle") or ""
    doi = d.get("DOI", "")
    meta = dict(d)
    meta["parsedDate"] = item.get("meta", {}).get("parsedDate", "")
    fm = [
        "---",
        f'aliases: [{json.dumps(title)}, "{citekey}"]',
        f"DOI: https://www.doi.org/{doi}" if doi else "DOI: ",
        f"cite_key: {citekey}",
        f"title: {json.dumps(title)}",
        f"domain_name: {json.dumps(domain)}",
        f"authors: [{', '.join(json.dumps(a) for a in authors)}]",
        f'item_type: "{d["itemType"]}"',
        f"collections: [{', '.join(json.dumps(c) for c in colls)}]",
        f"tags: [{', '.join(['media', 'research'] + hash_tags)}]",
        "links: []",
        f"date_published: {pub_date(meta)}",
        f"date_saved: {fmt_date(d.get('dateAdded',''))}",
        f"date_read: {fmt_date(d.get('dateModified',''))}",
        f"url: {d.get('url','')}",
        f"zotero: zotero://select/library/items/{d['key']}",
        "type: research",
        "publish: true",
        "publish_mode: external",
        "personal_rating: ",
        "---",
    ]
    body = ["", "# Formatted Bibliography", "", csl_bibliography(d["key"]), ""]
    if d.get("abstractNote"):
        body += ["# Abstract", "", d["abstractNote"], ""]
    body += ["# Extra", "", d.get("extra", ""), ""]
    body += ["# Notes", "", "%% begin notes %%", "",
             f"## Created by sync_zotero_obsidian_notes on [[{today}]]", "",
             "*(No deep read yet — run `lorite-paper-reader` to fill this section.)*", "",
             "%% end notes %%", ""]
    body += ["# Highlights", "", "%% begin annotations %%", ""]
    if highlights_md:
        body += [f"## Extracted on [[{today}]] (embedded PDF annotations, headless)", "",
                 highlights_md.rstrip(), ""]
    body += ["%% end annotations %%", "", "# Links", "", "%% begin links %%", "%% end links %%", ""]
    return title, "\n".join(fm + body)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="create at most N notes")
    ap.add_argument("--key", help="only process this item key")
    ap.add_argument("--no-highlights", action="store_true")
    args = ap.parse_args()

    from datetime import date
    today = date.today().isoformat()

    epa = None
    if not args.no_highlights:
        try:
            import extract_pdf_annotations as epa
        except ImportError:
            print("warn: pypdf/extract_pdf_annotations unavailable — skipping highlights", file=sys.stderr)

    existing = {f[:-3].rsplit(" - ", 1)[-1]
                for f in os.listdir(NOTES_DIR) if f.endswith(".md")}
    items = [api(f"/items/{args.key}?format=json")] if args.key else all_top_items()
    coll_paths = collection_paths()

    created = skipped = failed = 0
    for it in items:
        d = it["data"]
        if d["itemType"] in ("attachment", "note", "annotation") or "parentItem" in d:
            continue
        citekey = d.get("citationKey")
        if not citekey:
            print(f"warn: no citationKey for {d['key']} ({d.get('title','')[:50]}) — skipped", file=sys.stderr)
            failed += 1
            continue
        if citekey in existing:
            skipped += 1
            continue
        if args.limit and created >= args.limit:
            break
        title = escape_title(d.get("title") or citekey)
        # keep the filesystem name bounded (frontmatter keeps the full title)
        fname_title = title if len(title) <= 120 else title[:120].rsplit(" ", 1)[0] + " …"
        path = os.path.join(NOTES_DIR, f"{fname_title} - {citekey}.md")
        if args.dry_run:
            print(f"would create: {os.path.basename(path)}")
            created += 1
            continue
        try:
            hl = None
            if epa:
                try:
                    pdf = linked_pdf(d["key"])
                    if pdf:
                        annots = epa.extract(pdf)
                        if annots:
                            hl = epa.to_markdown(annots)
                except Exception as e:  # corrupt PDF etc. — note still gets created
                    print(f"warn: highlight extraction failed for {citekey}: {e}", file=sys.stderr)
            _, content = build_note(it, coll_paths, today, hl)
            with open(path, "w") as f:
                f.write(content)
            created += 1
            print(f"created: {os.path.basename(path)}" + (" [+highlights]" if hl else ""))
        except Exception as e:
            failed += 1
            print(f"FAILED {citekey}: {e}", file=sys.stderr)

    print(f"\n{'would create' if args.dry_run else 'created'}: {created}, "
          f"existing skipped: {skipped}, failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
