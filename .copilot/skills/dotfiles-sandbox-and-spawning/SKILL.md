---
name: dotfiles-sandbox-and-spawning
description: Why the Claude Desktop bubblewrap sandbox must stay disabled, why spawned subagents used to read a stale filesystem (Cowork microVM) and run zero tools (Copilot/Claude tool-name mismatch), and how both were fixed. Read when a spawned subagent behaves oddly — hallucinated tool output, stale vault reads, discarded writes, unreachable localhost — or when changing sandbox settings / the install.sh sync path.
argument-hint: "why did my spawned subagent report success but write nothing?"
---

# Sandbox, Cowork microVM, and subagent spawning

Forensics behind the four operative rules in the repo's `CLAUDE.md`. Everything here was verified on the laptop (`lori-ThinkPad-P15-Gen-2i`) in June 2026; the problems are **fixed** — this note explains *why* the fixes are shaped the way they are, so nobody re-breaks them.

## The Bash sandbox must be `enabled: false` in the Desktop app

`.claude/settings.json` carries the Bash-sandbox allowlist. The Claude **Desktop app runs the bubblewrap sandbox on by default**, which blocks subagents' Bash from (a) writing outside the cwd and (b) reaching non-allowlisted hosts — so pipeline agents couldn't write the vault / robotics repo / `~/.config/paper-scout`, reach Zotero's local API (`localhost:23119`), the research APIs, or run the `docker exec` dev-container wrappers. `sandbox.filesystem.allowWrite` + `sandbox.network.{allowLocalBinding,allowedDomains}` + `excludedCommands: ["docker *","devcontainer *"]` are the knobs — but only when the sandbox can actually run.

**In the Desktop app it cannot.** Agent mode already runs inside a restricted user namespace, so `bwrap` can't create the *nested* userns it needs (`nested userns is capability-restricted` / seccomp `setgroups` failure) and **every sandboxed command hard-fails at startup**. `enableWeakerNestedSandbox` does **not** fix this — that flag only addresses a later `/proc`-mount step, not userns creation; no `sandbox.*` key can grant back `CAP_SYS_ADMIN` inside an already-restricted namespace.

Disabling is safe because the Desktop app itself provides the outer isolation boundary (the inner `bwrap` was redundant double-containment). The `allowWrite` / `allowedDomains` / `allowLocalBinding` / `excludedCommands` block is harmless while disabled and becomes useful if you instead run the agents from the **bare `claude` CLI** (no outer namespace → `bwrap` nests fine → set `enabled: true` there).

Keep `.claude/settings.json` secret-free — it's plain-text symlinked.

## Root cause 1 — spawned subagents ran in a stale Cowork microVM

**`.claude/settings.json` `sandbox.*` does NOT control spawned subagents.** Verified 2026-06-12: a spawned subagent (Agent/Task tool) read a **stale rootfs-image snapshot** of the vault (a note showed 4444 B where the live file was 7003 B, with a different heading), had a **skewed clock** (VM image built 2026-03-26), and **could not reach host `localhost`** (Zotero `:23119`) — so its vault *writes were discarded* and its reads were stale, while the **main session runs on the host and sees everything live**. That asymmetry is why the subagent self-reported success and could not detect the problem.

Mechanism: Claude Desktop's **Cowork** feature — `/usr/lib/claude-desktop/.../app.asar.unpacked/cowork-vm-service.js` dispatches a pluggable backend: `host` (run directly on the host, no isolation), `bwrap` (namespace sandbox), or `kvm` (QEMU/KVM microVM; host dirs shared in via virtiofs but only the per-session workspace — everything else is the stale image). Auto-detect prefers `bwrap`, but `bwrap` is non-functional here (same nested-userns limit as above) so it fell back to the **kvm microVM** → the stale-FS symptom.

**Fix: force the host backend with `COWORK_VM_BACKEND=host`** (values `host|bwrap|kvm`), set in two host-side files (not in this repo):

- `~/.local/share/applications/claude-desktop.desktop` — `Exec=env COWORK_VM_BACKEND=host /usr/bin/claude-desktop %u`
- `~/.config/environment.d/claude-cowork.conf` — `COWORK_VM_BACKEND=host`

Takes effect on the **next Claude Desktop launch** (the launcher cleans up the old cowork daemon, so a normal relaunch re-inits the backend); revert by deleting the two files. With `host`, the stale-VM isolation is gone — **verified 2026-06-12 23:37**: a *clean* spawn read a just-written host file and landed durable writes on the live vault + reached live Zotero (`200`), all cross-checked from the host.

More-isolated alternative: keep the VM and virtiofs-mount specific `$HOME` dirs via `additionalBinds` in `~/.config/Claude/claude_desktop_linux_config.json` — but that cannot restore localhost-service reachability, so Zotero stays unreachable from subagents.

## Root cause 2 — the `tools:` allowlist matched nothing

After the VM fix, spawned *custom pipeline* agents still came back with `tool_uses: 0` (their tool calls rendered as inert text, often with hallucinated output), while `general-purpose` (`tools: *`) spawned cleanly.

Root cause: pipeline agents are authored in the **Copilot/VS-Code tool namespace** (lowercase `read`/`execute`/… + globs like `zotero/*`), but Claude Code's tools are **PascalCase** (`Bash`/`Read`/…) and MCP tools are `mcp__<server>__*`. `sync_copilot_to_claude` used to `cp` the frontmatter **verbatim**, so a spawned subagent's `tools:` allowlist matched **nothing** → empty registry → no tool could fire. The main session is immune (inline work uses the live tools, not the frontmatter filter) — exactly why "inline worked, spawning didn't".

**Fix: `normalize_frontmatter_for_claude()` in `install.sh`** translates the Copilot tool names to Claude's on the sync path. Agent defs are **cached at session start**, so it only takes effect in a **fresh session**.

**Verified 2026-06-13** in a clean session: `lorite-slidev-presentation-implementer` (built-ins) → `tool_uses: 1`, real host; `lorite-paper-reader` (built-ins + `mcp__zotero`) → `tool_uses: 2`, real host, and `zotero_list_libraries` returned the **live** library — so the known Claude bug #1885/#25200 (a `tools:` allowlist stripping inherited MCP tools) **does not bite here**: explicit scoping and MCP access coexist.

## Operating rule

**Spawning custom pipeline agents is reliable** (with `COWORK_VM_BACKEND=host` live + the translated `tools:`) — run them inline *or* spawned. Inline stays a safe default but is no longer required for vault/Zotero-touching agents.

## Frontmatter normalization reference

**Claude** (`normalize_frontmatter_for_claude`, applied by `sync_copilot_to_claude` to `*.agent.md`; skills still symlink): `read→Read`, `edit→Edit, Write`, `execute→Bash`, `search→Grep, Glob`, `web→WebFetch, WebSearch`, `todo→TodoWrite`, `agent→Agent`, `<server>/*→mcp__<server>` (non-`[A-Za-z0-9_-]`→`_`); `vscode`/unknown names are dropped; duplicates collapsed; and if nothing maps the `tools:` key is omitted entirely (→ inherit all tools, like `general-purpose`).

**OpenCode** (`normalize_frontmatter_for_opencode`): `argument-hint→argumentHint`, `user-invocable→userInvocable`, `tool-restrictions→toolRestrictions`, `tools:` arrays → `tools: {name: true}` map, and `model:` array placeholders are dropped.
