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
import itertools
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VAULT = Path.home() / "git/lorite-obsidian-notes"
DAILY_DIR = VAULT / "diary/daily"
SENTINEL = VAULT / ".process_daily_note_done"
QUICKADD_PROCESS_CMD = "quickadd:choice:a8895b3d-1db5-4476-8c7d-9c5a0eca8a6c"
STT_CSV = VAULT / ".android-simpletimetracking/stt_records_automatic.csv"
STT_HEADING = "# 📑 [[Android SimpleTimeTracker App]] Logs"
STT_LINE_RE = re.compile(r"^- (\d\d:\d\d)–(\d\d:\d\d) — ")

# ActivityWatch CSVs the note's AW sections render from, written by the 01:00
# lorite-nightly batch (aw_daily_export.py + aw_extra_export.py, both on the server).
# One representative file per exporter is enough to tell whether it has run for a date.
AW_EXPORT_FILES = (
    VAULT / "_android-appusage/LaptopITU/daily/{date}/LORI_Activity_{date}.csv",
    VAULT / "_activitywatch/daily/{date}/AW_Categories_{date}.csv",
)
# Existence is NOT enough for the HA-derived half. write_csv() emits the header row
# unconditionally, so an export that ran before ha_to_aw.py imported the day leaves a
# header-only file that passes an is_file() check and renders as an empty section — the
# 2026-08-13 -> 08-18 failure. These files must therefore carry at least one DATA row.
#
# Places was the canary here until 2026-08-25, on the reasoning that "location is a state
# series and any normal day produces at least one named-zone event". That is false while
# travelling, and it cost three days of notes. person.alejandro went `not_home` at
# 2026-08-20T02:59:59Z (working from Spain, outside every named HA zone) and stayed there;
# ha_to_aw.normalise() drops `not_home` deliberately — "the absence of information, not a
# place. Named zones only." So Places was correctly empty, the gate read correctly-empty as
# not-yet-arrived, and 2026-08-22 -> 08-24 never got a note at all.
#
# AW_Timeline replaces it and is a strictly better canary for the same question ("has the
# HA import landed for this day?"): it carries the HA-derived `activity` stream alongside
# the local app stream, so it is non-empty on travel days AND still proves ha_to_aw ran.
# Do NOT re-add a location-derived file here — location is legitimately absent whenever the
# user is somewhere they have not named, which is exactly when they are most likely to be
# working oddly and to want the note.
AW_EXPORT_FILES_NONEMPTY = (
    # The Day Log section renders from this one. A note built before it lands freezes the
    # section empty forever, which is the exact failure this guard exists to prevent.
    VAULT / "_activitywatch/daily/{date}/AW_Timeline_{date}.csv",
)
# How long to keep waiting for those CSVs before building the note without them.
# Processing STRIPS the %% run %% blocks, so a note is rendered exactly once and its
# AW sections are frozen from then on (only SimpleTimeTracker has a top-up path,
# refresh-stt). Building early therefore freezes an empty table permanently — which is
# precisely what happened while obsidian-daily-note.timer's OnUnitActiveSec=1h drift put
# it in the 00:30-00:58 window, minutes AHEAD of the 01:00 export, every night.
# The grace period is bounded so a day whose export never arrives (server off, exporter
# broken) still gets a note eventually: a note with an empty table beats no note at all.
AW_EXPORT_GRACE_DAYS = 3

# SimpleTimeTracker "activity name" -> Media DB media type, for the entries whose
# comment names a catalogable work. Only these activities are looked up / created;
# everything else (Social Media, YouTube, Read, …) is left to Virtual Linker to
# bracket if a note already exists, and is never queried or auto-created. Extend
# this table to cover more media kinds.
STT_ACTIVITY_MEDIA_TYPE = {
    "Series": "series",
    "Movie": "movie",
    "Film": "movie",
    "Videogame": "videogame",
    "Book": "book",
    "Manga": "comic_or_manga",
    "Comic": "comic_or_manga",
    "Boardgame": "boardgame",
}
# Titles that matched no Media DB entry (or errored) land here for the user to
# resolve by hand — we never guess a wrong note.
REVIEW_QUEUE = VAULT / "ai_chats/notes/STT media to triage.md"

# Runs in the Obsidian app via `obsidian eval`. Given a title + media type it:
# resolves existing notes (by name OR alias) to avoid duplicates; else queries
# the type's Media DB providers, takes an EXACT normalized-title match only
# (never a fuzzy guess), creates the note, and injects the bare title as an alias
# so its year-suffixed filename still resolves and Virtual Linker will bracket the
# log line. Returns a JSON status. Placeholders %TITLE%/%TYPE% are json-substituted.
MEDIA_CREATE_JS = r"""(async () => {
  const title = %TITLE%, mtype = %TYPE%;
  const p = app.plugins.plugins["obsidian-media-db-plugin"];
  if (!p || !p.apiManager) return JSON.stringify({status: "error", err: "media-db not loaded"});
  // Diacritic- + case-insensitive so "Pokemon" matches an accented "Pokémon" alias.
  const norm0 = s => (s == null ? "" : String(s)).normalize("NFD")
                       .replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  const ntitle = norm0(title);
  // Existing? The (already-cleaned) title exactly equals the note's filename, its filename
  // without a trailing " (year)" (Media DB names notes "Title (2013–2016)"), or any alias.
  // Exact match, not substring, so "…on Android" can't false-match [[Android]].
  const eq = c => norm0(c) === ntitle;
  const existing = app.vault.getMarkdownFiles().find(f => {
    if (eq(f.basename) || eq(f.basename.replace(/\s*\(\d{4}[^)]*\)\s*$/, ""))) return true;
    const al = app.metadataCache.getFileCache(f)?.frontmatter?.aliases;
    const arr = Array.isArray(al) ? al : (al ? [al] : []);
    return arr.some(eq);
  });
  if (existing) return JSON.stringify({status: "exists", path: existing.path});
  const am = p.apiManager;
  const apis = am.apis.filter(a => (a.types || []).includes(mtype)).map(a => a.apiName);
  if (!apis.length) return JSON.stringify({status: "no-provider"});
  // A provider with a missing/invalid API key can hang forever; cap every call.
  const withTimeout = (promise, ms) => Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error("provider timeout")), ms)),
  ]);
  let results;
  try { results = await withTimeout(am.query(title, apis), 15000); }
  catch (e) { return JSON.stringify({status: "error", err: String(e)}); }
  const norm = s => (s == null ? "" : String(s)).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const nt = norm(title);
  const pick =
       (results || []).find(r => r.type === mtype && norm(r.title) === nt)
    || (results || []).find(r => r.type === mtype && norm(r.englishTitle) === nt)
    || (results || []).find(r => norm(r.title) === nt);
  if (!pick) return JSON.stringify({status: "no-match", count: (results || []).length});
  let detailed;
  try { detailed = await withTimeout(am.queryDetailedInfo(pick), 15000); }
  catch (e) { return JSON.stringify({status: "error", err: String(e)}); }
  const before = new Set(app.vault.getMarkdownFiles().map(f => f.path));
  try { await p.createMediaDbNotes([detailed]); }
  catch (e) { return JSON.stringify({status: "error", err: String(e)}); }
  const created = app.vault.getMarkdownFiles().find(f => !before.has(f.path));
  if (!created) return JSON.stringify({status: "error", err: "no note after create"});
  try {
    await app.fileManager.processFrontMatter(created, fm => {
      const a = new Set(Array.isArray(fm.aliases) ? fm.aliases : (fm.aliases ? [fm.aliases] : []));
      a.add(title); fm.aliases = [...a];
    });
  } catch (e) { /* alias is best-effort; the note still exists */ }
  return JSON.stringify({status: "created", path: created.path, matched: pick.title, year: pick.year});
})()"""


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


def command_registered(cmd_id: str) -> bool:
    """Is `cmd_id` in Obsidian's command registry yet?"""
    code = f'JSON.stringify(!!app.commands.commands[{cmd_id!r}])'
    try:
        return "true" in obs("eval", f"code={code}", check=False).lower()
    except Exception:
        return False


def wait_for_command(cmd_id: str, timeout: float = 90) -> None:
    """Block until Obsidian has REGISTERED the command, before dispatching it.

    The vault runs Lazy Plugins, which keeps deferred plugins OUT of
    .obsidian/community-plugins.json and loads them itself on a timer. QuickAdd is set to
    startupType "long" (desktop longDelaySeconds = 15), while `run`, `dataview`,
    `templater-obsidian` and `virtual-linker` are "instant". The CLI socket answers well
    before that 15 s, so a headless run would fire quickadd:choice:... at a command that
    does not exist yet -- and executeCommandById() returns false SILENTLY. No macro runs,
    no sentinel is written, and step_process then waits out its entire budget for a result
    that was never coming. That is a startup RACE, not slowness: it presents as a plain
    timeout with no error, it is intermittent (a warm profile wins the race, a cold one
    loses), and no budget increase can fix it -- 900 s failed exactly like 193 s did.
    """
    if wait_for_predicate_quiet(lambda: command_registered(cmd_id), timeout):
        return
    # Dispatch anyway rather than failing outright: if the id is simply stale the command
    # will no-op as before, and the sentinel timeout still reports it.
    print(f"[warn] {cmd_id} not registered after {timeout:.0f}s — dispatching anyway",
          file=sys.stderr)


def wait_for_predicate_quiet(predicate, timeout: float, interval: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def active_note_path() -> str:
    """Vault-relative path of the active markdown editor, or "" if there is none."""
    code = ("JSON.stringify((app.workspace.getActiveViewOfType("
            "require('obsidian').MarkdownView)||{}).file?.path||'')")
    try:
        return obs("eval", f"code={code}", check=False).strip().strip('"').replace("=> ", "")
    except Exception:
        return ""


def ensure_active_note(date: str, attempts: int = 5) -> None:
    """Make the note the active markdown editor, retrying the open if something stole it."""
    want = vault_rel(date)
    for _ in range(attempts):
        if active_note_path().endswith(want):
            return
        obs("open", f"path={want}", check=False)
        time.sleep(2)
    print(f"[warn] {want} is not the active editor — dispatching anyway", file=sys.stderr)


def step_process(date: str) -> int:
    obs("open", f"path={vault_rel(date)}")
    time.sleep(1.5)
    SENTINEL.unlink(missing_ok=True)
    wait_for_command(QUICKADD_PROCESS_CMD)
    # Re-open AFTER the lazy plugins have settled, and confirm the note is really the
    # active editor before dispatching. The first open above happens seconds into startup;
    # by the time QuickAdd finishes loading, a plugin that opens its own view has had time
    # to steal the active leaf (this vault enables `homepage`, which does exactly that).
    # The macro's first act is getActiveViewOfType(MarkdownView), so losing the leaf makes
    # it write `(none)  error: no active markdown editor` — a sentinel whose path never
    # matches, so done() stays false and the caller times out on a macro that DID run.
    ensure_active_note(date)
    obs("command", f"id={QUICKADD_PROCESS_CMD}")

    def done() -> bool:
        return SENTINEL.exists() and SENTINEL.read_text().split("\t")[0] == vault_rel(date)

    # Budget = run blocks + link conversion. The block term used to be a flat 150 s on the
    # assumption that stabilization takes "<= 2 min", with only the LINE count varying --
    # which scales the wrong quantity: the blocks are the work (each queries tasks,
    # calendar, weather, AW, STT), while lines mostly mean rendered output that is already
    # there. 2026-08-19 (903 lines, 40 blocks) got 222 s and passed; 2026-08-20 (539 lines,
    # SAME 40 blocks) got 193 s and timed out twice. Same work, less budget, purely because
    # the note was shorter. So scale by the blocks and keep the line term for the link pass.
    body = read(date)
    n_lines = body.count("\n") + 1
    n_blocks = body.count("%% run start")
    budget = 150 + n_blocks * 3 + n_lines / 25 * 2
    # Escape hatch for diagnosing a note that will not finish: set a floor in seconds and
    # watch whether it EVER completes. A note that finishes at 400 s is slow (raise the
    # constants); one that never finishes has a genuinely stuck block, and no budget helps.
    override = os.environ.get("LORITE_MACRO_TIMEOUT")
    if override:
        budget = max(budget, float(override))
    wait_for(done, timeout=budget, interval=2,
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


def obsidian_reachable() -> bool:
    """True if the Obsidian CLI answers — the app is up, either the laptop's live
    instance or headless (Xvfb) on the server behind with-headless-obsidian.sh."""
    return subprocess.run(["obsidian", "eval", "code=1"],
                          capture_output=True, text=True).returncode == 0


def _eval_json(js: str, timeout: float = 45) -> dict:
    """Run JS via `obsidian eval` and parse its `=> <json>` result (the plugin
    also logs unrelated lines, so scan from the bottom for the JSON line). Always
    returns a dict; a subprocess timeout (e.g. a media provider that hangs on a
    missing API key) yields {"status": "error", ...} instead of blocking."""
    try:
        res = subprocess.run(["obsidian", "eval", f"code={js}"],
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "error", "err": f"eval timeout ({timeout:.0f}s)"}
    for line in reversed(res.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("=> "):
            line = line[3:]
        try:
            return json.loads(line)
        except (ValueError, TypeError):
            continue
    return {"status": "error", "err": f"no JSON from eval: {res.stdout.strip()[:200]!r}"}


def parse_stt_fields(line: str):
    """(category, activity, comment) for an STT bullet, else None. Shape:
    `- HH:MM–HH:MM — <cat> — <activity> — <comment>.`; the comment itself may
    contain ' — ' (e.g. a series title + episode)."""
    if not STT_LINE_RE.match(line):
        return None
    body = line[2:].rstrip()
    if body.endswith("."):
        body = body[:-1]
    parts = body.split(" — ")
    if len(parts) < 4:
        return None
    return parts[1], parts[2], " — ".join(parts[3:])


def create_or_check_media(title: str, mtype: str) -> dict:
    """Resolve/create the Media DB note for the cleaned `title` of `mtype` (see MEDIA_CREATE_JS)."""
    js = (MEDIA_CREATE_JS.replace("%TITLE%", json.dumps(title))
                         .replace("%TYPE%", json.dumps(mtype)))
    return _eval_json(js)


def wait_vault_indexed(timeout: float = 40) -> None:
    """A freshly launched (headless) Obsidian builds the metadata/alias index
    asynchronously; existence checks and Virtual Linker are unreliable until it is
    populated. Poll until ~all markdown files are cached (or the count stops
    growing), so we don't miss an existing note and duplicate/mis-queue it."""
    deadline = time.monotonic() + timeout
    prev = -1
    js = ('(()=>{try{const c=app.metadataCache.getCachedFiles?app.metadataCache.getCachedFiles().length:0;'
          'return JSON.stringify({c,t:app.vault.getMarkdownFiles().length,ready:!!app.workspace.layoutReady});}'
          'catch(e){return JSON.stringify({c:0,t:0,ready:false});}})()')
    while time.monotonic() < deadline:
        r = _eval_json(js, timeout=10)
        c, t, ready = r.get("c", 0), r.get("t", 0), r.get("ready", False)
        if ready and t and c >= t * 0.95:
            return
        if c > 0 and c == prev:  # stabilized even if slightly under the threshold
            return
        prev = c
        time.sleep(1)


def append_review_queue(items: list) -> None:
    """Append unresolved (title, type, why) media titles to the triage note, deduped."""
    REVIEW_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    existing = REVIEW_QUEUE.read_text(encoding="utf-8") if REVIEW_QUEUE.exists() else (
        "---\ntags:\n  - ai_generated\n---\n\n# STT media to triage\n\n"
        "SimpleTimeTracker media with no confident Media DB match — resolve by hand "
        "(the pipeline never guesses a wrong note).\n\n"
    )
    new = [f"- [ ] {t} ({m}) — {why}" for t, m, why in items
           if f"] {t} ({m})" not in existing]
    if new:
        if not existing.endswith("\n"):
            existing += "\n"
        REVIEW_QUEUE.write_text(existing + "\n".join(dict.fromkeys(new)) + "\n", encoding="utf-8")
        print(f"refresh-stt: queued {len(new)} media title(s) for triage")


def enrich_stt_media(date: str) -> bool:
    """Create Media DB notes for unlinked media rows in the note's STT section
    (routed by activity via STT_ACTIVITY_MEDIA_TYPE; exact-title match only, else
    queued for triage). Returns True if a relink pass is warranted (a note was
    created, or an existing note now resolves a still-plain row)."""
    lines = read(date).split("\n")
    try:
        h = lines.index(STT_HEADING)
    except ValueError:
        return False
    end = h + 1
    while end < len(lines) and lines[end].strip() != "---":
        end += 1
    already_queued = REVIEW_QUEUE.read_text(encoding="utf-8") if REVIEW_QUEUE.exists() else ""
    seen, queued, relink = set(), [], False
    for ln in lines[h + 1:end]:
        if "[[" in ln:
            continue  # already linked
        fields = parse_stt_fields(ln)
        if not fields:
            continue
        _cat, activity, comment = fields
        mtype = STT_ACTIVITY_MEDIA_TYPE.get(activity)
        if not mtype:
            continue  # not a catalogable media activity
        # Title for the DB query: drop the episode/track suffix, then strip common
        # free-text cruft ("Play … on Android"). Existing-note detection uses the
        # full `comment` (substring match), so this only matters for genuinely-new media.
        title = comment.split(" — ")[0].strip()
        title = re.sub(r"^(?:Play|Playing|Watch|Watching|Read|Reading|Listen(?:ing)? to)\s+",
                       "", title, flags=re.I)
        title = re.sub(r"\s+on (?:the )?(?:Android|iOS|iPhone|iPad|PC|Steam|Nintendo Switch|"
                       r"Switch|PS[45]|Xbox|the Switch)\b.*$", "", title, flags=re.I).strip()
        if not title or title == "undefined":
            continue
        if (title, mtype) in seen:
            continue
        seen.add((title, mtype))
        if f"] {title} ({mtype})" in already_queued:
            continue  # already pending triage — don't re-query a known miss every run
        res = create_or_check_media(title, mtype)
        st = res.get("status")
        if st == "created":
            relink = True  # a new note to bracket → relink is worth it
            print(f"refresh-stt: [{date}] created media note {res.get('path')}")
        elif st == "exists":
            # The note already exists; Virtual Linker will bracket it on the next
            # relink triggered by added/created content. Don't force a relink just
            # for this — a row Virtual Linker keeps missing would relink every run.
            pass
        elif st in ("no-match", "no-provider"):
            queued.append((title, mtype, st))  # genuinely not in any DB → triage
        else:  # "error" = transient (index not ready, provider hiccup) → retry next run
            print(f"refresh-stt: [{date}] media '{title}' ({mtype}) transient {res}")
    if queued:
        append_review_queue(queued)
    if relink:
        time.sleep(2)  # let new notes settle into the metadata / linker index
    return relink


def cmd_refresh_stt(lookback: int) -> None:
    """Top up the STT section of already-processed notes with entries the user
    back-filled in the app after the note was processed. Insertion is insert-only
    (existing lines and their wikilinks are never touched; a repeated (start, end)
    pair is matched as a multiset) and always runs, even with Obsidian closed.
    When Obsidian IS reachable it additionally enriches the topped-up notes:
    creates Media DB notes for new media rows (else queues them) and re-runs the
    daily-note macro so Virtual Linker brackets the newly inserted entities."""
    reachable = obsidian_reachable()
    if reachable:
        wait_vault_indexed()  # a fresh headless launch indexes asynchronously
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
        if reachable:
            # Enrich (create media notes / queue) then relink so Virtual Linker
            # brackets the new entities. Skip when nothing changed and there is
            # nothing to enrich (relink is idempotent but not free).
            relink = enrich_stt_media(date)
            if added or relink:
                try:
                    step_process(date)
                    print(f"refresh-stt: [{date}] re-linked STT entities")
                except Exception as e:  # a bad relink must not block other days
                    print(f"refresh-stt: [{date}] relink failed: {e}")


def _has_data_row(path: Path) -> bool:
    """Whether a CSV holds at least one row beyond its header."""
    try:
        with path.open(encoding="utf-8") as f:
            return sum(1 for _ in itertools.islice(f, 2)) > 1
    except OSError:
        return False


def aw_exports_missing(date: str) -> list[str]:
    """Names of the ActivityWatch export CSVs not yet usable for `date` (empty when ready).

    A file counts as missing when it is absent, or — for AW_EXPORT_FILES_NONEMPTY — when it
    exists but holds only its header, which is what an export that ran ahead of the HA
    import produces.
    """
    missing = [Path(str(t).format(date=date)).name
               for t in AW_EXPORT_FILES
               if not Path(str(t).format(date=date)).is_file()]
    for t in AW_EXPORT_FILES_NONEMPTY:
        p = Path(str(t).format(date=date))
        if not p.is_file():
            missing.append(p.name)
        elif not _has_data_row(p):
            missing.append(p.name + " (header only)")
    return missing


def aw_exports_ready(date: str) -> bool:
    """Whether `date`'s note may be built yet.

    True once every AW export CSV exists, or once the date is older than
    AW_EXPORT_GRACE_DAYS — past that the data is not coming and an AW-less note is
    better than no note. See AW_EXPORT_FILES for why building early is unrecoverable.
    """
    missing = aw_exports_missing(date)
    if not missing:
        return True
    age = (dt.date.today() - dt.date.fromisoformat(date)).days
    if age > AW_EXPORT_GRACE_DAYS:
        print(f"[{date}] AW exports still missing after {age}d "
              f"({', '.join(missing)}); building without them")
        return True
    print(f"[{date}] waiting for AW exports ({', '.join(missing)}); "
          f"will retry (grace {AW_EXPORT_GRACE_DAYS}d, age {age}d)")
    return False


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
        if not aw_exports_ready(date):
            continue  # build it on a later run, once the 01:00 export has landed
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
