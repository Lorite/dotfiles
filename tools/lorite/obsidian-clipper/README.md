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
| `./knap-lint.mjs [--fix]` | check (or repair) the templates against knap |

## The patches (`patches/`)

Upstream carries two defects the CLI cannot work without. A PR was closed as the CLI being work-in-progress, so we carry the fixes ourselves rather than wait.

1. **Empty output** — the Node polyfill banner in `scripts/build-cli.mjs` defines
   `document` but not `navigator`/`getComputedStyle`, which `defuddle` needs; and
   `src/api.ts`/`src/cli.ts` hand `doc.documentElement` (an **Element**) to Defuddle, which
   expects a **Document**. Together: zero extracted content.
2. **Non-deterministic template matching** — `matchTemplate()` returns the *first* trigger
   match, but the CLI reads the template directory with `fs.readdirSync` **unsorted**; on
   ext4 that is hash order. Patch adds `.sort()`.

There used to be a third, unescaping quotes in filter arguments. It is **gone as of 2026-09-11**, along with the file it patched.

Refresh a patch after upstream moves: build with `--latest`, fix the conflict in the build
dir, then `git format-patch` back into `patches/`.

**A pin bump has to be applied on the home server by hand.** `dotfiles-pull.service` deliberately never runs build scripts, so pulling the new `build-cli.sh` does not rebuild anything. Until someone runs it there, the server keeps its old build. Run both, in this order, because the linter needs the `knap` the build installs:

```bash
ssh lorite@100.72.103.27 'cd ~/git/dotfiles/tools/lorite/obsidian-clipper && ./build-cli.sh && ./export-templates.py'
```

## Knap, and why template repair replaced patch 0003

Upstream commit `a9d33ce` (2026-09-03, *"Move templating to Knap"*) deleted `src/utils/renderer.ts` and moved the whole template engine into [Knap](https://knap.md/), a standalone package. Our pin moved from `ec27f8b` to `a9d33ce` on 2026-09-11. Patches 0001 and 0002 still apply unchanged. Patch 0003 could not, because its file no longer exists.

Knap did not fix the underlying problem, it only relocated it. The extension stores many expressions with escaped quotes, and Knap rejects or mangles them just as the old renderer did. Measured across the 33 exported templates:

| shape | count | what Knap does |
|---|---|---|
| `calc:\"/238\"` | 14 | rejects the argument, value passes through unfiltered |
| `replace:\"PT\",\"\",\"S\",\"\"` | 2 | rejects it, and Knap's `replace` takes only one `old:new` pair anyway |
| `date:\"YYYY-MM-DDTHH:mm\"` | 48 | **accepts it**, and wraps the timestamp in literal quotes |
| `join:\"\\n- \"` | 8 | **accepts it**, and leaks quotes between list items |
| `[data-testid=\"x\"]` in a selector | many | **accepts it**, and queries the DOM with the backslashes still in |
| `{{\"Make 4-5 lines description...\"}}` | 11 | no longer recognised as an interpreter prompt, so the prompt text renders into the note |

The silent half is the dangerous half, and it is much larger than the loud half. So the repair now happens to the **templates**, in `knap-lint.mjs`, which also fixes the browser extension if you re-import the repaired settings.

**The settings export was repaired at the source on 2026-09-11**, so exports now come out clean and the browser extension renders these expressions correctly too. It needs a re-import into Web Clipper to take effect there. The repair touched only template expressions and `property_types`: 155 changed lines against 155 removed, every one containing an escaped quote, with `general_settings`, `interpreter_settings` and `template_list` untouched.

`property-types.json` is linted alongside the templates, because its `defaultValue` fields are template expressions too. Ten of them were broken, including one Knap could not even parse (`Missing closing }}`).

```bash
./knap-lint.mjs                              # report
./knap-lint.mjs --fix                        # repair the exported CLI templates in place
./knap-lint.mjs --settings <export> --fix    # repair a settings export, to re-import into the extension
```

Every repair is parser-gated: a rewrite is only kept when Knap then renders it with **no errors**, so the linter cannot make a template worse than it found it. That is what makes this safe where the old regex rewrite in `export-templates.py` was not. Escaping is peeled to a fixed point, because some LinkedIn selectors are escaped twice over, and peeling stops at the first unbalanced quote count, which is what protects `replace:"\"":""` where the escaped quote **is** the value being searched for.

On the current templates it repairs 145 expressions and deliberately leaves 18 alone. `build-cli.sh` runs it in report mode as a gate, and `export-templates.py` runs it with `--fix` on every export, because the extension re-introduces the escaping each time you edit a template there.

**Verification of the migration.** Old build (`ec27f8b` + three patches, original templates) and new build (`a9d33ce` + two patches, repaired templates) produce **byte-identical notes** for an article URL and a YouTube URL. Without the template repair the same comparison showed the interpreter prompt leaking into `description:` and datetime properties coming out quoted.

## `render-template.mjs` — the templates, without a page to clip

Knap is a library as well as an engine, so a generator that already holds its data can render a Web Clipper template directly instead of keeping a hand-written copy of the note shape. That copy is what drifts: `gh_to_tasknote.py` carried a Python reproduction of templates "GitHub Issue" and "TASK - GitHub Issue" that had to be edited by hand whenever the real templates changed. It now renders those templates.

```bash
echo '{"template": <template json>, "variables": {...}, "propertyTypes": {...}}' | ./render-template.mjs
# -> {"noteName": ..., "frontmatter": ..., "content": ..., "properties": [...], "errors": [...]}
```

Variable names go to Knap verbatim, which is the trick that makes this work off-page: a template's `{{selector:[data-testid="issue-body-header-author"]}}` resolves from a variables key of that exact name, so a caller feeds scraped-looking fields straight from an API response. Unknown variables render empty, the same as a selector that matched nothing.

Frontmatter generation is transcribed from the clipper's own `src/utils/shared.ts` so property types serialise identically, which is why a rendered note is quoted the way the extension quotes it rather than the way the old Python did. Re-check that transcription after a pin bump. The clipper's `dist/api.mjs` would be a better source than a copy, but it currently fails to load: it imports `defuddle/full`, which is CommonJS, as if it were ESM.

Look up templates by `name`, not filename. The numeric prefix encodes `template_list` order and moves whenever templates are reordered in the extension.

## `export-templates.py`

The extension's settings export keeps each template under its own `template_<id>` key; the
CLI wants one JSON file per template in a directory. This bridges them, reading **only**
`template_*` and `property_types` — never `interpreter_settings`, so **API keys cannot
leak** into the output.

It must keep **numbering the filenames by `template_list` order**. Several templates share
a trigger — `Wikipedia` and `Wikipedia (person)` have an *identical* regex — and the
extension breaks the tie by list order. Export them alphabetically and a Wikipedia article
clips as a **person**.

Otherwise templates are written **verbatim**, and then repaired by `knap-lint.mjs` as a separate pass. Don't reintroduce a regex rewrite here. Interpreter prompts (`{{"…"}}`) contain `\"` legitimately, and a prompt containing `}}` can't be delimited by a regex, so the old rewrite silently corrupted one. The linter avoids that by only keeping a rewrite Knap accepts, and by skipping any span whose quotes don't balance.

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

`inbox-watcher.py` (triggered by `obsidian-inbox-watcher.path` on inotify, within a second, with `obsidian-inbox-watcher.timer` as an hourly backstop) picks stubs up,
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

**Enrichment runs on the home server too** (since 2026-09-02), so capture and enrichment are both there and nothing waits for the laptop. The server has its own `obsidian-clipper-cli` build, `yt-dlp`, and its own export of the templates, which it can regenerate itself because the Web Clipper settings file is in the Syncthing-synced vault. Its build was brought to the Knap pin on 2026-09-11 and verified byte-identical to the laptop's for the same article URL, with the YouTube path giving the same 89 transcript lines.

**Run it on one machine only.** The laptop's `.path` unit is not installed and its timer is disabled, deliberately: the inbox is synced, so two watchers would both see the same stub, and `inbox-watcher.py` never overwrites an existing note, so the loser of the race writes a ` (2)` duplicate rather than failing.

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

- ~~The `first` filter crashes on YouTube (`JSON.parse` on a plain string)~~ **fixed by the Knap migration (2026-09-11)**. Knap's `first` returns a plain string unchanged with no error, and a full `youtube-enrich.py` run now finishes with silent stderr, 89 transcript lines and every field filled.
- No JavaScript execution: great for articles/blogs/docs, useless for SPA-rendered pages.
- `youtube-enrich.py` fills the gaps *after* rendering, so a template that puts the channel
  inside `noteNameFormat` (the filename) still gets it empty.
