---
name: lorite-slidev-meeting-deck
description: Stage 2 of the meeting workflow — build a visual-first Slidev status/meeting deck (PhD 3-1, status updates) FROM the prepared Obsidian meeting note, by copying the meetings/_skeleton template and filling it from the note's agenda. Uses the lorite-phd theme. NOT for paper decks (those use lorite-slidev-presentation-*). Use when asked to make slides for a recurring PhD meeting or status update.
argument-hint: "date=<YYYY-MM-DD> [meeting=<short name>] [note=<meeting note path>]"
---

# lorite-slidev-meeting-deck — visual-first status/meeting decks

A **meeting** deck (PhD 3-1, status update) is different from a **paper** deck. Paper decks use
the `lorite-slidev-presentation-*` agents (14-section paper structure). A meeting deck's structure
**mirrors the prepared Obsidian meeting note's agenda** — one deck section per `# Pre-meeting Tasks
and Notes` item — kept *simple and visual* (the note already holds the detail; the deck must
not repeat it). The supervisors' status shape (thesis objective · timeline · Past/Present/Future ·
actions) is just *one possible* agenda; **follow whatever the note defines, not a fixed template.**

Repo: `~/git/lorite_presentations_phd_slidev`. Theme: `slidev-theme-lorite-phd`. Node ≥ 20.

**Two-step pipeline (note → slides).** This skill is **step 2**. Step 1 is authoring the Obsidian
meeting note's `# Pre-meeting Tasks and Notes` agenda (via `lorite-meeting-prep`, then the user edits
it by hand) — the note is the **source of truth**. This skill only *reads* that note and renders the
deck; it never invents the structure. (Porting the other way, slides → note, is a manual one-off, not
the normal flow.)

## 1. Gather content first (don't invent)
The deck is the visual layer over work already prepared:

- The **meeting note** in the vault (`calendar_events/<date> …`) — its `# Pre-meeting Tasks and
  Notes` agenda (Purpose + table + numbered items) is the deck's backbone and section list (pairs
  with `lorite-meeting-prep`).
- The **previous meeting's deck/PDF** under `meetings/` — copy its visual style and which assets
  exist. (The old rolling Word doc + `lorite-recurring-meeting-docx` are **deprecated** — the note is
  the only ground truth now; share the deck as an exported PDF.)
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
cp ../_skeleton/slides.md slides.md   # start from the meeting-deck skeleton, then adapt it from the note
npm run media:link        # symlinks assets/pictures -> OneDrive/Pictures, assets/videos -> OneDrive/Videos
npm install               # pinned @slidev/cli 52.14.1
```

`meetings/_skeleton/` is the copyable template (see its README) — `deck:new` handles the scaffolding
+ config, then you overwrite `slides.md` with the skeleton and adapt it.

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

**Start from the skeleton** (`meetings/_skeleton/slides.md`, copied in step 2): it already encodes
cover → purpose → one agenda-separated section per item → actions table, with the gantt convention
and 👥💬 discussion markers — fill the `<...>` placeholders from the note. Reference deck:
`meetings/meeting_alejandro_phd_3-1_2026-06-16` — 6 sections: Recent milestones (a "last 2 months"
gantt + paper/MSc deep-dive) · Roadmap (a Q3 gantt + a "key points" slide) · Thesis direction ·
Paper 2 · Novo Nordisk asks · Next steps (actions/owners table). Mark discussion slides with 👥💬.

## 4. Visual-first rules
- ~1 slide per 2 min; **no text-only stretch > 2 slides**; the note holds the detail.
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
- `mermaid` `gantt` for timelines — follow the **`lorite-mermaid-gantt`** skill (canonical `init`
  block + tag→colour convention). `[DIAGRAM_PLACEHOLDER: …]` where a diagram is needed but absent.
- Layouts: `default`, `two-cols-header` (`::left::` / `::right::`), the theme grid families
  (`two-by-two-header`, `one-by-three`, …), `center`, `cover`, `agenda`.
- Useful assets in `OneDrive/Pictures`: `Logos and icons/`, `AI generated/` (overview + rendered
  Spot/Crazyflie scenes), `Presentations/` (fermentation tanks). Videos in `OneDrive/Videos/Camera/`.

## 5. Validate — then hand off (do NOT read the PDF back)
```bash
npm run build      # agenda:generate + slidev build; catches component/import errors (NOT mermaid)
npm run export     # -> slides.pdf (needs playwright-chromium); good to hand to the user
npm run dev        # http://localhost:3030 to present (video plays live)
```
`npm run build` does **not** catch mermaid parse errors. **Do not export + read the PDF yourself to
verify** — reading rendered PDF pages is very token-expensive. Make your best-reasoned change, then
**ask the user** to check the render (`npm run dev`, or open `slides.pdf`).

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
- **Gantt charts:** follow the **`lorite-mermaid-gantt`** skill — its canonical `init` block (colours +
  wider rows / bigger font) and the tag→colour convention (untagged = amber/planned, `:active` = blue,
  `:done` = green, `:crit` = red; milestones same). A gantt that renders **blank** is a parse error
  `npm run build` won't catch — compare to the template and **ask the user** to confirm the render.
- Don't double the logos: the theme renders them globally, so no per-slide logo `MediaFigure`.
