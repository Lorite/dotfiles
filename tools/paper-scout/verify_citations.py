#!/usr/bin/env python3
"""
paper-scout — deterministic citation-EXISTENCE verifier for a BibTeX file.

Why this exists: LLM-written prose can cite papers that do not exist, or attach a real
`\\cite{key}` to a bib entry whose title/DOI don't actually match a real work (the
"hallucinated citation" failure mode — Zhao et al. 2026 counted ~147k of them across 2.5M
papers in 2025). This script checks every entry in `references.bib` against public,
authoritative indexes WITHOUT an LLM in the loop, so it can be trusted as a pre-submission
gate. It is advisory by default (reports a table) and a hard gate with `--strict` (nonzero
exit if anything is UNRESOLVED or TITLE-MISMATCH).

Resolution order per entry (first hit wins; a DOI is the strongest signal):
  1. DOI present      -> Crossref /works/{doi}   (then OpenAlex /works/doi: as fallback)
  2. arXiv id present -> arXiv export API id_list (eprint / archivePrefix=arXiv)
  3. neither          -> Crossref bibliographic query by title, take best title match
For every hit we also compare the *found* title to the bib title (difflib ratio); a resolve
whose title similarity is below --title-threshold (default 0.82) is reported TITLE-MISMATCH
rather than RESOLVED, which catches a real-DOI-but-wrong-paper mixup.

No third-party deps (stdlib urllib + difflib only), so it runs under system python3 or the
shared agents venv. Network calls are polite: a descriptive User-Agent (Crossref's "polite
pool"), a small delay between calls, and a local cache so re-runs are cheap.

Cache: JSON at $PAPER_SCOUT_HOME/cite-verify-cache.json (default ~/.config/paper-scout/),
keyed by doi / arxiv / normalized-title, 90-day TTL. --no-cache bypasses read+write;
--refresh ignores existing entries but re-writes them.

Usage:
  verify_citations.py references.bib                 # advisory table to stdout
  verify_citations.py references.bib --strict        # exit 1 if any UNRESOLVED/MISMATCH
  verify_citations.py references.bib --json           # machine-readable report
  verify_citations.py references.bib --only-problems  # print only non-RESOLVED rows
  verify_citations.py references.bib --key foo23bar   # verify a single entry

Contact for the polite User-Agent can be set with $PAPER_SCOUT_CONTACT (an email).
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

_HOME = Path(os.environ.get("PAPER_SCOUT_HOME", Path.home() / ".config/paper-scout"))
CACHE_PATH = _HOME / "cite-verify-cache.json"
CACHE_TTL = 90 * 24 * 3600  # seconds
CONTACT = os.environ.get("PAPER_SCOUT_CONTACT", "paper-scout@localhost")
UA = f"paper-scout-cite-verify/1.0 (mailto:{CONTACT})"
# Public APIs only — no proxy, no auth. Bypass any institutional http(s)_proxy env vars.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DELAY = float(os.environ.get("PAPER_SCOUT_VERIFY_DELAY", "0.4"))


# ---------------------------------------------------------------- bib parsing
def _strip_latex(s):
    """Lightweight de-TeX for title comparison: drop braces/commands, unescape, normalize."""
    s = re.sub(r"\\[a-zA-Z]+\s*", " ", s)   # \command
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\\&", "&").replace("~", " ").replace("--", "-")
    return s


def norm_title(s):
    s = _strip_latex(s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def title_sim(a, b):
    """Similarity in [0,1], tolerant of dropped subtitles (Crossref often stores only the
    main title, so a bib 'Main: subtitle' vs an indexed 'Main' should score as a match).

    The subtitle bonus only applies when a title *actually has* a ':' — comparing its
    main-title part to the other title. Two colon-less titles that merely share a generic
    opening ('The Nonexistent …' vs a real paper 'The Nonexistent') must NOT match, so they
    fall through to the plain ratio."""
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0.0
    best = difflib.SequenceMatcher(None, na, nb).ratio()
    for x, y in ((a, b), (b, a)):
        if ":" in x:
            main = norm_title(x.split(":", 1)[0])
            if len(main) >= 12:
                best = max(best, difflib.SequenceMatcher(None, main, norm_title(y)).ratio())
    return best


# Entry types whose works are cited by URL and are not registered in DOI indexes; a title
# search on these just finds spurious matches, so they are reported NO-ID (verify by hand),
# not counted against the --strict gate.
NON_INDEXED_TYPES = {"misc", "online", "software", "manual", "unpublished", "booklet"}


def parse_bib(text):
    """Minimal BibTeX parser. Yields dicts {key, type, title, doi, arxiv, year}.

    Balanced-brace aware for field values; handles {..} and "..".  Comments and @string/
    @comment/@preamble blocks are skipped. Robust enough for a hand/Zotero-maintained .bib.
    """
    entries = []
    i, n = 0, len(text)
    while i < n:
        at = text.find("@", i)
        if at < 0:
            break
        m = re.match(r"@(\w+)\s*[{(]", text[at:])
        if not m:
            i = at + 1
            continue
        etype = m.group(1).lower()
        body_start = at + m.end()
        if etype in ("comment", "string", "preamble"):
            i = body_start
            continue
        # find matching close brace for the whole entry
        depth = 1
        j = body_start
        while j < n and depth:
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        body = text[body_start:j - 1]
        i = j
        # first token up to comma is the cite key
        comma = body.find(",")
        if comma < 0:
            continue
        key = body[:comma].strip()
        fields = _parse_fields(body[comma + 1:])
        arxiv = fields.get("eprint", "")
        if fields.get("archiveprefix", "").lower() != "arxiv" and "arxiv" not in fields.get("journal", "").lower():
            # only trust `eprint` as an arXiv id when it's declared arXiv (or journal says so)
            if not re.match(r"\d{4}\.\d{4,5}", arxiv or ""):
                arxiv = ""
        entries.append({
            "key": key,
            "type": etype,
            "title": _strip_latex(fields.get("title", "")).strip(),
            "doi": _clean_doi(fields.get("doi", "")),
            "arxiv": (arxiv or "").strip(),
            "year": fields.get("year", "").strip(),
        })
    return entries


def _parse_fields(body):
    fields = {}
    i, n = 0, len(body)
    while i < n:
        m = re.match(r"\s*([A-Za-z_][\w-]*)\s*=\s*", body[i:])
        if not m:
            i += 1
            continue
        name = m.group(1).lower()
        i += m.end()
        if i >= n:
            break
        if body[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                j += 1
            val = body[i + 1:j - 1]
            i = j
        elif body[i] == '"':
            j = i + 1
            while j < n and body[j] != '"':
                j += 1
            val = body[i + 1:j]
            i = j + 1
        else:  # bare number/word
            j = i
            while j < n and body[j] not in ",\n":
                j += 1
            val = body[i:j].strip()
            i = j
        fields[name] = " ".join(val.split())
        nxt = body.find(",", i)
        i = nxt + 1 if nxt >= 0 else n
    return fields


def _clean_doi(doi):
    doi = (doi or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.strip()


# ---------------------------------------------------------------- HTTP + cache
def _get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with _DIRECT.open(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def load_cache(use):
    if not use or not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text())
    except Exception:
        return {}
    now = time.time()
    return {k: v for k, v in data.items() if now - v.get("_ts", 0) < CACHE_TTL}


def save_cache(cache, use):
    if not use:
        return
    _HOME.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=0))


# ---------------------------------------------------------------- resolvers
def crossref_by_doi(doi):
    try:
        j = json.loads(_get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"))
        t = j["message"].get("title") or [""]
        return {"found": True, "source": "crossref/doi", "title": t[0] if t else ""}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"found": False, "source": "crossref/doi"}
        raise


def openalex_by_doi(doi):
    try:
        j = json.loads(_get(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}"))
        return {"found": True, "source": "openalex/doi", "title": j.get("title") or ""}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"found": False, "source": "openalex/doi"}
        raise


def arxiv_by_id(aid):
    aid = re.sub(r"^arxiv:", "", aid, flags=re.I).strip()
    xml = _get(f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}",
               accept="application/atom+xml")
    # an unknown id returns a feed with zero <entry> (or an entry whose title is "Error")
    m = re.search(r"<entry>.*?<title>(.*?)</title>", xml, re.S)
    if not m or "Error" in m.group(1):
        return {"found": False, "source": "arxiv"}
    return {"found": True, "source": "arxiv", "title": " ".join(m.group(1).split())}


def crossref_by_title(title):
    q = urllib.parse.urlencode({"query.bibliographic": title, "rows": "5"})
    j = json.loads(_get(f"https://api.crossref.org/works?{q}"))
    best, best_r = None, 0.0
    for it in j["message"].get("items", []):
        cand = (it.get("title") or [""])[0]
        r = title_sim(title, cand)
        if r > best_r:
            best, best_r = cand, r
    if best is None:
        return {"found": False, "source": "crossref/title"}
    return {"found": True, "source": "crossref/title", "title": best}


_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(.+)$", re.I)


def _effective_ids(entry):
    """(doi, arxiv) after recovering an arXiv id hidden inside a DataCite arXiv DOI."""
    doi, arxiv = entry["doi"], entry["arxiv"]
    if not arxiv and doi:
        m = _ARXIV_DOI.match(doi)  # Zotero writes preprints as 10.48550/arXiv.<id>
        if m:                      # which neither Crossref nor OpenAlex index by DOI
            arxiv = m.group(1)
    return doi, arxiv


def _cache_key(entry):
    doi, arxiv = _effective_ids(entry)
    return doi and f"doi:{doi.lower()}" \
        or arxiv and f"arxiv:{arxiv.lower()}" \
        or f"title:{norm_title(entry['title'])}"


def resolve(entry, cache):
    doi, arxiv = _effective_ids(entry)
    ck = _cache_key(entry)
    if ck in cache:
        return cache[ck]
    res = None
    if arxiv:
        res = arxiv_by_id(arxiv)
    elif doi:
        res = crossref_by_doi(doi)
        if not res.get("found"):
            time.sleep(DELAY)
            res = openalex_by_doi(doi)
    elif entry["type"] in NON_INDEXED_TYPES:
        res = {"found": False, "source": "no-id", "note": "no DOI/arXiv — cited by URL, verify by hand"}
    elif entry["title"]:
        res = crossref_by_title(entry["title"])
    else:
        res = {"found": False, "source": "none", "note": "no doi/arxiv/title in entry"}
    # DOI dead-ended but we have a title: fall back to a title search so a real paper with a
    # stale/wrong DOI still verifies as existing (the DOI miss is noted in the source).
    if not res.get("found") and doi and entry["title"]:
        time.sleep(DELAY)
        t = crossref_by_title(entry["title"])
        if t.get("found"):
            t["source"] = "crossref/title(doi-404)"
            res = t
    res["_ts"] = time.time()
    cache[ck] = res
    return res


def classify(entry, res, threshold):
    if res.get("source") == "no-id":
        return "NO-ID", ""
    if not res.get("found"):
        return "UNRESOLVED", ""
    found_t = res.get("title", "")
    if not entry["title"] or not found_t:
        return "RESOLVED", ""  # nothing to compare against (e.g. arXiv-only, no title)
    ratio = title_sim(entry["title"], found_t)
    if ratio < threshold:
        return "TITLE-MISMATCH", f"found: {found_t!r} (sim {ratio:.2f})"
    return "RESOLVED", ""


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Verify BibTeX citations exist in public indexes.")
    ap.add_argument("bib", help="path to references.bib")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any UNRESOLVED/TITLE-MISMATCH")
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    ap.add_argument("--only-problems", action="store_true", help="print only non-RESOLVED rows")
    ap.add_argument("--key", action="append", help="verify only these cite key(s)")
    ap.add_argument("--title-threshold", type=float, default=0.82)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ignore cached results, re-fetch")
    args = ap.parse_args()

    text = Path(args.bib).read_text(encoding="utf-8", errors="replace")
    entries = parse_bib(text)
    if args.key:
        want = set(args.key)
        entries = [e for e in entries if e["key"] in want]
    if not entries:
        print("no entries parsed (check the path / --key)", file=sys.stderr)
        return 2

    cache = {} if args.refresh else load_cache(not args.no_cache)
    rows = []
    for e in entries:
        served = _cache_key(e) in cache
        try:
            res = resolve(e, cache)
        except Exception as ex:  # network/parse hiccup -> report, don't crash the gate
            res = {"found": False, "source": "error", "note": str(ex)}
        status, detail = classify(e, res, args.title_threshold)
        rows.append({"key": e["key"], "status": status, "source": res.get("source", ""),
                     "title": e["title"], "detail": detail or res.get("note", "")})
        if not served:  # be polite to the public APIs between live lookups
            time.sleep(DELAY)
    save_cache(cache, not args.no_cache)

    # NO-ID (software/web cites) is informational, not a gate failure; UNRESOLVED and
    # TITLE-MISMATCH are the citations that may not exist.
    gate_fail = [r for r in rows if r["status"] in ("UNRESOLVED", "TITLE-MISMATCH")]
    flagged = [r for r in rows if r["status"] != "RESOLVED"]
    if args.json:
        print(json.dumps({"total": len(rows), "gate_failures": len(gate_fail),
                          "rows": rows}, indent=2))
    else:
        shown = flagged if args.only_problems else rows
        w = max((len(r["key"]) for r in shown), default=3)
        for r in shown:
            line = f"{r['status']:<15} {r['key']:<{w}}  {r['source']}"
            if r["detail"]:
                line += f"  — {r['detail']}"
            print(line)
        c = lambda s: sum(1 for r in rows if r["status"] == s)
        print(f"\n{len(rows)} entries: {c('RESOLVED')} RESOLVED, {c('UNRESOLVED')} UNRESOLVED, "
              f"{c('TITLE-MISMATCH')} TITLE-MISMATCH, {c('NO-ID')} NO-ID (verify by hand)",
              file=sys.stderr)
    return 1 if (args.strict and gate_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
