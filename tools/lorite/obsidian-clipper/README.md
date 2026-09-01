# obsidian-clipper — headless CLI for the capture pipeline

Builds and feeds the **headless `obsidian-clipper` CLI**, the enrichment half of the
*"Automate the Obsidian capture + note-enrichment pipeline"* task. Turns a URL into a full
Obsidian note using the **same templates and the same `defuddle` engine** as the browser
extension — no browser, no display.

## ⚠️ Never use a plain upstream build

`npm i -g obsidian-clipper`, or building `main` yourself, gives you a CLI that **runs
successfully and produces empty notes** — frontmatter only, empty `title`, no content
(~115 bytes vs ~1.6 KB). It fails silently, which is the worst way to fail in an
unattended pipeline. Always build via `build-cli.sh`.

## Usage

```bash
./build-cli.sh                 # build the pinned upstream commit + our patches
./export-templates.py          # export your Web Clipper templates for the CLI
obsidian-clipper-cli <url> -t ~/.config/obsidian-clipper-cli/templates \
    --property-types ~/.config/obsidian-clipper-cli/property-types.json -o note.md
```

`build-cli.sh` clones to `~/.local/share/obsidian-clipper-cli`, checks out a **pinned**
commit, applies `patches/`, builds, **smoke-tests the result**, and installs a wrapper at
`~/.local/bin/obsidian-clipper-cli`. The smoke test is the point: it fails loudly if the
build regressed to empty output.

| command | does |
|---|---|
| `./build-cli.sh` | deterministic build (pinned commit + patches) |
| `./build-cli.sh --latest` | build today's `origin/main` — use to check whether the patches still apply or have been fixed upstream |
| `./build-cli.sh --check` | re-run the smoke test against the existing build |

## The patches (`patches/`)

Upstream carries three defects. A PR was closed as the CLI being work-in-progress, so we
carry the fixes ourselves rather than wait.

1. **Empty output** — the Node polyfill banner in `scripts/build-cli.mjs` defines
   `document` but not `navigator`/`getComputedStyle`, which `defuddle` needs; and
   `src/api.ts`/`src/cli.ts` hand `doc.documentElement` (an **Element**) to Defuddle, which
   expects a **Document**. Together: zero extracted content.
2. **Non-deterministic template matching** — `matchTemplate()` returns the *first* trigger
   match, but the CLI reads the template directory with `fs.readdirSync` **unsorted**; on
   ext4 that is hash order. Patch adds `.sort()`.
3. **Escaped quotes in filter arguments are silently dropped.** The extension writes
   `{{words|calc:\"/238\"}}`. The lexer turns `\"` into `"` but keeps the surrounding
   quotes, so the argument arrives **double-quoted** (`""/238""`); each filter strips only
   one pair, `calc` then reads `"` as its operator, rejects the argument, and returns the
   value **unfiltered**. Result: `read_length_minutes` came out as the raw word count
   (748 instead of 3.14) with only a console warning. Patch collapses the doubling in
   `evaluateFilter`.

Refresh a patch after upstream moves: build with `--latest`, fix the conflict in the build
dir, then `git format-patch` back into `patches/`.

## `export-templates.py`

The extension's settings export keeps each template under its own `template_<id>` key; the
CLI wants one JSON file per template in a directory. This bridges them, reading **only**
`template_*` and `property_types` — never `interpreter_settings`, so **API keys cannot
leak** into the output.

It must keep **numbering the filenames by `template_list` order**. Several templates share
a trigger — `Wikipedia` and `Wikipedia (person)` have an *identical* regex — and the
extension breaks the tie by list order. Export them alphabetically and a Wikipedia article
clips as a **person**.

Otherwise templates are written **verbatim**. An earlier version rewrote the escaped
quotes in filter arguments here; don't reintroduce that. Interpreter prompts (`{{"…"}}`)
contain `\"` legitimately, and a prompt containing `}}` can't be delimited by a regex, so
the rewrite silently corrupted one. That escaping is now handled inside the CLI by
patch 0003, where the parser actually knows what is an argument and what is prose.

Re-run it whenever you change templates in the extension.

## YouTube — use `youtube-enrich.py`, not the CLI directly

```bash
./youtube-enrich.py "https://www.youtube.com/watch?v=..." -o note.md
```

The CLI alone cannot do YouTube properly. It runs no JavaScript, and the JSON-LD in the
served HTML has only `name`, `thumbnailUrl`, `uploadDate` — **no `embedUrl`, `author` or
`duration`** — so the template's `url`, `channel` and `duration` render **empty**, the
`aliases` line starts with a dangling `"— "`, and `{{transcript}}` (a browser-extension
variable that does not exist in the CLI) leaves the Transcript section blank.

So `youtube-enrich.py` lets obsidian-clipper build the note from your real template, then
fills the gaps from `yt-dlp`: `url`, `channel`, `duration`, the alias, and the transcript
as `[mm:ss](url&t=Ns) text` lines under the template's own `# Transcript` heading — the
timestamp form the AI-summary prompt in that template asks for.

It only ever fills frontmatter keys that rendered **empty**, so it cannot clobber a value
the template got right. Auto-captions roll (each cue repeats the previous line plus a
word), so the VTT parser drops repeats — otherwise the transcript is several times longer
than the real one and much worse as LLM input.

Verified: *Never Gonna Give You Up* → 89 transcript lines; a 12:31 vault video → 378, with
`url`/`channel`/`duration`/`aliases` all filled. Unavailable videos exit with yt-dlp's own
message rather than a traceback.

## Instant phone capture — `inbox-watcher.py`

One-tap capture from any Android device, with no server endpoint and no secret on the
phone. The phone's only job is to drop a tiny file into the Syncthing-synced vault:

```
<vault>/ai_chats/inbox/capture-<anything>.md      # content: the shared URL on any line
```

`inbox-watcher.py` (run by `obsidian-inbox-watcher.timer`, every 2 min) picks stubs up,
clips the URL headlessly — `youtube-enrich.py` for YouTube, the CLI (with a
"Website Default" fallback, since the CLI errors on unmatched URLs instead of falling
back like the extension) for everything else — files the note where the matched
template's `path` says (`media/videos`, `media/wikis`, …) with a vault-convention
filename, and moves the stub to `processed/`. Failures go to `failed/` with a `.reason`
file; existing notes are never overwritten (a ` (2)` suffix is added).

## Automatic capture from what you actually watched

The phone share above is a *manual* trigger. `aw-youtube-capture.py` adds the automatic
one: it asks ActivityWatch which YouTube videos were genuinely watched and drops a stub
for each, so the same `inbox-watcher.py` path enriches them with no action from you.

```bash
./aw-youtube-capture.py --dry-run          # show what would be captured
./aw-youtube-capture.py --days 7           # look back a week
./aw-youtube-capture.py --min-minutes 10   # only longer watches
```

Runs nightly on the home server as part of `lorite-nightly.target`, which is the only
machine that sees the phone's buckets as well as the laptop's. It has no timer of its own:
the default look-back is 2 days and every candidate is deduped against the notes in
`media/videos` (by video id in the `url:` frontmatter) and the stubs in `ai_chats/inbox/`,
including `processed/` and `failed/`, so cadence only controls latency and a failed clip is
never retried in a loop.

Enrichment still happens on the laptop: the server has no `obsidian-clipper-cli` or
`yt-dlp` templates, so the stub travels by Syncthing and the laptop's already-running
`obsidian-inbox-watcher.timer` turns it into a note.

**What becomes a note is decided by CHANNEL, not by watch time**, because watch time gets
it wrong both ways: a 3-minute Fireship video is worth keeping and a 40-minute League of
Legends stream is not. The allow/deny lists live in the vault at
`ai_chats/queues/Video capture channels.md`, deliberately not in this repo: an edit there
reaches every host over Syncthing in seconds and can be made from the phone, whereas a
list here would only reach the home server on the next nightly `dotfiles-pull`.

Nothing is lost by not capturing. Every video already appears as a one-line entry in the
daily note's `# 🧭 ActivityWatch Day Log`, built from the same data. A channel in neither
list is reported for triage rather than captured or silently dropped.

**Why ActivityWatch and not the YouTube API.** There is no API option: YouTube deprecated
the watch-history playlist in 2016 and exposes no OAuth scope for history at all. Google
Takeout can export history, but only as periodic manual exports and **without watch
duration**, which is the one signal that matters here.

**Three buckets, because no single one is enough.** `currently-playing` (laptop) and
`media.playback` (phone) know real playback time but carry no URL; `web.tab.current` is the
only source of URLs but measures tab focus, so a video playing while you work elsewhere is
invisible to it. Playback comes from the media buckets, the URL from the web buckets matched
by title, and for phone viewing (which has no URL anywhere) a guarded `yt-dlp` search that
requires the channel to match and every word of the observed title to appear in the real one.
Measured: one talk was 15.1 min of tab dwell and 31.3 min of actual playback.

Tab dwell is afk-filtered so an idle open tab does not qualify. Playback deliberately is
**not**: watching involves no keyboard input, and afk-filtering cut one talk from 37.6 to
23.8 minutes.

Takeout is still worth one thing: a one-off backfill of history from before the watchers
existed, and of phone/TV viewing the desktop browser never saw.

**Phone side (build once per device, in Automate):**
1. **Content shared** block (makes the flow a share target; set MIME to `text/*`):
   https://llamalab.com/automate/doc/block/content_shared.html
2. **File write** block → path `.../<syncthing vault>/ai_chats/inbox/capture-{Now}.md`,
   content = the shared text. Add the device name to the filename if you want to know
   which device captured it.
3. Optional: a **Flow beginning → Toast** for feedback. That's the whole flow — two
   blocks. Works offline; the capture arrives when Syncthing next syncs.

Why a synced file and not a webhook or `obsidian://`: no auth secret on the phone, no
public endpoint, no Obsidian app required at capture time, offline-safe — and the vault
sync already exists. Latency is Syncthing's (seconds when online), which is fine for
fire-and-forget capture.

## Known gaps

- The `first` filter crashes on YouTube (`JSON.parse` on a plain string). Harmless — it
  only affects `thumbnailUrl`, which resolves anyway — but it is noisy on stderr.
- No JavaScript execution: great for articles/blogs/docs, useless for SPA-rendered pages.
- `youtube-enrich.py` fills the gaps *after* rendering, so a template that puts the channel
  inside `noteNameFormat` (the filename) still gets it empty.
