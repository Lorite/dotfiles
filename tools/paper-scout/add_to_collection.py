#!/usr/bin/env python3
"""
Add an EXISTING Zotero item to a collection.

Why this exists: Zotero's local API (:23119/api) is read-only (POST blocked, PATCH → 501)
and the connector only *creates* new items — neither can file an existing item into a
collection. The Zotero Web API (api.zotero.org) can, via a read/write API key; the change
syncs down to the local app. So when paper-scout's dedup finds a picked paper already in
the library, it calls this to add that item to "Scout Inbox" instead of duplicating it.

Setup (once): create a read/write key at https://www.zotero.org/settings/keys , then
  printf '%s' '<KEY>' > ~/.config/paper-scout/zotero-api-key && chmod 600 ~/.config/paper-scout/zotero-api-key
(or export ZOTERO_API_KEY=...). The user id is auto-detected from the local API.

Usage:
  add_to_collection.py <itemKey> <collectionKey>        # by keys
  add_to_collection.py --doi <DOI> <collectionKey>      # look the item up by DOI first
"""
import json, os, sys, urllib.request, urllib.error
from pathlib import Path

LOCAL = "http://localhost:23119/api/users/0"
WEB = "https://api.zotero.org"
_HOME = Path(os.environ.get("PAPER_SCOUT_HOME", Path.home() / ".config/paper-scout"))
# Local calls bypass any institutional proxy; web calls (api.zotero.org) use the default opener.
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
    import urllib.parse
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


def main():
    args = sys.argv[1:]
    by_doi = "--doi" in args
    args = [a for a in args if a != "--doi"]
    if len(args) != 2:
        sys.exit("usage: add_to_collection.py [--doi] <itemKey|DOI> <collectionKey>")
    ident, coll_key = args
    key = api_key()
    uid = os.environ.get("ZOTERO_USER_ID") or local_userid()
    item_key = item_key_for_doi(ident) if by_doi else ident

    st, raw, _ = web(f"/users/{uid}/items/{item_key}", key)
    item = json.loads(raw)
    cols = item["data"].get("collections", [])
    if coll_key in cols:
        print(f"already in collection {coll_key} — nothing to do")
        return
    ver = item["version"]
    body = json.dumps({"collections": cols + [coll_key]}).encode()
    try:
        st, _, _ = web(f"/users/{uid}/items/{item_key}", key, method="PATCH", body=body,
                       headers={"Content-Type": "application/json",
                                "If-Unmodified-Since-Version": str(ver)})
        print(f"OK ({st}) — added item {item_key} to collection {coll_key}. "
              "Local Zotero syncs it down shortly.")
    except urllib.error.HTTPError as e:
        sys.exit(f"PATCH failed HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")


if __name__ == "__main__":
    main()
