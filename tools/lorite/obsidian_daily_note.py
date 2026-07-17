#!/usr/bin/env python3
"""Automate the Obsidian daily-note generation pipeline (headless, via the obsidian CLI).

Reproduces the manual flow for a daily note (diary/daily/<YYYY-MM-DD>.md):
  1. create - create the note via the obsidian CLI; Templater's file-template rule
              (^diary/daily/.*) expands templates/diary/daily.md on creation.
  2. process - trigger the QuickAdd macro "Process Daily Note (run, strip, links,
              lint)" (scripts/process_daily_note.js in the vault), which runs the
              whole in-app pipeline on the active note: Run-plugin blocks (tasks,
              calendar, weather, notes, SimpleTimeTracker, app usage — all
              retroactive, they take the note-title date as argument), strips the
              script code with the canonical regex, converts Virtual Linker
              virtual links to real wikilinks, lints, and saves.

The LLM summary of the "# ⁉️ Daily Questions" section is NOT done here — the
lorite-daily-note skill has the calling agent write it after `process`, then run
`finish` to lint the edited note again.

Requires the Obsidian desktop app running with the vault open (the obsidian CLI
talks to the live app).

Usage:
  obsidian_daily_note.py process <YYYY-MM-DD>   # create if missing + full pipeline
  obsidian_daily_note.py finish  <YYYY-MM-DD>   # lint + save (after summary edit)
  obsidian_daily_note.py pending [--since YYYY-MM-DD]
      # list dates (since --since, or from the last existing note, up to today)
      # that are missing, still contain %% run %% blocks, or have a TODO summary
  obsidian_daily_note.py auto [--lookback N]
      # create + process every missing/unprocessed note from yesterday back N
      # days (default 7; never today — its data is still accumulating). Exits 0
      # quietly when Obsidian isn't running. Run by obsidian-daily-note.timer
      # (systemd user unit, canonical copy in this directory). Does NOT write
      # the LLM summary — that stays with the lorite-daily-note skill.
      # Also tops up recent notes' SimpleTimeTracker sections (see below).
  obsidian_daily_note.py refresh-stt [--lookback N]
      # insert SimpleTimeTracker entries the user back-filled in the app AFTER
      # a note was processed (its STT section is otherwise frozen at process
      # time). Insert-only by (start, end) time pair — existing lines and their
      # wikilinks are never modified. File-only; also run hourly via `auto`.
"""

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path

VAULT = Path.home() / "git/lorite-obsidian-notes"
DAILY_DIR = VAULT / "diary/daily"
SENTINEL = VAULT / ".process_daily_note_done"
QUICKADD_PROCESS_CMD = "quickadd:choice:a8895b3d-1db5-4476-8c7d-9c5a0eca8a6c"
STT_CSV = VAULT / ".android-simpletimetracking/stt_records_automatic.csv"
STT_HEADING = "# 📑 [[Android SimpleTimeTracker App]] Logs"
STT_LINE_RE = re.compile(r"^- (\d\d:\d\d)–(\d\d:\d\d) — ")


def obs(*args: str, check: bool = True) -> str:
    res = subprocess.run(["obsidian", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"obsidian {' '.join(args)} failed: {res.stdout} {res.stderr}")
    return res.stdout.strip()


def note_path(date: str) -> Path:
    return DAILY_DIR / f"{date}.md"


def vault_rel(date: str) -> str:
    return f"diary/daily/{date}.md"


def read(date: str) -> str:
    return note_path(date).read_text(encoding="utf-8")


def wait_for(predicate, timeout: float, interval: float = 1.0, what: str = "condition") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise TimeoutError(f"timed out after {timeout:.0f}s waiting for {what}")


def step_create(date: str) -> None:
    p = note_path(date)
    if p.exists() and p.read_text(encoding="utf-8").strip():
        return
    # An existing 0-byte / whitespace-only stub (left by an interrupted create)
    # blocks Templater — `obsidian create` no-ops on an existing path — and is
    # then treated as "processed" forever. Remove it so the template can expand.
    # Delete through the app, not os.unlink: the app's vault index keeps the
    # just-unlinked path for a moment, so an immediate `create` dedup-suffixes
    # into "<date> 1.md" instead of the real path.
    if p.exists():
        obs("delete", f"path={vault_rel(date)}", check=False)
    p.unlink(missing_ok=True)
    obs("create", f"path={vault_rel(date)}")
    # Templater expands the daily template on creation; wait until it did.
    wait_for(
        lambda: note_path(date).exists() and "%% run start" in read(date),
        timeout=20,
        what=f"Templater expansion of {vault_rel(date)}",
    )
    print(f"[{date}] created from template")


def step_process(date: str) -> int:
    obs("open", f"path={vault_rel(date)}")
    time.sleep(1.5)
    SENTINEL.unlink(missing_ok=True)
    obs("command", f"id={QUICKADD_PROCESS_CMD}")

    def done() -> bool:
        return SENTINEL.exists() and SENTINEL.read_text().split("\t")[0] == vault_rel(date)

    # Budget: run-block stabilization (<= 2 min) + ~1.2 s per 25-line link chunk.
    n_lines = read(date).count("\n") + 1
    wait_for(done, timeout=150 + n_lines / 25 * 2, interval=2,
             what=f"process_daily_note macro on {vault_rel(date)}")
    _, status, debug = SENTINEL.read_text().split("\t", 2)
    SENTINEL.unlink(missing_ok=True)
    if status != "ok":
        raise RuntimeError(f"[{date}] macro failed: {status} — {debug}")
    links = sum(int(c.rsplit("=", 1)[1]) for c in json.loads(debug).get("chunks", []))
    print(f"[{date}] processed (virtual links converted: {links})")
    return links


def step_finish(date: str) -> None:
    obs("open", f"path={vault_rel(date)}")
    time.sleep(1)
    obs("command", "id=obsidian-linter:lint-file-unless-ignored")
    time.sleep(2)
    obs("command", "id=editor:save-file", check=False)
    time.sleep(1)
    print(f"[{date}] linted and saved")


def cmd_process(date: str) -> None:
    step_create(date)
    links = step_process(date)
    if links == 0:
        # Virtual Linker decorations occasionally miss a pass entirely (transient
        # rendering hiccup); zero conversions on a daily note is almost always
        # that, so retry the (idempotent) in-app pipeline once.
        print(f"[{date}] 0 links converted — retrying once")
        step_process(date)
    content = read(date)
    if "%% run" in content:
        raise RuntimeError(f"[{date}] %% run %% markers still present after processing")
    todo = "TODO." in content.split("# ⁉️ Daily Questions")[-1].split("---")[0]
    print(f"[{date}] OK — summary {'still TODO (LLM step pending)' if todo else 'filled'}")


def cmd_pending(since: str | None) -> None:
    existing = sorted(p.stem for p in DAILY_DIR.glob("????-??-??.md"))
    if since is None:
        since = existing[-1] if existing else dt.date.today().isoformat()
    day = dt.date.fromisoformat(since)
    today = dt.date.today()
    while day <= today:
        date = day.isoformat()
        p = note_path(date)
        if not p.exists():
            print(f"{date}\tmissing")
        else:
            content = p.read_text(encoding="utf-8")
            flags = []
            if not content.strip():
                flags.append("empty")  # 0-byte stub — needs a fresh create+process
            else:
                if "%% run start" in content:
                    flags.append("unprocessed")
                if "- In the morning, TODO." in content:
                    flags.append("summary-todo")
            if flags:
                print(f"{date}\t{','.join(flags)}")
        day += dt.timedelta(days=1)


def stt_lines_for(date: str) -> list[tuple[tuple[str, str], str]]:
    """((start, end), rendered bullet) for every CSV record starting on `date`,
    formatted byte-identically to scripts/daily/simple_time_tracker.js (which
    renders dataview's undefined for empty CSV fields as the literal string
    "undefined")."""
    fmt = lambda s: s if s else "undefined"
    hhmm = lambda ts: ts[11:16]
    out = []
    with STT_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            start = (row["time started"] or "").strip()
            name = (row["activity name"] or "").strip()
            if not start.startswith(date) or "Still" in name:
                continue
            comment = (row["comment"] or "").strip()
            comment_r = f"[[{comment}]]" if name == "Task" and comment else fmt(comment)
            key = (hhmm(start), hhmm((row["time ended"] or "").strip()))
            out.append((key, f"- {key[0]}–{key[1]} — {fmt((row['categories'] or '').strip())} — {fmt(name)} — {comment_r}."))
    return out


def cmd_refresh_stt(lookback: int) -> None:
    """Top up the STT section of already-processed notes with entries the user
    back-filled in the app after the note was processed. Insert-only: existing
    lines (incl. their Virtual Linker / media wikilinks) are never touched, so
    a repeated (start, end) pair is matched as a multiset. Pure file I/O — no
    Obsidian needed."""
    today = dt.date.today()
    for offset in range(1, lookback + 1):
        date = (today - dt.timedelta(days=offset)).isoformat()
        p = note_path(date)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")
        if not content.strip() or "%% run start" in content:
            continue  # unprocessed — the normal pipeline still owns it
        lines = content.split("\n")
        try:
            h = lines.index(STT_HEADING)
        except ValueError:
            continue
        end = h + 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        budget = {}
        for ln in lines[h + 1:end]:
            m = STT_LINE_RE.match(ln)
            if m:
                budget[m.groups()] = budget.get(m.groups(), 0) + 1
        added = 0
        for key, rendered in stt_lines_for(date):
            if budget.get(key, 0) > 0:
                budget[key] -= 1
                continue
            pos = next((i for i in range(h + 1, end)
                        if (m := STT_LINE_RE.match(lines[i])) and m.group(1) > key[0]),
                       None)
            if pos is None:  # after the last bullet, or just before --- if none exist
                pos = next((i + 1 for i in range(end - 1, h, -1) if STT_LINE_RE.match(lines[i])), end)
            lines.insert(pos, rendered)
            end += 1
            added += 1
        if added:
            if lines[end - 1].strip():  # keep the house-style blank line before ---
                lines.insert(end, "")
            p.write_text("\n".join(lines), encoding="utf-8")
            print(f"refresh-stt: [{date}] +{added} entries")


def cmd_auto(lookback: int) -> None:
    cmd_refresh_stt(10)  # file-only: runs even when Obsidian is closed
    res = subprocess.run(["obsidian", "vault"], capture_output=True, text=True)
    if res.returncode != 0:
        print("auto: Obsidian not running — skipping")
        return
    yesterday = dt.date.today() - dt.timedelta(days=1)
    for offset in range(lookback):
        date = (yesterday - dt.timedelta(days=offset)).isoformat()
        p = note_path(date)
        if p.exists():
            content = p.read_text(encoding="utf-8")
            if content.strip() and "%% run start" not in content:
                continue  # already processed (a TODO summary is the LLM step, not ours)
            # empty stub or leftover %% run %% blocks → (re)process below
        try:
            cmd_process(date)
        except Exception as e:  # keep going: one bad day must not block the rest
            print(f"auto: [{date}] failed: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("process", "finish"):
        s = sub.add_parser(name)
        s.add_argument("date", help="YYYY-MM-DD")
    s = sub.add_parser("pending")
    s.add_argument("--since", default=None, help="first date to check (default: from last existing note)")
    s = sub.add_parser("auto")
    s.add_argument("--lookback", type=int, default=7, help="days before today to catch up (default 7)")
    s = sub.add_parser("refresh-stt", help="insert late-entered SimpleTimeTracker entries into recent processed notes")
    s.add_argument("--lookback", type=int, default=10, help="days before today to top up (default 10)")
    args = ap.parse_args()

    if args.cmd == "pending":
        cmd_pending(args.since)
        return
    if args.cmd == "auto":
        cmd_auto(args.lookback)
        return
    if args.cmd == "refresh-stt":
        cmd_refresh_stt(args.lookback)
        return
    dt.date.fromisoformat(args.date)  # validate
    {"process": cmd_process, "finish": step_finish}[args.cmd](args.date)


if __name__ == "__main__":
    main()
