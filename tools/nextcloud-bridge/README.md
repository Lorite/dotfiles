# Nextcloud → Obsidian file bridge

`setup-bridge.sh` symlinks selected **Nextcloud sync-client** folders into a dedicated subfolder of the Obsidian vault (default `vault/nextcloud/`) so notes can embed/link files with stable, cross-machine vault-relative wikilinks (`![[nextcloud/papers/foo.pdf]]`) while the actual bytes live in Nextcloud — editable by any app (e.g. Ubuntu's Documents), offline-available, and Nextcloud-synced to the home server.

Run automatically by `install.sh` on every machine; also runnable on its own:

```bash
tools/nextcloud-bridge/setup-bridge.sh
```

## What it does

For each `subfolder:linkname` pair it:

1. Creates `vault/<NEXTCLOUD_VAULT_SUBDIR>/<linkname>` → `NEXTCLOUD_BASE/<subfolder>` (idempotent; re-points a stale link; **refuses to replace a real, non-symlink vault path**).
2. Adds the whole `/<NEXTCLOUD_VAULT_SUBDIR>` folder to the vault's `.stignore` (Syncthing) and `.gitignore` (git) so the links are **never synced** — every machine creates its own, because the symlink target and the `/home/<user>` path differ per host (`lori` on the laptop, `lorite` on the server). (With `NEXTCLOUD_VAULT_SUBDIR=""`, each root-level link is ignored individually instead.)

## Config (per-machine)

Optional `~/.config/dotfiles/paths.env` (see `paths.env.example`) or environment:

| Var | Default | Notes |
|-----|---------|-------|
| `NEXTCLOUD_BASE` | `$HOME/nextcloud` | Sync-client root. **Not** a WebDAV mount. |
| `OBSIDIAN_VAULT` | `$HOME/git/lorite-obsidian-notes` | The Syncthing-synced vault. |
| `NEXTCLOUD_VAULT_SUBDIR` | `nextcloud` | Vault subfolder the links live under (`""` = vault root). |
| `NEXTCLOUD_BRIDGE` | `zotero:papers` | Space/newline `subfolder:linkname` pairs. |

## Design choices

- **Sync client, not WebDAV.** Point `NEXTCLOUD_BASE` at the Nextcloud desktop sync client (real local files). A WebDAV mount (e.g. `~/nextcloud-all`) is slow, breaks offline, and can serve stale cache — the same "reads wrong/partial" hazard that bites Obsidian's indexer and non-interactive agent reads. The script warns if the base looks like a WebDAV/FUSE mount.
- **Curated subfolders, not the whole tree.** Symlinking all of Nextcloud makes Obsidian enumerate/watch thousands of unrelated files, pollutes the explorer/search/graph, and risks symlink recursion (if the tree ever contains the vault). Expose only what you embed.
- **With VFS ("files on demand"): keep the bridged folders pinned "available locally"** so the indexer and agents never hit dehydrated placeholders.
