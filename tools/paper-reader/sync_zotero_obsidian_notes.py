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
note's annotations block unless --no-highlights. Zotero CHILD NOTES are imported too:
the "AI Generated Summary (<model>)" note becomes the note's Notes section, the machine
"Citations" note becomes the `citations` / `citations_counted_date` frontmatter lists
(appended, so the count keeps a dated history), and an arXiv "Comment:" note becomes
`arxiv_comment`. Use --refresh-notes to backfill notes that already exist.

Usage (run with the shared agents venv — pymupdf lives there):
    ~/.local/share/dotfiles-agents/venv/bin/python sync_zotero_obsidian_notes.py --dry-run
    ... --limit 5            # create at most 5 notes (testing)
    ... --key ABCD1234       # only this item
    ... --no-highlights      # skip PDF annotation extraction
    ... --refresh-notes      # backfill Zotero child notes into EXISTING notes too
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


def build_note(item, coll_paths, today, highlights_md=None, parsed=None):
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
        *( [f"citations: [{parsed['citations']}]",
             f"citations_counted_date: [{parsed['citations_date']}]"]
           if parsed and parsed.get("citations") is not None and parsed.get("citations_date") else [] ),
        *( [f"arxiv_comment: {json.dumps(parsed['arxiv_comment'])}"]
           if parsed and parsed.get("arxiv_comment") else [] ),
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
    body += ["# Notes", "", "%% begin notes %%", ""]
    if parsed and parsed.get("summary_md"):
        body += [notes_section(today, parsed.get("summary_model") or "unknown", parsed["summary_md"])]
    else:
        body += [f"## Created by sync_zotero_obsidian_notes on [[{today}]]", "",
                 "*(No deep read yet — run `lorite-paper-reader` to fill this section.)*", ""]
    body += ["%% end notes %%", ""]
    body += ["# Highlights", "", "%% begin annotations %%", ""]
    if highlights_md:
        body += [hl_section(today, highlights_md)]
    body += ["%% end annotations %%", "", "# Links", "", "%% begin links %%", "%% end links %%", ""]
    return title, "\n".join(fm + body)



# ---------------------------------------------------------------------------
# Zotero child notes -> vault
#
# Zotero items carry child notes that the headless sync ignored until 2026-08-19:
# an "AI Generated Summary (<model>)" note, a machine-written "Citations" note whose
# <pre> block is a JSON array of citing/cited records, and short arXiv "Comment:" notes.
# The summary is rendered into the notes block (same shape the Zotero Integration
# plugin produced, so old and new notes read alike); the other two become frontmatter.
# ---------------------------------------------------------------------------

NOTES_BEGIN = "<!-- zotero-notes:begin -->"
NOTES_END = "<!-- zotero-notes:end -->"


def child_notes(key):
    out = []
    for ch in api(f"/items/{key}/children"):
        d = ch["data"]
        if d.get("itemType") == "note":
            out.append(d.get("note", ""))
    return out


def _strip_tags(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def html_note_to_md(body, demote=1):
    """Minimal Zotero-note HTML -> Markdown. Headings are demoted by `demote` levels so
    the note's own <h2> sits under the '### AI Generated Summary' heading we add."""
    t = body
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    out, pos = [], 0
    token = re.compile(r"<(h[1-6])>(.*?)</\1>|<li>(.*?)</li>|<p>(.*?)</p>", re.I | re.DOTALL)
    for m in token.finditer(t):
        if m.group(1):
            level = min(6, int(m.group(1)[1]) + demote)
            txt = _strip_tags(m.group(2))
            if txt:
                out.append(f"{'#' * level} {txt}\n")
        elif m.group(3) is not None:
            txt = _strip_tags(m.group(3))
            if txt:
                out.append(f"- {txt}")
        else:
            txt = _strip_tags(m.group(4))
            if txt:
                out.append(f"{txt}\n")
    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def parse_child_notes(notes):
    """-> dict(summary_md, summary_model, citations, citations_date, arxiv_comment)."""
    res = {"summary_md": None, "summary_model": None,
           "citations": None, "citations_date": None, "arxiv_comment": None}
    for n in notes:
        head = _strip_tags(n[:400])
        m = re.search(r"AI Generated Summary\s*\(([^)]+)\)", n)
        if m and res["summary_md"] is None:
            res["summary_model"] = m.group(1).strip()
            # drop the title heading itself; it becomes our '### AI Generated Summary (model)'
            body = re.sub(r"<h[1-6]>\s*AI Generated Summary[^<]*</h[1-6]>", "", n, count=1, flags=re.I)
            res["summary_md"] = html_note_to_md(body, demote=1)
            continue
        if head.startswith("Citations") and "<pre>" in n:
            try:
                raw = html.unescape(re.search(r"<pre>(.*?)</pre>", n, re.DOTALL).group(1))
                data = json.loads(raw)
                res["citations"] = len(data)
                dates = [e.get("creationDate", "")[:10] for e in data if e.get("creationDate")]
                res["citations_date"] = max(dates) if dates else None
            except Exception:
                pass
            continue
        m = re.match(r"Comment:\s*(.+)", head)
        if m and res["arxiv_comment"] is None:
            res["arxiv_comment"] = m.group(1).strip().rstrip(".")
    return res


def notes_section(today, model, summary_md):
    return (f"{NOTES_BEGIN}\n## Imported on [[{today}]]\n\n\n"
            f"### AI Generated Summary ({model})\n\n{summary_md}\n{NOTES_END}\n")


def refresh_note_children(note_path, today, parsed):
    """Update an EXISTING note in place from its Zotero child notes.

    Touches only machine-managed surface: the marked notes block and the three
    frontmatter keys. A note that already carries a plugin-imported summary
    ('### AI Generated Summary' outside our markers) keeps it and is not duplicated.
    Returns a list of what changed.
    """
    s = open(note_path).read()
    orig = s
    changed = []

    # --- body: the AI summary ---
    if parsed["summary_md"]:
        has_ours = NOTES_BEGIN in s
        has_theirs = "AI Generated Summary" in s.split("%% end notes %%")[0] and not has_ours
        if not has_theirs:
            sec = notes_section(today, parsed["summary_model"] or "unknown", parsed["summary_md"])
            if has_ours:
                s = re.sub(re.escape(NOTES_BEGIN) + r".*?" + re.escape(NOTES_END) + r"\n?",
                           sec, s, flags=re.DOTALL)
            else:
                placeholder = ("*(No deep read yet — run `lorite-paper-reader` to fill this section.)*\n\n")
                stale = re.search(r"## Created by sync_zotero_obsidian_notes on \[\[[0-9-]+\]\]\n\n"
                                  + re.escape(placeholder), s)
                if stale:
                    s = s.replace(stale.group(0), sec, 1)
                elif placeholder in s:
                    s = s.replace(placeholder, sec, 1)
                elif "%% end notes %%" in s:
                    s = s.replace("%% end notes %%", sec + "%% end notes %%", 1)
                else:
                    return changed
            # also retire the stale creation heading if it now sits right above our block
            s = re.sub(r"## Created by sync_zotero_obsidian_notes on \[\[[0-9-]+\]\]\n\n(?=" +
                       re.escape(NOTES_BEGIN) + r")", "", s)
            if s != orig:
                changed.append("summary")

    # --- frontmatter ---
    def fm_block(key):
        """Whole frontmatter entry for `key`, inline or block list. -> (text, values)."""
        m = re.search(rf"^{key}:[ \t]*(.*)(?:\n(?:[ \t]*-[ \t]*.*\n?)*)?", s, re.M)
        if not m:
            return None, []
        return m.group(0).rstrip("\n"), re.findall(r"[\w.:-]+", m.group(0).split(":", 1)[1])

    if parsed["citations"] is not None and parsed["citations_date"]:
        cur_c, counts = fm_block("citations")
        cur_d, dates = fm_block("citations_counted_date")
        if parsed["citations_date"] not in dates:
            counts = [c for c in counts if c.isdigit()] + [str(parsed["citations"])]
            dates = [d for d in dates if re.fullmatch(r"\d{4}-\d\d-\d\d", d)] + [parsed["citations_date"]]
            new_c = f"citations: [{', '.join(counts)}]"
            new_d = "citations_counted_date: [" + ", ".join(dates) + "]"
            if cur_c and cur_d:
                s = s.replace(cur_c, new_c, 1).replace(cur_d, new_d, 1)
            elif cur_c:
                s = s.replace(cur_c, new_c + "\n" + new_d, 1)
            else:
                s = s.replace("\ntype: research", f"\n{new_c}\n{new_d}\ntype: research", 1)
            changed.append("citations")

    if parsed["arxiv_comment"] and not fm_block("arxiv_comment")[0]:
        line = f"arxiv_comment: {json.dumps(parsed['arxiv_comment'])}"
        s = s.replace("\ntype: research", f"\n{line}\ntype: research", 1)
        changed.append("arxiv_comment")

    if s != orig:
        open(note_path, "w").write(s)
    return changed


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
    ap.add_argument("--refresh-notes", action="store_true",
                    help="import Zotero child notes (AI summary, citation count, arXiv "
                         "comment) into EXISTING notes as well as new ones")
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
            print("warn: pymupdf/extract_pdf_annotations unavailable — skipping highlights", file=sys.stderr)

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
            try:
                parsed = parse_child_notes(child_notes(d["key"]))
            except Exception as e:
                print(f"warn: child-note parse failed for {citekey}: {e}", file=sys.stderr)
                parsed = None
            _, content = build_note(it, coll_paths, today, hl, parsed)
            with open(path, "w") as f:
                f.write(content)
            created += 1
            extras = ("" if not hl else " [+highlights]") + ("" if not (parsed and parsed.get("summary_md")) else " [+summary]")
            print(f"created: {os.path.basename(path)}{extras}")
        except Exception as e:
            failed += 1
            print(f"FAILED {citekey}: {e}", file=sys.stderr)

    notes_updated = 0
    if args.refresh_notes and not args.dry_run:
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
                parsed = parse_child_notes(child_notes(d["key"]))
                if not any(parsed.values()):
                    continue
                ch = refresh_note_children(note, today, parsed)
                if ch:
                    notes_updated += 1
                    print(f"notes updated ({', '.join(ch)}): {os.path.basename(note)}")
            except Exception as e:
                print(f"warn: child-note refresh failed for {d.get('citationKey')}: {e}", file=sys.stderr)

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

    if not args.quiet or created or refreshed or notes_updated or failed:
        print(f"\n{'would create' if args.dry_run else 'created'}: {created}, "
              f"existing skipped: {skipped}, highlights refreshed: {refreshed}, "
              f"notes updated: {notes_updated}, failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
