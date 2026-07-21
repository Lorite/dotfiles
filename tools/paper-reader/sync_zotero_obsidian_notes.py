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
        "status: new",
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
        body += [hl_section(today, highlights_md)]
    body += ["%% end annotations %%", "", "# Links", "", "%% begin links %%", "%% end links %%", ""]
    return title, "\n".join(fm + body)


HL_BEGIN = "<!-- boox-highlights:begin -->"
HL_END = "<!-- boox-highlights:end -->"


def hl_section(today, highlights_md):
    return (f"{HL_BEGIN}\n## Extracted on [[{today}]] (embedded PDF annotations, headless)\n\n"
            f"{highlights_md.rstrip()}\n{HL_END}\n")


def refresh_note_highlights(note_path, today, highlights_md):
    """Replace the machine-managed highlights section inside the annotations block.

    Only the marked (or legacy unmarked '## Extracted on') section is touched —
    plugin-imported Zotero annotations ('## Imported on ...') and hand edits stay.
    Returns True if the file changed.
    """
    s = open(note_path).read()
    if "%% begin annotations %%" not in s:
        return False
    new_sec = hl_section(today, highlights_md)
    if HL_BEGIN in s and HL_END in s:
        pre, rest = s.split(HL_BEGIN, 1)
        _, post = rest.split(HL_END, 1)
        out = pre + new_sec.rstrip("\n") + post
    else:
        m = re.search(r"## Extracted on \[\[[0-9-]+\]\] \(embedded PDF annotations, headless\)\n"
                      r".*?(?=\n%% end annotations %%)", s, re.DOTALL)
        if m:  # legacy unmarked section from the first backfill — migrate to markers
            out = s[:m.start()] + new_sec.rstrip("\n") + s[m.end():]
        else:  # no section yet — insert before the block's end marker
            out = s.replace("%% end annotations %%", new_sec + "%% end annotations %%", 1)
    if out != s:
        open(note_path, "w").write(out)
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="create at most N notes")
    ap.add_argument("--key", help="only process this item key")
    ap.add_argument("--no-highlights", action="store_true")
    ap.add_argument("--refresh-highlights", action="store_true",
                    help="re-extract highlights into EXISTING notes for PDFs whose mtime "
                         "changed since the last run (BOOX reading sessions synced back)")
    ap.add_argument("--quiet", action="store_true",
                    help="timer mode: no output unless something was created or failed")
    args = ap.parse_args()

    from datetime import date
    today = date.today().isoformat()

    # Timer mode: if Zotero isn't running there's nothing new to sync (the browser
    # connector needs Zotero open to add items) — exit clean, don't mark the unit failed.
    try:
        api("/collections?limit=1")
    except Exception:
        if args.quiet:
            return 0
        print("Zotero local API unreachable (is Zotero running?)", file=sys.stderr)
        return 1

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

    refreshed = 0
    if args.refresh_highlights and epa and not args.dry_run:
        state_dir = os.path.expanduser("~/.local/state/zotero-obsidian-sync")
        os.makedirs(state_dir, exist_ok=True)
        state_path = os.path.join(state_dir, "highlights_mtimes.json")
        try:
            state = json.load(open(state_path))
        except Exception:
            state = {}
        note_by_citekey = {f[:-3].rsplit(" - ", 1)[-1]: os.path.join(NOTES_DIR, f)
                           for f in os.listdir(NOTES_DIR) if f.endswith(".md")}
        for it in items:
            d = it["data"]
            if d["itemType"] in ("attachment", "note", "annotation") or "parentItem" in d:
                continue
            note = note_by_citekey.get(d.get("citationKey", ""))
            if not note:
                continue
            try:
                pdf = linked_pdf(d["key"])
                if not pdf:
                    continue
                mtime = os.path.getmtime(pdf)
                if state.get(pdf) == mtime:
                    continue
                annots = epa.extract(pdf)
                if annots and refresh_note_highlights(note, today, epa.to_markdown(annots)):
                    refreshed += 1
                    print(f"highlights refreshed: {os.path.basename(note)}")
                state[pdf] = mtime  # record even if no annotations — don't rescan unchanged files
            except Exception as e:
                print(f"warn: highlight refresh failed for {d.get('citationKey')}: {e}", file=sys.stderr)
        json.dump(state, open(state_path, "w"))

    if not args.quiet or created or refreshed or failed:
        print(f"\n{'would create' if args.dry_run else 'created'}: {created}, "
              f"existing skipped: {skipped}, highlights refreshed: {refreshed}, failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
