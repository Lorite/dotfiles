---
name: dotfiles-tooling
description: Full details of the PhD workflow's tools and integrations — Obsidian CLI + Web Clipper, Zotero and the zotero-mcp server, the automatic Zotero→vault literature-note timer, the automatic daily-note timer and SimpleTimeTracker refresh-stt enrichment, the Nextcloud→Obsidian file bridge, SimpleTimeTracker on Android, Slidev, gh, and the dev-container wrappers. Read before configuring, debugging, or changing any of these.
argument-hint: "how does the zotero-obsidian sync timer work?"
---

# Tooling / integrations

The repo's `CLAUDE.md` carries a one-line index of these. This is the full detail.

## Obsidian CLI

`~/.local/bin/obsidian` — requires the Obsidian desktop app running with the vault open. Prefer Bases (`base:query`) for structured reads. AI writes only inside `ai_brain/` unless explicitly told otherwise; if it must touch a note elsewhere, append under `# AI Generated` with `## Prompt` + `## AI Generated Answer`. Never echo secrets from `obsidian-web-clipper-settings.json`.

Efficient read patterns: `obsidian outline path="..."` for structure before a full `read`; `obsidian search:context query="..." path="..."` (matching lines + context in one call, better than `search` then `read`); `obsidian property:read name=<field> path="..."` for a single frontmatter field.

## Obsidian Web Clipper

Used to turn GitHub issues into `tasks/` notes.

## Zotero

`/usr/bin/zotero` — reference manager feeding the paper's `references.bib`. Also exposed to `lorite-paper-reader` via the **`zotero-mcp` MCP server** (`54yyyu/zotero-mcp`, PyPI `zotero-mcp-server`; pilot since 2026-06).

Launcher `tools/paper-reader/zotero-mcp.sh` **auto-detects** its mode: **hybrid** when the local API `:23119` is up (read local, write via the Web key) and **web-only** when there's no local app (e.g. the headless home server — reads and writes both go through the Web API). Key sourced from `~/.config/paper-scout/zotero-api-key`, never inlined in MCP config; preset `ZOTERO_LOCAL` to force a mode. Installed + registered with Claude Code by `install.sh` (user scope). Adds semantic search (`zotero-mcp update-db` builds the ChromaDB index).

**`lorite-paper-scout` still uses the curl/connector flow**, and **paywalled IEEE PDFs still go through `tools/paper-scout/fetch_attach.py`** (the MCP server can't drive the authenticated ITU/KB proxy). The `add_to_collection.py` helper remains a reader fallback; `zotero_note.py` is retired from the normal flow (kept only for explicitly-requested Zotero notes).

**Since 2026-06 the PDFs are Zotero *linked files* in `~/nextcloud/zotero/`** (synced by the Nextcloud client, annotated on the BOOX e-reader), and **since 2026-07-06 all AI reading content is written directly to the Obsidian literature note** (`media/research/<title> - <citekey>.md`, schema of `templates/media/research.md`) — no Zotero child notes, no Zotero-Integration import picker. Embedded PDF highlights are extracted headlessly by `tools/paper-reader/extract_pdf_annotations.py` (PyMuPDF, shared agents venv); the vault's `obsidian-extract-pdf-annotations` plugin does the same interactively in-app.

**Every Zotero item has a vault literature note, automatically:** the **`zotero-obsidian-sync.timer`** systemd user timer (units canonical in `tools/paper-reader/`, installed+enabled by `install.sh`) runs `sync_zotero_obsidian_notes.py --quiet` every 15 min — idempotent, no-op when Zotero is closed (the browser connector needs Zotero open to add items, so nothing is missed). The user saves papers via the browser connector or "Add by identifier"; the note appears within ~15 min with no human or AI involvement. Agents may therefore *assume* the literature note exists, and run the same script (`--key <K>`) for a just-added item.

## gh CLI

GitHub issues/PRs on the robotics repo.

## Obsidian daily notes, automatically

The **`obsidian-daily-note.timer`** systemd user timer (units canonical in `tools/lorite/`, installed+enabled by `install.sh`) runs `tools/lorite/obsidian_daily_note.py auto` hourly — creates + fully processes (Templater template, Run-plugin blocks, script-strip, Virtual Linker links, lint) every missing/unprocessed `diary/daily/` note from yesterday back 7 days, never today; quiet no-op when Obsidian is closed. The pipeline drives the Obsidian app via the `obsidian` CLI + the vault QuickAdd macro `scripts/process_daily_note.js`.

The **service ExecStart is routed through `with-headless-obsidian.sh`**, so it works on the laptop (passthrough to the live app) *and* headless on the home server (launches Obsidian under Xvfb for the run).

LLM time-slot summaries are NOT written by the timer — that's the **`lorite-daily-note`** skill (the agent writes them from the note's own generated data).

## SimpleTimeTracker late-entry enrichment (`refresh-stt`)

`obsidian_daily_note.py refresh-stt` (also run hourly by `auto`) tops up already-processed daily notes with STT entries the user back-filled in the app after processing. Insertion is file-only (runs even with Obsidian closed).

**When Obsidian is reachable it also enriches:** for `Media`-category rows of a catalogable type (Series/Movie/Videogame/Book/Manga/… → `STT_ACTIVITY_MEDIA_TYPE`) it creates the rich **Media DB** note headless — query the type's providers (OMDb/MyAnimeList/OpenLibrary/IGDB/…), take an **exact-title match only**, `createMediaDbNotes`, and inject the bare title as an alias so its year-suffixed filename resolves — then re-runs the daily-note macro so **Virtual Linker brackets** the new entities. No confident match / not in any DB (YouTube, social media) → a deduped **review-queue note** `ai_chats/notes/STT media to triage.md` (never guesses).

This is why 2026-07-17's STT log was originally unlinked: late-synced entries were inserted after processing, so nothing bracketed them — headless Obsidian fixes it at the root.

## Nextcloud → Obsidian file bridge

`tools/nextcloud-bridge/setup-bridge.sh` (run by `install.sh` on every machine, also runnable standalone) symlinks curated **Nextcloud sync-client** folders into a dedicated vault subfolder (default `vault/nextcloud/`) so notes embed/link files with stable, cross-machine vault-relative wikilinks (`![[nextcloud/papers/foo.pdf]]`) while the bytes live in Nextcloud (editable by any app, offline-available).

Default map `zotero:papers` → `vault/nextcloud/papers` ➞ `~/nextcloud/zotero`; the whole `nextcloud/` subfolder is added to the vault's `.stignore` **and** `.gitignore` so it is **never synced** — every machine creates its own (targets + the `/home/<user>` path differ per host: `lori` laptop vs `lorite` server). Idempotent; **refuses to replace a real (non-symlink) vault path**.

Config (per-machine, optional): `~/.config/dotfiles/paths.env` — `NEXTCLOUD_BASE` (default `~/nextcloud`), `OBSIDIAN_VAULT`, `NEXTCLOUD_VAULT_SUBDIR` (default `nextcloud`, `""` = vault root), `NEXTCLOUD_BRIDGE` (space/newline `subfolder:linkname` pairs); see `tools/nextcloud-bridge/{README.md,paths.env.example}`.

**Point `NEXTCLOUD_BASE` at the Nextcloud desktop sync client, NOT a WebDAV/rclone mount** (`~/nextcloud-all` is `fuse.rclone`): network mounts are slow, break offline, and serve stale cache — the same "reads wrong/partial" hazard that bites Obsidian's indexer and non-interactive agent reads; the script warns if the base is on a `*dav*`/`fuse` mount. Bridge **only curated subfolders, never the whole tree** (a whole-tree link makes Obsidian enumerate/watch thousands of files, pollutes explorer/search/graph, and risks symlink recursion). With Nextcloud VFS ("files on demand"), keep bridged folders pinned "available locally" so the indexer/agents never hit dehydrated placeholders.

## Slidev

`slidev-theme-lorite-phd` theme for presentations.

## Declared intent → ActivityWatch (`lorite_intent.py`, the destination)

Live work-session timing, straight into the local aw-server (`AW_SERVER`, default `http://localhost:5600`, bucket `aw-intent_<host>`) and onward to the home server over aw-sync. `tools/lorite/lorite_intent.py start|stop|status|add|list|edit|rm`, with `--source` (env `LORITE_INTENT_SOURCE`) recording who declared it. Unlike the SimpleTimeTracker hop below it is **editable after the fact** (`list` for ids, then `edit`/`rm`), which is what lets an agent correct its own mistake instead of asking the user to.

**Several declarations can run at once**, because work does: `start` may be issued again without stopping the first, and each stream is closed by name (`stop --task "<name>"`, or `stop --all`). A bare `stop` is refused while more than one is running, a repeat `start` for the same task is refused (that is a forgotten stop), and `stop` refuses to close a declaration a *different* `--source` started unless `--force`. Overlap does not inflate the day: `intent_resolve.py` (in `~/git/lorite-activitywatch`) splits each observed minute evenly across the declarations covering it, and `list` prints the day's real time next to the plain sum. `status` marks any declaration older than 4 h `<-- STALE` (`LORITE_INTENT_STALE_HOURS`), which the morning briefing reports — a running declaration is written **nowhere** until it stops. The phone board keeps its own running blocks in localStorage, independent of the CLI state file (`$XDG_STATE_HOME/lorite/intent.json`), and writes straight to the server.

**Every block is mirrored to the home server** when `~/.config/lorite/aw-remote.env` exists (`AW_REMOTE=ssh://lorite@100.72.103.27`, port 5600, no password needed — the server's aw-server is localhost-only and the Tailscale SSH key already exists). This is a correctness fix, not a convenience: declarations are stamped with their start but written at `stop`, so they reach the bucket **out of order**, and `aw-sync` resumes a bucket from where the destination's newest event ends — a late block that starts before that point never arrives. One 24-minute block was lost exactly that way on 2026-08-12, and the daily note built on the server under-reported the day by 25 min. `edit` and `rm` delete the mirror's copy too (matched by content, since ids are per-server). A failed mirror prints to stderr and never blocks the local write. The exporters dedupe what they read (`exporters/aw_intent_common.py`), so the direct and synced copies of a block collapse into one.

**`lorite_intent.py reconcile --date <d> [--prune]`** repairs a day that already drifted: it diffs this machine's blocks against the mirror's, inserts what is missing there, and with `--prune` deletes what the mirror has and this machine does not (only from this machine's own buckets, never the phone's). Both sides are compared as **whole events** — aw-server clips an event to the queried range, so comparing day views would "repair" one midnight-spanning block into two fragments, which is exactly what the first run did before it was fixed. Used on 2026-08-12 to restore a lost 24-min block and clear 5 pre-edit leftovers.

## SimpleTimeTracker (Android, via LlamaLab Automate Cloud Messaging)

Live work-session timing, run in parallel with the above during the transition and **single-track**: one live activity, no overlap, no API of its own. `tools/lorite/simple_time_tracker.py start|stop|add_record` POSTs to `https://llamalab.com/automate/cloud/message` an envelope `{secret,to,device,priority,payload}` where `payload.action` ∈ `start`/`stop`/`add_record` (`start`/`stop` = live timer, the prospective complement to the vault's retrospective `daily_time_tracker.py` blocks). Config from env `AUTOMATE_ANDROID_APP_{SECRET,TO,DEVICE}` (or `<vault>/.secrets/automate.env`) — never echo the secret.

## Dev-container execution model

The robotics (`lorite_ros2_humble_phd`) and CLAWAR paper repos each run inside a **Docker Dev Container**, but the Obsidian vault + dotfiles live on the host. So **run Claude/the editor on the host** (not "Reopen in Container") — the repo source is bind-mounted, so host edits are already live inside; only *running* the toolchain needs the container.

Two thin host wrappers shell in (via `docker exec` / `devcontainer exec`, bringing the container up if down): `tools/lorite/in-ros2.sh <cmd>` (ROS 2 — colcon/ros2/gz; container `ros2_humble_dev`) and `tools/lorite/in-tex.sh <cmd>` (texlive — latexmk/chktex). No args → an interactive shell. The `lorite-ros2-operator`, `lorite-experiment-coder`, and `lorite-data-analyst` agents call `in-ros2.sh`; `lorite-paper-writer` calls `in-tex.sh`.
