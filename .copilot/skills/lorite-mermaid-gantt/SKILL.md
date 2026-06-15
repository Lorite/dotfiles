---
name: lorite-mermaid-gantt
description: Author or restyle a Mermaid gantt chart (timeline / roadmap / schedule) with the lorite colour convention — the canonical init block + tag→colour→meaning rules (untagged = amber/planned, :active = blue/in-progress, :done = green/completed, :crit = red/missed; milestones use the same fills). Use whenever building or editing a gantt in a Slidev deck, an Obsidian note, or an agent figure. Shared by lorite-slidev-meeting-deck, lorite-obsidian-markdown, and the slidev/data agents.
---

# lorite-mermaid-gantt — gantt colour convention

The single source of truth for how lorite gantt charts look. Put the canonical `init` block on every
gantt; then **the task's tag chooses its colour and meaning** — no per-task styling needed. The block
also widens rows and enlarges the font (good for slides).

## Canonical init block

```mermaid
%%{init: {'theme':'base','themeVariables':{'sectionBkgColor':'#e3f2fd','altSectionBkgColor':'#f0f8ff','sectionBkgColor2':'#e8f5e9','primaryColor':'#f5f5f5','primaryBorderColor':'#bbbbbb','gridColor':'#dddddd','taskBkgColor':'#ffd54f','taskBorderColor':'#f9a825','taskTextColor':'#000000','taskTextDarkColor':'#000000','doneTaskBkgColor':'#a5d6a7','doneTaskBorderColor':'#2e7d32','activeTaskBkgColor':'#bbdefb','activeTaskBorderColor':'#1976d2','critBkgColor':'#e53935','critBorderColor':'#b71c1c','fontSize':'18px'},'gantt':{'barHeight':30,'barGap':6,'topPadding':40,'leftPadding':280,'fontSize':18,'sectionFontSize':20,'gridLineStartPadding':30}}}%%
gantt
    dateFormat YYYY-MM-DD
    axisFormat %d %b
    todayMarker on
    section Example
    Planned period       :2026-06-01, 2026-06-06
    In progress          :active, 2026-06-07, 2026-06-12
    Completed            :done, 2026-06-13, 2026-06-18
    Upcoming deadline    :milestone, 2026-06-20, 0d
    Achieved milestone   :milestone, done, 2026-06-17, 0d
    Missed deadline      :milestone, crit, 2026-06-23, 0d
```

Tune `gantt.leftPadding` for long task labels, and `barHeight` / `fontSize` / `sectionFontSize` for
the surface (bigger for slides, smaller for dense notes). Use `todayMarker on` to show "now".

## Period bars (rectangles)

| Tag | Colour | Meaning |
|---|---|---|
| _(no tag)_ | 🟡 amber | planned / upcoming |
| `:active` | 🔵 blue | in progress |
| `:done` | 🟢 green | completed |
| `:crit` | 🔴 red | missed / overdue |

## Milestones (diamonds, italic label — same fill rules)

| Tag | Colour | Meaning |
|---|---|---|
| `:milestone` | 🟡 amber | upcoming deadline |
| `:milestone, active` | 🔵 blue | happening today |
| `:milestone, done` | 🟢 green | achieved |
| `:milestone, crit` | 🔴 red | missed |

## `crit` on `:active` / `:done` (special case)

`crit` combined with `active`/`done` does **not** repaint the fill — it keeps the fill and only turns
the **border** red (`critBorderColor`):

| Tag | Fill | Border | Reads as |
|---|---|---|---|
| `:active, crit` | blue | red | in progress, but at-risk |
| `:done, crit` | green | red | completed, but was critical |

## Gotchas

- Untagged period tasks are **valid** — they are the amber "planned" state; don't force a tag on them.
- A gantt that renders **blank** is a Mermaid parse error — `slidev build` does **not** catch it and
  it's only visible once rendered. Compare against the block above, and **ask the user to confirm the
  render** rather than exporting + reading a PDF yourself (token-expensive; see
  `lorite-slidev-meeting-deck` §5).
