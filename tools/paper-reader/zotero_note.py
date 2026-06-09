#!/usr/bin/env python3
"""
Create a child NOTE on an existing Zotero item (paper-reader's structured read), via the
Zotero Web API. The local API (:23119/api) is read-only, so notes — like collection edits
(see ../paper-scout/add_to_collection.py) — go through api.zotero.org with a read/write key
and then sync down to the local app.

Shares paper-scout's setup (no extra config): API key at ~/.config/paper-scout/zotero-api-key
(or $ZOTERO_API_KEY); user id auto-detected from the local API. Override the data dir with
$PAPER_SCOUT_HOME. Uses only the Python stdlib (no venv needed).

Usage:
  zotero_note.py <itemKey> <note.html|->                 # note body from a file, or '-' = stdin
  zotero_note.py --doi <DOI> <note.html|->               # resolve the item by DOI first
  zotero_note.py <itemKey> <note> --tag-parent read,...  # ALSO add tags to the parent paper

Note body: HTML is preferred (Zotero notes are HTML). If the content contains no HTML tags,
a minimal Markdown->HTML conversion is applied (headings, **bold**, "- " bullet lists,
blank-line paragraphs) — enough for paper-reader's fixed template.
"""
import html as _html
import json, os, re, sys, urllib.request, urllib.error, urllib.parse
from pathlib import Path

LOCAL = "http://localhost:23119/api/users/0"
WEB = "https://api.zotero.org"
_HOME = Path(os.environ.get("PAPER_SCOUT_HOME", Path.home() / ".config/paper-scout"))
# Local calls bypass any institutional proxy; web calls use the default opener.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api_key():
    k = os.environ.get("ZOTERO_API_KEY")
    if k:
        return k.strip()
    f = _HOME / "zotero-api-key"
    if f.exists():
        return f.read_text().strip()
    sys.exit("No Zotero API key. Create a read/write key at "
             "https://www.zotero.org/settings/keys then:\n"
             f"  printf '%s' '<KEY>' > {f} && chmod 600 {f}")


def local_get(path):
    req = urllib.request.Request(LOCAL + path, headers={"Zotero-API-Version": "3"})
    with _DIRECT.open(req, timeout=8) as r:
        return json.loads(r.read())


def local_userid():
    # The local library id equals the zotero.org user id for a synced account.
    return str(local_get("/collections?limit=1")[0]["library"]["id"])


def item_key_for_doi(doi):
    """Exact-DOI lookup via the read-only local API (q= tokenizes DOIs → verify exactly)."""
    items = local_get(f"/items?q={urllib.parse.quote(doi)}&qmode=everything"
                       "&itemType=-attachment&format=json")
    for it in items:
        if (it["data"].get("DOI") or "").lower() == doi.lower():
            return it["key"]
    sys.exit(f"No item with DOI {doi} found in the local library.")


def web(path, key, method="GET", body=None, headers=None):
    h = {"Zotero-API-Version": "3", "Zotero-API-Key": key}
    if headers:
        h.update(headers)
    req = urllib.request.Request(WEB + path, data=body, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read(), r.headers


def md_to_html(text):
    """Minimal, dependency-free Markdown->HTML — only used when the input isn't already HTML."""
    out, ul = [], False

    def esc(s):
        s = _html.escape(s, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)

    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if line.startswith("- ") or line.startswith("* "):
            if not ul:
                out.append("<ul>"); ul = True
            out.append(f"<li>{esc(line[2:])}</li>")
            continue
        if ul:
            out.append("</ul>"); ul = False
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{esc(m.group(2))}</h{lvl}>")
        elif line.strip():
            out.append(f"<p>{esc(line)}</p>")
    if ul:
        out.append("</ul>")
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    by_doi = "--doi" in args
    tags = []
    if "--tag-parent" in args:
        i = args.index("--tag-parent")
        tags = [t.strip() for t in args[i + 1].split(",") if t.strip()]
        del args[i:i + 2]
    args = [a for a in args if a != "--doi"]
    if len(args) != 2:
        sys.exit("usage: zotero_note.py [--doi] <itemKey|DOI> <note.html|-> [--tag-parent t1,t2]")
    ident, note_src = args

    body_text = sys.stdin.read() if note_src == "-" else Path(note_src).read_text()
    note_html = body_text if "<" in body_text and ">" in body_text else md_to_html(body_text)

    key = api_key()
    uid = os.environ.get("ZOTERO_USER_ID") or local_userid()
    item_key = item_key_for_doi(ident) if by_doi else ident

    # Create the child note.
    payload = [{"itemType": "note", "parentItem": item_key, "note": note_html, "tags": []}]
    try:
        st, raw, _ = web(f"/users/{uid}/items", key, method="POST",
                         body=json.dumps(payload).encode(),
                         headers={"Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        sys.exit(f"note POST failed HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
    resp = json.loads(raw)
    if resp.get("failed"):
        sys.exit(f"note creation failed: {json.dumps(resp['failed'])[:200]}")
    note_key = (resp.get("successful") or {}).get("0", {}).get("key", "?")
    print(f"OK ({st}) — added note {note_key} to item {item_key}.")

    # Optionally tag the parent paper (e.g. 'read').
    if tags:
        st, raw, _ = web(f"/users/{uid}/items/{item_key}", key)
        item = json.loads(raw)
        have = {t["tag"] for t in item["data"].get("tags", [])}
        new = [{"tag": t} for t in tags if t not in have]
        if not new:
            print(f"parent already has tags {tags} — nothing to add")
        else:
            merged = item["data"].get("tags", []) + new
            pbody = json.dumps({"tags": merged}).encode()
            try:
                st, _, _ = web(f"/users/{uid}/items/{item_key}", key, method="PATCH", body=pbody,
                               headers={"Content-Type": "application/json",
                                        "If-Unmodified-Since-Version": str(item["version"])})
                print(f"OK ({st}) — tagged parent {item_key} with {[t['tag'] for t in new]}.")
            except urllib.error.HTTPError as e:
                print(f"WARN: parent tagging failed HTTP {e.code}: "
                      f"{e.read()[:160].decode(errors='replace')}")
    print("Local Zotero syncs the change down shortly.")


if __name__ == "__main__":
    main()
