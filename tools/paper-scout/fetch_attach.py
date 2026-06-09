#!/usr/bin/env python3
"""
paper-scout — fetch paper PDFs (open-access directly, paywalled via your authenticated
browser) and attach them to Zotero, which recognizes each into a proper item + child PDF.

Auth model: a DEDICATED Chrome profile you log into the institutional proxy ONCE (headed).
The session persists in the profile; later runs reuse it. Your real browser/credentials
stay untouched — you do the login yourself, in this profile.

Two steps, run as SEPARATE commands (attaching inside the fetch process breaks Zotero):
  # 1. fetch all PDFs to disk (opens Chrome; log into the proxy once)
  <agent-venv>/bin/python tools/paper-scout/fetch_attach.py PAPERS.json
  # 2. select "Scout Inbox" in Zotero, then attach (a fresh command):
  <agent-venv>/bin/python tools/paper-scout/fetch_attach.py --attach-only

PAPERS.json (the agent writes this from the user-approved shortlist; no papers are
hard-coded here) is a list of:
  {"title": str,
   "doi":   str,
   "ieee":  "<IEEE article number>" | null,  # resolve via the DOI redirect, NOT the DOI
                                              # suffix (suffix == arnumber only for conf. papers)
   "oa":    "<direct OA pdf url>"    | null,  # open-access pdf; fetched without the browser
   "url":   "<item url>"}            # optional, e.g. the proxied IEEE link
Papers with neither `oa` nor `ieee` are reported NO-PDF (finish via the connector extension).

Runtime paths can be overridden with $PAPER_SCOUT_HOME (default: ~/.config/paper-scout).
"""
import json, os, re, sys, uuid, time, urllib.request, urllib.error
from pathlib import Path

_HOME = Path(os.environ.get("PAPER_SCOUT_HOME", Path.home() / ".config/paper-scout"))
PROFILE = _HOME / "pw-profile"
PDFDIR = _HOME / "pdfs"
CONN = "http://localhost:23119/connector"
ZAPI = "http://localhost:23119/api/users/0"
PROXY_HOST = "ieeexplore-ieee-org.kb-itu.idm.oclc.org"

# Connector calls go to localhost — never through an institutional http(s)_proxy
# (env proxies make Zotero's local endpoint return 500). Force a direct connection.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def zotero_attach(pdf_bytes, title, url, retries=3):
    """Upload PDF bytes; Zotero stores + recognizes into item + child PDF.

    A 500 here usually means Zotero's recognizer is busy/backed-up — restart Zotero if
    every attach 500s. Short, bounded retry so a bad state doesn't make the run crawl.
    """
    last = None
    for attempt in range(retries):
        # Zotero's saveStandaloneAttachment returns HTTP 500 on an empty url, so
        # always send a non-empty one (the recognizer overrides item metadata anyway).
        meta = {"url": url or "https://doi.org", "title": title,
                "id": str(uuid.uuid4()), "sessionID": str(uuid.uuid4())}
        req = urllib.request.Request(
            CONN + "/saveStandaloneAttachment", data=pdf_bytes, method="POST",
            headers={"Content-Type": "application/pdf", "X-Metadata": json.dumps(meta),
                     "X-Zotero-Connector-API-Version": "3", "User-Agent": "paper-scout/0.1"})
        try:
            with _DIRECT.open(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (500, 503) and attempt < retries - 1:
                time.sleep(2 + attempt * 2)   # 2, 4s
                continue
            raise
    raise last


def fetch_oa(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        body = urllib.request.urlopen(req, timeout=60).read()
        return (body, "ok") if body[:4] == b"%PDF" else (None, f"not-pdf {body[:12]!r}")
    except Exception as e:
        return None, f"err {e}"


def fetch_ieee(context, arnum):
    """Open the proxied IEEE page (authenticated) and pull the PDF bytes.

    Page navigation is best-effort (to establish the session/referer and discover
    the iframe PDF url); the actual byte download uses context.request (carries the
    profile cookies) and is always attempted even if the page misbehaves.
    """
    import re
    base = f"https://{PROXY_HOST}"
    iframe_src = None
    # --- best-effort: visit the article, scrape the stamp page for the PDF url ---
    try:
        page = context.new_page()
        page.goto(f"{base}/document/{arnum}", wait_until="domcontentloaded", timeout=60000)
        if "signon" in page.url or "login" in page.url.lower():
            try: page.close()
            except Exception: pass
            return None, "NOT-LOGGED-IN"
        try:
            page.goto(f"{base}/stamp/stamp.jsp?tp=&arnumber={arnum}",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            for fr in page.frames:
                if fr.url and ".pdf" in fr.url.lower():
                    iframe_src = fr.url; break
            if not iframe_src:
                el = page.query_selector("iframe")
                if el:
                    iframe_src = el.get_attribute("src")
        except Exception:
            pass
        try: page.close()
        except Exception: pass
    except Exception:
        pass
    # --- robust: HTML-parse the stamp page via request (independent of the page) ---
    if not iframe_src:
        try:
            html = context.request.get(f"{base}/stamp/stamp.jsp?tp=&arnumber={arnum}", timeout=60000).text()
            m = re.search(r'["\']([^"\']*(?:iel[0-9x]+/[^"\']+\.pdf|getPDF\.jsp[^"\']*)[^"\']*)["\']', html)
            if m:
                iframe_src = m.group(1)
        except Exception:
            pass
    # --- download candidates (always tried) ---
    candidates = []
    if iframe_src:
        candidates.append(iframe_src)
    candidates.append(f"{base}/stampPDF/getPDF.jsp?tp=&arnumber={arnum}&ref=")
    for c in candidates:
        if c.startswith("/"):
            c = base + c
        elif c.startswith("http") and PROXY_HOST not in c:
            c = c.replace("https://ieeexplore.ieee.org", base)
        try:
            body = context.request.get(c, timeout=60000).body()
            if body[:4] == b"%PDF":
                return body, "ok"
        except Exception:
            continue
    return None, "pdf-not-found"


def safe_name(title):
    return re.sub(r"[^\w]+", "_", title)[:60] + ".pdf"


def zotero_reachable():
    try:
        _DIRECT.open(CONN + "/ping", timeout=5)
        return True
    except Exception:
        return False


def attach_only():
    """Attach every PDF in PDFDIR to Zotero. MUST run in a clean process — attaching
    from inside the Playwright process makes Zotero's connector return HTTP 500."""
    if not zotero_reachable():
        sys.exit("Zotero not reachable on :23119 — open Zotero and retry.")
    pdfs = sorted(PDFDIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs in {PDFDIR}. Run a fetch first.")
    print(f"--- attaching {len(pdfs)} PDF(s) from {PDFDIR} (clean process) ---")
    ok = []
    for f in pdfs:
        body = f.read_bytes()
        try:
            zotero_attach(body, f.stem.replace("_", " "), "")
            ok.append(f.name)
            print(f"  OK          {len(body)//1024:>6}KB  {f.name[:55]}")
        except Exception as e:
            print(f"  ATTACH-FAIL {str(e)[:24]:>8}  {f.name[:55]}")
        time.sleep(2)   # brief settle before the next save
    print(f"\nAttached {len(ok)}/{len(pdfs)}. Recognition is async — check 'Scout Inbox' in ~30s.")
    print("Tip: clear PDFDIR (or move attached PDFs) before the next fetch to avoid re-attaching.")


def fetch_phase(papers):
    """Open the authenticated browser and save every PDF to PDFDIR. No Zotero writes here."""
    from playwright.sync_api import sync_playwright
    PROFILE.mkdir(parents=True, exist_ok=True)
    PDFDIR.mkdir(parents=True, exist_ok=True)
    fetched, missing = [], []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False)
        if any(pp.get("ieee") and not pp.get("oa") for pp in papers):
            probe = ctx.new_page()
            probe.goto(f"https://{PROXY_HOST}/Xplore/home.jsp", wait_until="domcontentloaded", timeout=60000)
            if "signon" in probe.url or "login" in probe.url.lower():
                print("\n>>> Log into the ITU/KB proxy in the opened Chrome window.")
                input(">>> Press Enter here once you can see IEEE Xplore content... ")
            probe.close()
        for pp in papers:
            title = pp["title"]
            if pp.get("oa"):
                body, st = fetch_oa(pp["oa"])
            elif pp.get("ieee"):
                body, st = fetch_ieee(ctx, pp["ieee"])
            else:
                body, st = None, "no-source"
            if body:
                (PDFDIR / safe_name(title)).write_bytes(body)
                fetched.append(title)
                print(f"  FETCHED  {len(body)//1024:>6}KB  {title[:55]}")
            else:
                missing.append((title, st))
                print(f"  NO-PDF   {st:>10}  {title[:55]}")
        ctx.close()
    return fetched, missing


def main():
    # Attach phase — clean process, no Playwright (see attach_only docstring).
    if "--attach-only" in sys.argv:
        attach_only()
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: fetch_attach.py PAPERS.json    (then, separately: --attach-only)\n"
                 'PAPERS.json = [{"title":..,"doi":..,"ieee":<num>|null,"oa":<pdf url>|null}, ...]')
    papers = json.loads(Path(args[0]).read_text())
    if not zotero_reachable():
        sys.exit("Zotero not reachable on :23119 — open Zotero and retry.")

    # Phase 1: fetch all PDFs to disk (Playwright).
    fetched, missing = fetch_phase(papers)

    # Phase 2 must be a SEPARATE command. Attaching from this process — or even a
    # subprocess of it — fails: after a Playwright run the inherited process state makes
    # Zotero's connector return HTTP 500. A freshly-launched command attaches fine.
    if fetched:
        print(f"\n{len(fetched)} PDF(s) saved to {PDFDIR}")
        print("Select 'Scout Inbox' in Zotero, then attach them with a SEPARATE command:\n")
        print(f"  {sys.executable} {Path(__file__).resolve()} --attach-only\n")
    if missing:
        print("No auto-source — use the Zotero Connector extension on these:")
        for title, st in missing:
            print(f"  - [{st}] {title}")


if __name__ == "__main__":
    main()
