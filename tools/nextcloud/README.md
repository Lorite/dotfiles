# Nextcloud home-server access (this laptop)

Two complementary layers for `https://nextcloud.lorite.eu` (~800k files / ~700 GB).
They target **different, non-nested paths** on purpose.

| Path | Mechanism | Behaviour | Scope |
|------|-----------|-----------|-------|
| `~/nextcloud/` | **Nextcloud desktop client** (full sync, `virtualFilesMode=off`) | full local copy, offline, real-time two-way | only chosen working folders (e.g. `zotero/`, `nextcloud_temp_sync/`) |
| `~/nextcloud-all/` | **rclone mount** (this dir's systemd unit) | on-demand fetch-on-open, needs network, VFS cache | the **whole** library |
| `~/OneDrive/` | `onedrive --monitor` (separate) | independent daemon | unrelated, kept non-nested |

Why not full-sync everything: at this file count the desktop client's per-file
stat/journal + `inotify` watches blow up. So sync only the working set; browse
the rest on demand. Background → Obsidian concept note **WebDAV** and the task
*"Sync the Nextcloud home-server files to the laptop"*.

## Install / refresh the rclone mount

```bash
tools/nextcloud/setup.sh
```

Requires an rclone WebDAV remote named `nextcloud_home_server_webdav`
(`rclone config`; `type=webdav`, `vendor=nextcloud`,
`url=https://nextcloud.lorite.eu/remote.php/dav/files/<USER>`).

Control / inspect:

```bash
systemctl --user status  rclone-nextcloud-all
systemctl --user restart rclone-nextcloud-all
journalctl --user -u rclone-nextcloud-all
tail -f ~/.local/state/rclone/nextcloud-all.log
```

## Notes

- **`find` / recursive scans** over `~/nextcloud-all` are slow (one PROPFIND per
  directory) — fine for `ls`/opening files, painful for deep walks/indexers.
- New files created on the **server by other clients** can take up to
  `--dir-cache-time` (5 min) to appear; force-refresh with
  `rclone rc vfs/refresh recursive=true` or restart the unit. Your own writes via
  the mount appear immediately.
- The mount is a **user** unit and starts on graphical login (no `enable-linger`
  needed on a laptop).
