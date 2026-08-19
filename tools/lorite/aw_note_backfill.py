#!/usr/bin/env python3
"""Repair the ActivityWatch sections of daily notes that were built before the data arrived.

Notes built between 2026-08-13 and 2026-08-18 rendered an empty `Where I Was` and `Sleep`
section, and a Category Summary silently missing its `Rest > Sleep` row, because
obsidian-daily-note.service read ActivityWatch before ha_to_aw.py had imported the day
(fixed in dotfiles c5710d7). Processing STRIPS the %% run %% blocks, so a built note never
revisits its own data — the damage is permanent unless something writes it back.

This is that something. It re-renders ONLY the four AW subsections below, from the CSVs the
exporter has since filled in, and rewrites nothing else in the note.

    Where I Was          <- AW_Places_<date>.csv
    Sleep                <- AW_Sleep_<date>.csv
    Category Summary     <- AW_Categories_<date>.csv
    Work vs Personal     <- AW_CategoryContext_<date>.csv

The rendering is a port of scripts/daily/aw_extra.js, which is the live renderer and stays
the source of truth. A port can drift from its original silently, so --verify re-renders a
date whose note is known GOOD and diffs the result against what the note actually contains:
if the port cannot reproduce a note Obsidian rendered, it has no business rewriting six
others. 2026-08-11 and 2026-08-12 are the good dates (they were rebuilt by hand that day,
after the HA import had caught up).

    aw_note_backfill.py --verify 2026-08-11 2026-08-12
    aw_note_backfill.py --date 2026-08-13 --dry-run
    aw_note_backfill.py --range 2026-08-13 2026-08-18

Safety: every write is preceded by a .bak-<timestamp> copy (write them OUTSIDE the vault
with --backup-dir, or they get committed and Syncthing'd everywhere), a section is only ever replaced
between its own heading and the next `---` or `#` heading, and a section that would render
EMPTY is left untouched rather than blanked (an empty render means the CSV is still not
there, which is exactly the situation that caused the damage).
"""
import argparse
import csv
import datetime as dt
import difflib
import os
import re
import shutil
import sys
from pathlib import Path

VAULT = Path(os.environ.get("LORITE_VAULT", Path.home() / "git/lorite-obsidian-notes"))
AW_DIR = VAULT / "_activitywatch/daily"
NOTES = VAULT / "diary/daily"

# Virtual Linker rewrites plain text into [[wikilinks]] AFTER the Run block has produced it
# ("com.sec.android.app.shealth" becomes "com.sec.[[Android|android]].app.shealth"). That is
# a post-processing pass this script does not run, so --verify must compare modulo those
# brackets or every good note would look like a mismatch.
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
# The vault's linter converts _emphasis_ to *emphasis* as a later step, so the same render
# appears both ways depending on whether lint has run. Compare modulo the marker.
EMPHASIS_RE = re.compile(r"_([^_\n]+)_")
# The provenance footnote this script appends lives inside the last section it rewrites, so
# it must be stripped before comparing — otherwise every re-run "differs" from itself and
# stacks another copy of the line.
PROVENANCE_RE = re.compile(r"^_Regenerated \d{4}-\d\d-\d\d from the ActivityWatch exports.*?_$",
                           re.M | re.S)


def unlink_text(s: str) -> str:
    """Normalise a rendered section for comparison: drop Virtual Linker's aliased brackets
    and unify emphasis markers, neither of which this script is responsible for."""
    return EMPHASIS_RE.sub(r"*\1*", WIKILINK_RE.sub(r"\2", PROVENANCE_RE.sub("", s))).strip()


def read_csv(date: str, name: str):
    p = AW_DIR / date / f"AW_{name}_{date}.csv"
    if not p.is_file():
        return None
    with p.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows or None


def pretty(hms: str) -> str:
    """'6:33:00' -> '6 h 33 m'. Port of _awPretty; long durations read badly as clock time."""
    parts = str(hms or "").split(":")
    if len(parts) < 2:
        return hms or ""
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return hms or ""
    if h == 0 and m == 0:
        return "< 1 m"
    return (f"{h} h " if h > 0 else "") + f"{m} m"


def to_hms(secs: int) -> str:
    return "%d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60, secs % 60)


def render_places(date: str) -> str:
    data = read_csv(date, "Places")
    if not data:
        return ""
    rows = ["| Place\t| Time\t|", "|------------|------------|"]
    for r in data:
        rows.append(f"| {r['Place']}\t| {pretty(r['Duration'])}\t|")
    return "\n".join(rows)


def render_sleep(date: str) -> str:
    data = read_csv(date, "Sleep")
    if not data:
        return ""
    out = []
    for r in data:
        src = f" *({r['Source']})*" if r.get("Source") else ""
        out.append(f"- **{r['Start']} – {r['End']}** — {pretty(r['Duration'])}{src}")
    return "\n".join(out)


def render_categories(date: str) -> str:
    data = read_csv(date, "Categories")
    if not data:
        return ""
    rows = ["| Category\t| Time\t|", "|------------|------------|"]
    total = 0
    for r in data:
        rows.append(f"| {r['Category']}\t| {pretty(r['Duration'])}\t|")
        try:
            total += int(r["Seconds"])
        except (KeyError, ValueError):
            pass
    h, m = total // 3600, round((total % 3600) / 60)
    rows.append(f"| **Total tracked**\t| **{(str(h) + ' h ') if h > 0 else ''}{m} m**\t|")
    return "\n".join(rows)


CONTEXTS = ["work", "personal", "both", "unknown"]


def render_category_context(date: str) -> str:
    data = read_csv(date, "CategoryContext")
    if not data:
        return ""
    grid, col_totals, seen = {}, {}, set()
    for r in data:
        cat, ctx = r.get("Category"), r.get("Context")
        if not cat or not ctx:
            continue
        try:
            secs = int(r["Seconds"])
        except (KeyError, ValueError):
            secs = 0
        seen.add(ctx)
        grid.setdefault(cat, {})[ctx] = grid.setdefault(cat, {}).get(ctx, 0) + secs
        col_totals[ctx] = col_totals.get(ctx, 0) + secs
    if not grid:
        return ""
    # Columns PRESENT in the data, not columns with a non-zero total: keying on the total
    # meant one unparsable Seconds field collapsed the matrix to no columns at all.
    cols = [c for c in CONTEXTS if c in seen]
    row_total = lambda cat: sum(grid[cat].get(c, 0) for c in cols)
    cats = sorted(grid, key=row_total, reverse=True)
    cell = lambda s: pretty(to_hms(s)) if s else "—"
    head = "\t| ".join(["| Category"] + [c.capitalize() for c in cols] + ["Total |"])
    rows = [head, "|------------|" + "------------|" * (len(cols) + 1)]
    for cat in cats:
        rows.append(f"| {cat}\t| " + "\t| ".join(cell(grid[cat].get(c, 0)) for c in cols)
                    + f"\t| **{cell(row_total(cat))}**\t|")
    grand = sum(col_totals[c] for c in cols)
    rows.append("| **Total**\t| " + "\t| ".join(f"**{cell(col_totals[c])}**" for c in cols)
                + f"\t| **{cell(grand)}**\t|")
    return "\n".join(rows)


# heading in the note -> renderer. Matched loosely on the distinctive part, because the
# headings carry emoji and [[ActivityWatch]] wikilinks that are tedious to match exactly.
SECTIONS = [
    (re.compile(r"^# .*Where I Was\s*$", re.M), render_places, "Where I Was"),
    (re.compile(r"^# .*Sleep\s*$", re.M), render_sleep, "Sleep"),
    (re.compile(r"^# .*Category Summary\s*$", re.M), render_categories, "Category Summary"),
    (re.compile(r"^## .*Work [Vv]s Personal\s*$", re.M), render_category_context, "Work vs Personal"),
]

# A section body ends at the next heading or horizontal rule, whichever comes first.
BODY_END_RE = re.compile(r"^(?:---\s*$|#{1,6} )", re.M)


def extract_body(text: str, heading_match) -> tuple[int, int, str]:
    r"""Character span and content of the body under a heading (heading itself excluded).

    The heading patterns end in `\s*$`, and under re.M `\s` matches newlines — so the match
    can run past the heading's own line ending. Anchor on the first newline after the
    heading's start instead, or the replacement grows a blank line on every run.
    """
    nl = text.find("\n", heading_match.start())
    start = len(text) if nl == -1 else nl + 1
    m = BODY_END_RE.search(text, start + 1)
    end = m.start() if m else len(text)
    return start, end, text[start:end]


def build_sections(date: str) -> dict:
    return {name: fn(date) for _, fn, name in
            [(p, f, n) for p, f, n in SECTIONS]}


def apply_to_note(date: str, dry_run: bool, backup_dir=None) -> tuple[bool, list]:
    note = NOTES / f"{date}.md"
    if not note.is_file():
        return False, [f"{date}: no note"]
    text = note.read_text(encoding="utf-8")
    original = text
    log = []
    # Right to left, so earlier spans stay valid as later ones are replaced.
    edits = []
    for pattern, fn, name in SECTIONS:
        m = pattern.search(text)
        if not m:
            log.append(f"  {name}: heading not found — skipped")
            continue
        rendered = fn(date)
        if not rendered:
            log.append(f"  {name}: renders empty (CSV still missing) — left untouched")
            continue
        start, end, current = extract_body(text, m)
        if unlink_text(current).strip() == unlink_text(rendered).strip():
            log.append(f"  {name}: already correct")
            continue
        had = "empty" if not current.strip() else f"{len(current.strip().splitlines())} lines"
        log.append(f"  {name}: {had} -> {len(rendered.splitlines())} lines")
        edits.append((start, end, "\n\n" + rendered + "\n\n", name))
    if edits:
        # Say that the numbers moved, and why. Precedent: the 2026-08-11 note's Declared
        # Tasks section was regenerated the same way on 08-12 and carries the same kind of
        # line — a silently changed number is worse than a visibly wrong one. Placed at the
        # end of the last section touched, so it reads as a footnote to the whole block.
        names = ", ".join(e[3] for e in edits)
        stamp = dt.date.today().isoformat()
        note_line = (f"\n_Regenerated {stamp} from the ActivityWatch exports ({names}). "
                     f"The note was originally built before the day's Home Assistant import "
                     f"and phone sync had landed, so these sections were empty or incomplete._\n")
        last = max(range(len(edits)), key=lambda i: edits[i][0])
        st, en, rep, nm = edits[last]
        edits[last] = (st, en, rep.rstrip("\n") + "\n" + note_line, nm)

    for start, end, replacement, _ in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + replacement + text[end:]
    if text == original:
        return False, log
    if not dry_run:
        stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        if backup_dir:
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(note, backup_dir / f"{date}.md.bak-{stamp}")
        else:
            shutil.copy2(note, note.with_suffix(f".md.bak-{stamp}"))
        note.write_text(text, encoding="utf-8")
    return True, log


def verify(dates: list) -> int:
    """Re-render a known-good note and diff. Non-zero exit if the port cannot reproduce it."""
    bad = 0
    for date in dates:
        note = NOTES / f"{date}.md"
        if not note.is_file():
            print(f"{date}: no note to verify against")
            bad += 1
            continue
        text = note.read_text(encoding="utf-8")
        print(f"{date}:")
        for pattern, fn, name in SECTIONS:
            m = pattern.search(text)
            if not m:
                print(f"  {name}: heading not found")
                continue
            _, _, current = extract_body(text, m)
            rendered = fn(date)
            a = unlink_text(current).strip()
            b = unlink_text(rendered).strip()
            if a == b:
                print(f"  {name}: MATCH ({len(b.splitlines())} lines)")
            elif not a and not b:
                print(f"  {name}: both empty")
            else:
                bad += 1
                print(f"  {name}: MISMATCH")
                for line in list(difflib.unified_diff(
                        a.splitlines(), b.splitlines(),
                        fromfile="note", tofile="ported", lineterm=""))[:14]:
                    print("      " + line)
    return bad



def selftest() -> int:
    """Pin the table renderers against fixtures.

    --verify is the stronger check, but it can only cover Places and Sleep: the Categories
    and CategoryContext CSVs are rewritten by every later export (phone data lands up to 6 h
    late, and apply-categories.py re-runs nightly), so a note rendered days ago no longer
    matches its own source data. These fixtures are the fixed reference for those two.
    """
    import tempfile
    global AW_DIR
    saved, failures = AW_DIR, []
    tmp = Path(tempfile.mkdtemp())
    AW_DIR = tmp
    date = "2026-01-01"
    (tmp / date).mkdir(parents=True)

    def put(name, text):
        (tmp / date / f"AW_{name}_{date}.csv").write_text(text, encoding="utf-8")

    def check(label, got, want):
        if got != want:
            failures.append(label)
            print(f"  {label}: FAIL")
            for line in difflib.unified_diff(want.splitlines(), got.splitlines(),
                                             fromfile="want", tofile="got", lineterm=""):
                print("      " + line)
        else:
            print(f"  {label}: ok")

    put("Categories", '"Category","Duration","Seconds"\n'
                      '"Rest > Sleep","6:27:00","23220"\n'
                      '"Media > Social","0:31:00","1860"\n'
                      '"Email","0:00:20","20"\n')
    check("categories", render_categories(date), "\n".join([
        "| Category\t| Time\t|",
        "|------------|------------|",
        "| Rest > Sleep\t| 6 h 27 m\t|",
        "| Media > Social\t| 31 m\t|",
        # 20 s has no whole minute: _awPretty returns "< 1 m" rather than "0 m".
        "| Email\t| < 1 m\t|",
        "| **Total tracked**\t| **6 h 58 m**\t|"]))

    # Columns are the ones PRESENT, so no "both" column here; rows sort by row total.
    put("CategoryContext", '"Category","Context","Duration","Seconds"\n'
                           '"Media > Social","personal","0:23:00","1380"\n'
                           '"Media > Social","unknown","0:07:00","420"\n'
                           '"Coding","work","0:05:00","300"\n')
    check("category context", render_category_context(date), "\n".join([
        "| Category\t| Work\t| Personal\t| Unknown\tTotal |".replace("\tTotal |", "\t| Total |"),
        # one cell per context column, plus Category and Total
        "|------------|------------|------------|------------|------------|",
        "| Media > Social\t| —\t| 23 m\t| 7 m\t| **30 m**\t|",
        "| Coding\t| 5 m\t| —\t| —\t| **5 m**\t|",
        "| **Total**\t| **5 m**\t| **23 m**\t| **7 m**\t| **35 m**\t|"]))

    # An unparsable Seconds must not collapse the matrix to no columns at all - the column
    # set keys on contexts SEEN, not on non-zero totals. Regression from the JS.
    put("CategoryContext", '"Category","Context","Duration","Seconds"\n'
                           '"Coding","work","0:05:00","oops"\n')
    got = render_category_context(date)
    check("unparsable seconds still renders a Work column",
          got.splitlines()[0], "| Category\t| Work\t| Total |")

    # A missing CSV renders "" so the section is left untouched rather than blanked.
    check("absent csv -> empty", render_places(date), "")
    put("Places", '"Place","Duration","Seconds"\n')
    check("header-only csv -> empty", render_places(date), "")

    put("Sleep", '"Start","End","Duration","Minutes","Source"\n'
                 '"23:57","06:27","6:30:00","390","com.sec.android.app.shealth"\n')
    check("sleep", render_sleep(date),
          "- **23:57 – 06:27** — 6 h 30 m *(com.sec.android.app.shealth)*")

    AW_DIR = saved
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nselftest: {len(failures)} failure(s)")
    return len(failures)


def daterange(a: str, b: str):
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    while d0 <= d1:
        yield d0.isoformat()
        d0 += dt.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", action="append", default=[], help="a single date (repeatable)")
    ap.add_argument("--range", nargs=2, metavar=("FROM", "TO"))
    ap.add_argument("--verify", nargs="+", metavar="DATE",
                    help="re-render these known-good dates and diff; writes nothing")
    ap.add_argument("--selftest", action="store_true",
                    help="render fixtures and compare; writes nothing")
    ap.add_argument("--backup-dir", type=Path,
                    help="where .bak copies go; defaults beside the note, which pollutes the vault")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(1 if selftest() else 0)

    if args.verify:
        sys.exit(1 if verify(args.verify) else 0)

    dates = list(args.date)
    if args.range:
        dates += list(daterange(*args.range))
    if not dates:
        ap.error("give --date, --range or --verify")

    changed = 0
    for date in dates:
        did, log = apply_to_note(date, args.dry_run, args.backup_dir)
        print(f"{date}:" + ("" if log else " nothing to do"))
        for line in log:
            print(line)
        changed += bool(did)
    verb = "would change" if args.dry_run else "changed"
    print(f"\n{verb} {changed} of {len(dates)} note(s)")


if __name__ == "__main__":
    main()
