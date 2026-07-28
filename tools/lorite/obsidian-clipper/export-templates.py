#!/usr/bin/env python3
"""Export Obsidian Web Clipper templates into a directory the headless CLI can use.

The browser extension's settings export keeps every template under its own
`template_<id>` top-level key, but `obsidian-clipper -t <dir>` wants one JSON file
per template (and auto-matches by the template's URL `triggers`). This bridges the two.

Only `template_*` keys and `property_types` are read. `interpreter_settings` and the
other settings blocks are never touched, so no API keys can leak into the output.

Usage:
    ./export-templates.py                      # vault settings -> ~/.config/obsidian-clipper-cli
    ./export-templates.py --settings X --out Y
"""
import argparse
import json
import os
import re
import sys

DEFAULT_SETTINGS = os.path.expanduser("~/git/lorite-obsidian-notes/obsidian-web-clipper-settings.json")
DEFAULT_OUT = os.path.expanduser("~/.config/obsidian-clipper-cli")


def slugify(name):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(name)).strip("-").lower()
    return slug or "untitled"


# The extension stores filter arguments with escaped quotes, e.g.
#   {{words|calc:\"/238\"}}
# The headless CLI's filter parser does not strip that escaping: it fails to parse the
# argument, logs `Invalid calculation value`, and returns the value *unfiltered* — so
# read_length_minutes silently comes out as the raw word count instead of words/238.
# Verified on obsidian-clipper 1.7.1: \"/238\" -> 748 (wrong), "/238" and '/238' -> 3.14.
# Rewrite ONLY filter arguments (`|name:\"arg\"`). Two things must not be touched:
# interpreter prompts, written as {{"...long prompt..."}}, legitimately contain \" and
# break if unescaped; and ordinary prose may contain \" as well.
TEMPLATE_EXPR = re.compile(r"\{\{.*?\}\}", re.DOTALL)
FILTER_ARG = re.compile(r"\|(\w+):\\\"(.*?)\\\"")


def _fix_expr(match):
    expr = match.group(0)
    if expr.startswith('{{"'):        # interpreter prompt — leave entirely alone
        return expr
    return FILTER_ARG.sub(lambda m: '|%s:"%s"' % (m.group(1), m.group(2)), expr)


def unescape_filter_quotes(value):
    if isinstance(value, str):
        return TEMPLATE_EXPR.sub(_fix_expr, value)
    if isinstance(value, list):
        return [unescape_filter_quotes(v) for v in value]
    if isinstance(value, dict):
        return {k: unescape_filter_quotes(v) for k, v in value.items()}
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--settings", default=DEFAULT_SETTINGS, help="Web Clipper settings export JSON")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output directory (templates/ is created inside)")
    args = ap.parse_args()

    with open(args.settings) as fh:
        data = json.load(fh)

    tpl_dir = os.path.join(args.out, "templates")
    os.makedirs(tpl_dir, exist_ok=True)

    # Drop templates from a previous run so renamed/deleted ones don't linger and
    # keep matching URLs with stale rules.
    for stale in os.listdir(tpl_dir):
        if stale.endswith(".json"):
            os.remove(os.path.join(tpl_dir, stale))

    # Precedence matters: the CLI's matchTemplate() returns the FIRST template whose
    # trigger matches, and several templates here share a trigger (e.g. "Wikipedia" and
    # "Wikipedia (person)" have the same regex). The extension breaks that tie with
    # `template_list` order, so mirror it by numbering the filenames -- otherwise a
    # Wikipedia article silently clips with the person template.
    order = {}
    for idx, entry in enumerate(data.get("template_list") or []):
        tid = entry if isinstance(entry, str) else (entry or {}).get("id")
        if tid:
            order[tid] = idx

    templates = [
        (key, tpl) for key, tpl in data.items()
        if key.startswith("template_") and isinstance(tpl, dict)
    ]
    # Anything missing from template_list sorts after the ordered ones, by name.
    templates.sort(key=lambda kv: (order.get(kv[1].get("id"), len(order)), str(kv[1].get("name"))))

    written, seen = 0, {}
    for idx, (key, tpl) in enumerate(templates):
        slug = slugify(tpl.get("name"))
        seen[slug] = seen.get(slug, 0) + 1
        if seen[slug] > 1:
            slug = "%s-%d" % (slug, seen[slug])
        name = "%03d-%s.json" % (idx, slug)
        with open(os.path.join(tpl_dir, name), "w") as fh:
            json.dump(unescape_filter_quotes(tpl), fh, indent=2, ensure_ascii=False)
        written += 1

    prop_types = data.get("property_types")
    prop_path = None
    if prop_types is not None:
        prop_path = os.path.join(args.out, "property-types.json")
        with open(prop_path, "w") as fh:
            json.dump(prop_types, fh, indent=2, ensure_ascii=False)

    if not written:
        sys.exit("No template_* keys found in %s" % args.settings)

    print("Exported %d templates -> %s" % (written, tpl_dir))
    if prop_path:
        print("Wrote property types  -> %s" % prop_path)
    print()
    print("Use with:")
    print("  obsidian-clipper <url> -t %s \\" % tpl_dir)
    print("      --property-types %s -o <note.md>" % (prop_path or "<none>"))


if __name__ == "__main__":
    main()
