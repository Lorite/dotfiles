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
3. *(not patched — handled in the exporter)* the filter parser can't read the escaped-quote
   argument form the extension writes; see below.

Refresh a patch after upstream moves: build with `--latest`, fix the conflict in the build
dir, then `git format-patch` back into `patches/`.

## `export-templates.py`

The extension's settings export keeps each template under its own `template_<id>` key; the
CLI wants one JSON file per template in a directory. This bridges them, reading **only**
`template_*` and `property_types` — never `interpreter_settings`, so **API keys cannot
leak** into the output.

Two things it must keep doing:

- **Number the filenames by `template_list` order.** Several templates share a trigger —
  `Wikipedia` and `Wikipedia (person)` have an *identical* regex — and the extension breaks
  the tie by list order. Export them alphabetically and a Wikipedia article clips as a
  **person**.
- **Unescape filter arguments only.** The extension stores `{{words|calc:\"/238\"}}`; the
  CLI can't parse that and returns the value **unfiltered**, so `read_length_minutes`
  silently becomes the raw word count (748 instead of 3.14). But LLM interpreter prompts
  (`{{"…"}}`) contain `\"` legitimately — unescaping those corrupts the prompt. The rewrite
  is deliberately narrow.

Re-run it whenever you change templates in the extension.

## Known gaps

- **YouTube**: metadata only, and thin — `url`, `channel`, `duration` all come out empty,
  and there is no transcript. Needs a `yt-dlp` enrichment step (not built yet).
- The `first` filter crashes on YouTube (`JSON.parse` on a plain string).
- No JavaScript execution: great for articles/blogs/docs, useless for SPA-rendered pages.
