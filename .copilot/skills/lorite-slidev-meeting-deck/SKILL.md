---
name: lorite-slidev-meeting-deck
description: Build a visual-first Slidev status/meeting deck (PhD 3-1, status updates) in the lorite_presentations_phd_slidev repo, using the lorite-phd theme. NOT for paper decks (those use lorite-slidev-presentation-*). Mirrors the structure of the prepared Obsidian meeting note's agenda, pulling content from that note, the recurring-meeting docx, and the relevant paper repo(s). Use when asked to make slides for a recurring PhD meeting or status update.
argument-hint: "date=<YYYY-MM-DD> [meeting=<short name>] [source=<meeting note / docx>]"
---

# lorite-slidev-meeting-deck — visual-first status/meeting decks

A **meeting** deck (PhD 3-1, status update) is different from a **paper** deck. Paper decks use
the `lorite-slidev-presentation-*` agents (14-section paper structure). A meeting deck's structure
**mirrors the prepared Obsidian meeting note's agenda** — one deck section per `# Pre-meeting Tasks
and Notes` item — kept *simple and visual* (the Word doc already holds the detail; the deck must
not repeat it). The supervisors' status shape (thesis objective · timeline · Past/Present/Future ·
actions) is just *one possible* agenda; **follow whatever the note defines, not a fixed template.**

Repo: `~/git/lorite_presentations_phd_slidev`. Theme: `slidev-theme-lorite-phd`. Node ≥ 20.

## 1. Gather content first (don't invent)
The deck is the visual layer over work already prepared:

- The **meeting note** in the vault (`calendar_events/<date> …`) — its `# Pre-meeting Tasks and
  Notes` agenda (Purpose + table + numbered items) is the deck's backbone and section list (pairs
  with `lorite-meeting-prep`).
- The **rolling docx** for the series (pairs with `lorite-recurring-meeting-docx`) — same content,
  concise.
- The **previous meeting's PDF** in the OneDrive series folder — copy its visual style and which
  assets exist.
- The **paper repo(s)** for any work being reported (e.g. the CLAWAR paper at
  `~/git/Drone-localization-support-from-a-quadruped-robot-CLAWAR-2026-`) — use the real abstract,
  numbers, and `figures/` rather than approximations or AI mock-ups (read `main.tex` for exact
  metrics/captions). Copy the figures into the deck's `public/<paper>/` (see §4).

## 2. Scaffold the project
Decks live at the repo root or under a subfolder (e.g. `meetings/`). From the theme dir:

```bash
cd ~/git/lorite_presentations_phd_slidev/slidev-theme-lorite-phd
npm run deck:new -- --name meetings/meeting_<name>_<YYYY-MM-DD> \
  --deck meeting-<name>-<YYYY-MM-DD> --title "<title>" --dry-run   # preview, then drop --dry-run
```

`--name` may be a nested path (the script `mkdir -p`s it and computes the theme path). The
scaffolder also writes `vite.config.ts` and copies `public/combined-logos.png` (both required — see
Gotchas). Then:

```bash
cd ~/git/lorite_presentations_phd_slidev/meetings/meeting_<name>_<YYYY-MM-DD>
npm run media:link        # symlinks assets/pictures -> OneDrive/Pictures, assets/videos -> OneDrive/Videos
npm install               # pinned @slidev/cli 52.14.1
```

## 3. Slide structure = the meeting note's agenda
Read the meeting note's `# Pre-meeting Tasks and Notes` (Purpose + agenda table + the numbered
items with their pre-meeting bullets) and **map it 1:1 onto the deck**, with a `layout: agenda`
separator before each section (the theme auto-injects the numbered agenda with the active item
highlighted — one `layout: agenda` slide per section, first heading = the section name):

1. **Cover** (`layout: cover`, `class: title`) — title, subtitle, presenter + supervisors +
   affiliations. The theme adds the logos/date/progress globally; do **not** add a logo image.
2. **Purpose** — the note's Purpose line as a few bullets + the framing.
3. For **each agenda item**: a `layout: agenda` separator (heading = the item name), then 1–N
   content slides built from that item's pre-meeting bullets. Expand the substantive items (e.g.
   the reported paper) into a few visual slides; keep the lighter ones to one slide.
4. **Thank you / discussion** (`layout: center`).

The section count and titles come from the note, **not** from this skill.

## 4. Visual-first rules
- ~1 slide per 2 min; **no text-only stretch > 2 slides**; the docx holds the detail.
- Big numbers as **stat callouts** (`<div class="px-4 py-2 bg-blue-50 border-l-4 border-blue-700">`
  with a `text-3xl font-bold` number) instead of prose.
- `<MediaFigure src="…" caption="…" img-class="w-full h-auto object-contain shadow" />` for images.
  - OneDrive media via the symlinks: `./assets/pictures/…`, **URL-encode spaces (`%20`) and commas
    (`%2C`)**; verify the file exists on disk (some are on-demand/empty locally).
  - Real **paper figures**: copy into the deck's `public/<paper>/` and reference as
    `/<paper>/<fig>.png` (leading-slash public path) so they version with the deck and bundle on
    build — prefer these over AI mock-ups when reporting a paper.
- Video: standard HTML5 `<video controls><source src="./assets/videos/…mp4" /></video>` inside a
  `<figure class="media-figure">` + `<FigureCaption>` (the theme's `SlidevVideo` is unreliable).
- `mermaid` `gantt` for timelines; `[DIAGRAM_PLACEHOLDER: …]` where a diagram is needed but absent.
- Layouts: `default`, `two-cols-header` (`::left::` / `::right::`), the theme grid families
  (`two-by-two-header`, `one-by-three`, …), `center`, `cover`, `agenda`.
- Useful assets in `OneDrive/Pictures`: `Logos and icons/`, `AI generated/` (overview + rendered
  Spot/Crazyflie scenes), `Presentations/` (fermentation tanks). Videos in `OneDrive/Videos/Camera/`.

## 5. Validate
```bash
npm run build      # agenda:generate + slidev build; catches component/import errors
npm run export     # -> slides.pdf (needs playwright-chromium); good to hand to the user
npm run dev        # http://localhost:3030 to present (video plays live)
```
Then read the exported PDF to eyeball rendering.

## Gotchas (learned 2026-06-15)
- **`public/combined-logos.png` is mandatory** — the theme's `global-top.vue` imports
  `/combined-logos.png` on every slide; without it the build fails `UNRESOLVED_IMPORT`. The
  scaffolder copies it from the theme; if missing, `cp ../../slidev-theme-lorite-phd/public/combined-logos.png public/`.
- **`vite.config.ts` with `server.fs.{strict:false, allow:[…OneDrive]}`** — the `assets/*` symlinks
  resolve outside the repo; newer Vite blocks bundling them. The scaffolder writes this.
- **Pin `@slidev/cli` to `52.14.1`** (matches the theme). `52.16+` ships rolldown-vite, which breaks
  against the theme's nested `@slidev/client` (`Could not load #slidev/styles`). The scaffolder pins
  it; if a deck drifted, set the exact version, delete `node_modules`+lockfile, reinstall.
- **A `<video>`/`<img>` `src` must point at a file that exists** — the build *bundles* the asset
  (even a leading-slash `/…` public path is resolved at build), so a missing placeholder fails the
  build. For a video the user will supply later, point the slide at an existing clip (e.g. the MOCAP
  clip under `assets/videos/Camera/`) as a working placeholder and leave a comment to swap the src.
- Don't double the logos: the theme renders them globally, so no per-slide logo `MediaFigure`.
