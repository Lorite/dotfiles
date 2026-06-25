#!/usr/bin/env bash
# Install/refresh the rclone-mount systemd *user* unit that exposes the whole
# Nextcloud home server on-demand at ~/nextcloud-all (fetch-on-open).
#
# Host-specific (laptop): NOT wired into the top-level install.sh, because the
# mount only makes sense on a machine that (a) has the rclone remote configured
# and (b) is a personal workstation — not the server or the Orin. Run it by hand
# on each such machine. See rclone-nextcloud-all.service for the full rationale.
#
# Idempotent: safe to re-run after editing the unit file.
set -euo pipefail

REMOTE="nextcloud_home_server_webdav"
UNIT="rclone-nextcloud-all.service"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/${UNIT}"
DEST_DIR="${HOME}/.config/systemd/user"
DEST="${DEST_DIR}/${UNIT}"

# --- preflight ---------------------------------------------------------------
command -v rclone >/dev/null     || { echo "ERROR: rclone not installed"; exit 1; }
command -v fusermount3 >/dev/null || { echo "ERROR: fusermount3 (FUSE) not installed"; exit 1; }

if ! rclone listremotes | grep -qx "${REMOTE}:"; then
  echo "ERROR: rclone remote '${REMOTE}:' not found. Configure it first: rclone config"
  exit 1
fi

# Guard against overlapping the desktop client's real-sync root (~/nextcloud).
case "${HOME}/nextcloud-all" in
  "${HOME}/nextcloud"|"${HOME}/nextcloud/"*)
    echo "ERROR: mountpoint would overlap the desktop-client folder ~/nextcloud"; exit 1;;
esac

# --- install -----------------------------------------------------------------
mkdir -p "${DEST_DIR}" "${HOME}/nextcloud-all" "${HOME}/.local/state/rclone"
ln -sf "${SRC}" "${DEST}"
echo "Linked ${DEST} -> ${SRC}"

systemctl --user daemon-reload
systemctl --user enable --now "${UNIT}"

sleep 2
systemctl --user --no-pager status "${UNIT}" || true
echo
echo "Done. Browse the full library at: ~/nextcloud-all"
echo "Control: systemctl --user {status,restart,stop} ${UNIT%.service}"
