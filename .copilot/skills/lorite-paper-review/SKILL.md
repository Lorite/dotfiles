---
name: lorite-paper-review
description: The reviewer-side substance rubric for judging a scientific paper (positioning/novelty, baselines, experimental rigor, claims/terminology, reproducibility/compute, limitations honesty, structure/story, figures/tables, venue fit), distilled from the DTU 34792 Advanced Perception reading-club discussions. Produces a prioritized P0/P1/P2 finding table plus a score out of 5. Use when reviewing someone else's paper, preparing a reading-club presentation, or self-reviewing your own draft before submission. Complements lorite-paper-writer's Critique mode, which owns the PROSE rubric - this skill owns whether the science would survive a program committee.
argument-hint: "<paper to review> [mode=external|self] e.g. 'review main.tex before ICRA submission, mode=self' or 'review the Any6D paper for the reading club'"
---

# lorite-paper-review - the reviewer-side rubric

**Source of truth for a human reader:** the vault note [[How to review scientific research]] (`work/workflows/research/How to review scientific research.md`). Every rule below is grounded in a concrete paper discussed in the DTU PhD course 34792 (Advanced Topics in Perception for Robotics and Autonomous Systems, Feb to May 2026); the note carries the wikilink to each. **Read that note before a review pass** so the examples are in context, and log findings back per `lorite-ai-chat-diary`.

## What this skill is NOT

It is not a prose critique. `lorite-paper-writer`'s **Critique mode** owns sentence length, active voice, acronym expansion, AI-tells, overclaim-by-wording and the supervisor's feedback rubric. This skill asks the orthogonal question: **would the science survive a skeptical program committee?** When both run on the same draft, run this one first (a paper with no baseline cannot be saved by better sentences) and keep the two finding tables separate so it stays obvious which axis a fix belongs to.

## Modes

- **`external`** (default) - reviewing someone else's paper, or preparing a reading-club presentation. Output the finding table, the score, and the discussion questions.
- **`self`** - reviewing your own draft before submission. Same rubric, but every P0 and P1 becomes an action item, and the pass ends by asking which to fix. Never edit the paper in this skill (that is `lorite-paper-writer` Draft mode).

## Before you read the paper

1. **Pre-commit the bar, paper-blind.** In two lines, state which dimensions this pass weights most and what would count as a P0 for *this* paper. Committing before reading stops score inflation on a draft that reads smoothly. (Same guardrail as the writer agent's Critique pre-commit.)
2. **Establish the contract.** Conference paper, journal article, pre-print, or RA-L style rolling submission. A pre-print is not polished for anyone, and a journal article is allowed the space a conference paper is not. Judge against the contract the paper signed, and say which one you assumed.
3. **Research the authors.** Count, lab or company, known work, plausible resources. Two authors from a frontier lab producing a giant benchmark table probably had those benchmarks internally. A single author attacking a prior method is a different object than a 20-author release. Big-company work often stays a pre-print on purpose.
4. **Read the paper yourself first.** Never let an LLM pass substitute for the first read. `lorite-paper-reader` output or a NotebookLM overview can replace the *first pass* on some papers, never the read.

## The nine dimensions

Walk them in order, taking notes per dimension rather than per page.

1. **Positioning and novelty.** Problem to solution, never solution to problem. The niche may be tiny (darker environments, one condition, faster, more precise) but it must exist, because in robotics/perception a paper that is not better on some axis does not get published. A niche-staking comparison table is a strong move and a trap: the dataset must cover the cells it claims. Low novelty plus good storytelling is legitimately publishable, so the real question is the reader's: after this, do I use their system or just the component they swapped in? A new dataset needs a reason, because datasets saturate. Integration papers deserve credit and resist compression to one key idea.
2. **Baselines and comparisons.** Are the baselines current, or all several years old? Is the obvious baseline missing (typically the strong off-the-shelf component the method is built on, evaluated alone)? Do they compare against the competing methods they themselves cite? If the dataset is private and unpublished, comparison is impossible by construction. Copied rather than re-run numbers make sparse tables, and reported numbers routinely beat what you get reproducing them.
3. **Experimental rigor.** Test data genuinely unseen. No hand-picked dataset subsets in the results table, no cherry-picked demo videos. Ablations present, and swapping a component beats deleting it. In a multi-stage pipeline, which stage failed (compounding error is guaranteed, so end-to-end-only numbers hide the diagnosis). Is n stated and large enough? A surprising ablation result is a claim owed an explanation, not a bonus contribution. Experiments outside the paper's own claim add noise. Both lab and real-world experiments is the bar. Recurring data questions: class distributions, the null case (silence, empty scene, no detection), and whether the labelling is the limiting factor rather than the model.
4. **Claims and terminology.** Undefined superlatives ("optimal", "compromised accuracy") are the classic tell. "Real-time" and "robust" mean nothing without device, frequency and numbers. The title is a claim too ("A Comprehensive Study" on a focused empirical paper). Acronyms defined at first use, in order, ideally with a nomenclature table. Separate "the English is imprecise" from "the thought is imprecise" and say which, because precise terminology is what reviewers grade and it is genuinely harder for non-native speakers.
5. **Reproducibility and compute.** Code, dataset, or an honest "code will be available at URL". Check for a repo even when the text never mentions one. Empirically-tuned parameters need guidelines. Compute reported, with training cost distinguished from inference cost, and which GPU and how many (CVPR makes resource reporting mandatory). FLOPs alone is the wrong efficiency axis: throughput and images per watt say more about deployability. For frontier-lab papers the question shifts from "can I reproduce this" to "what is transferable".
6. **Honesty about limitations.** A missing limitations section is a finding every time. A long specific one reads as trustworthy, not weak. A missing hypothesis or requirements paragraph is the same defect earlier in the paper. An "ideas that failed" appendix is exemplary. Criticism of prior work must be proven and must be polite, and it belongs in the appendix when it runs to pages.
7. **Structure, story and length.** Is there a story (hypothesis, method that tests it, results that answer it)? Can the paper compress to one key idea? Balance of introduction against method, because the method is what the reader came for. Bold lead-ins help, more than about five subsections in one section stops helping. Heavy mathematics belongs in the appendix, and the control-paper convention is the gold standard (notation list, every term explained, subtitles marking derivation transitions). A strong related-work section is a contribution. Needing several re-reads to extract the method is a finding, and so is a paper that is hard to read for no structural reason. Watch for prose optimised for acceptance rather than understanding.
8. **Figures and tables.** Table captions above, figure captions below. Rank results with typography (bold best, underline second) rather than a coloured background. When colour does encode value, zero must be white with diverging colours either side, never a loud colour. A big comparison table is often the wrong instrument where a scatter plot of accuracy against a cost measure would land instantly. Captions must carry the takeaway. Devices worth crediting: the figure showing output with each intermediate stage removed, visualisations of the raw data itself, a front nomenclature table.
9. **Venue and reviewing context.** Does the paper fit its venue? RA-L is worth flagging as a target when relevant (ICRA/IROS-comparable, counts as a journal, rolling submission, back-and-forth review that improves the paper, present at whichever conference is closer). Reviewer luck is real, which is a reason to remove obvious rejection hooks rather than a reason to fatalism.

## Severity

Map every finding to the same P0/P1/P2 scale `lorite-paper-writer` Critique uses, so the two tables merge cleanly:

- **P0 - would sink the paper.** No code and no data with no statement about either. No limitations section. The obvious baseline missing. Hand-picked result subsets or cherry-picked videos. A core claim ("real-time", "robust", "optimal") with nothing behind it. Solution in search of a problem.
- **P1 - a reviewer will raise it and the text does not answer it.** All-old baselines. Unexplained surprising results. n too small or unstated. Experiments that do not test the paper's claim. Missing compute reporting. Missing hypothesis paragraph. Undefined acronyms that block comprehension.
- **P2 - real but survivable.** Figure and table craft, subsection count, caption thinness, naming quibbles, length-format mismatch, related-work thinness.

**Coverage first, filter later.** Report every finding including low-confidence ones; the priority column is the filter. Do not silently drop something you judged below a bar.

## Grounding rules

- **Quote or locate the paper's own text for every finding** (section, line, table, figure). A finding with no anchor is an impression.
- **Never invent a fact about the paper.** If you cannot tell whether a baseline is missing or merely unmentioned in the section you read, say so and mark it `[VERIFY]`.
- Existing-work claims ("the field uses 100 to 200 demonstrations") need a source or must be softened to a question for the authors.
- In `self` mode, a finding about the user's own paper must be checkable against the repo or the vault, not against recollection.

## Output

```
Pre-commit: <what this pass weights, what counts as P0 here>
Contract assumed: <conference | journal | pre-print | RA-L-style>, <venue if known>

| # | Dim | Sev | Finding | Where | Fix |
|---|-----|-----|---------|-------|-----|

Score: X.XX / 5 - <one sentence why>
Green flags: <what the paper does that is worth naming>
Top 3: <the three fixes that move the score most>
Discussion questions: <external mode only, 3 to 5 for the reading club>
```

Calibration points from the course scoring: a well written paper with modest novelty that sells its story well scored ~4.25, a solid paper with hand-picked result tables and no limitations section ~3.75, a rushed paper with a suspicious ablation ~3.

In `self` mode, end by asking which findings to apply; applying them is a hand-off to `lorite-paper-writer` (Draft mode) or `lorite-data-analyst` (numbers, figures, tables), never an edit made here.

## Green flags worth naming explicitly

A plug-and-play repository, better still with a notebook. A long specific limitations section. An "ideas that failed" appendix. Ablations that swap rather than only delete. Both lab and real-world experiments. A related-work section that teaches the field. A nomenclature table with acronyms in order. Old ideas combined with new ones, and real physics used rather than ignored.
