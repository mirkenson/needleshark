#!/bin/bash
# Install independent maintenance release; no site/backend restart or recipient changes.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
recipient="${1:?Usage: install-maintenance.sh APPROVED_MONITOR_RECIPIENT}"
[[ "$recipient" =~ ^[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+$ ]] || exit 2
revision="$(git -C "$project_dir" rev-parse HEAD)"
git -C "$project_dir" diff --exit-code HEAD -- ops >/dev/null
release="$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}"
host=root@194.87.99.98
options=(-i "${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
ssh "${options[@]}" "$host" "install -d -m 0755 /opt/needle-maintenance/releases/$release; install -d -m 0700 /opt/needle-maintenance/backups/$release"
scp "${options[@]}" "$project_dir/ops/maintenance.py" "$project_dir"/ops/needle-{cleanup,monitor}.{service,timer} "$host:/opt/needle-maintenance/releases/$release/"
ssh "${options[@]}" "$host" bash -s -- "$release" "$revision" "$recipient" <<'REMOTE'
set -euo pipefail
release_dir="/opt/needle-maintenance/releases/$1"
backup_dir="/opt/needle-maintenance/backups/$1"
umask 077
# Snapshot real systemd configuration before adding/replacing units.
systemctl cat needle-leads nginx postgresql > "$backup_dir/existing-units.txt"
for unit in needle-cleanup.service needle-cleanup.timer needle-monitor.service needle-monitor.timer; do
  if test -f "/etc/systemd/system/$unit"; then cp -p "/etc/systemd/system/$unit" "$backup_dir/$unit"; fi
done
if test -f /etc/needle-shark/monitor.env; then cp -p /etc/needle-shark/monitor.env "$backup_dir/monitor.env"; fi
if test -L /opt/needle-maintenance/current; then readlink /opt/needle-maintenance/current > "$backup_dir/current"; fi
readlink /opt/needle-shark/current > "$backup_dir/backend-current"
readlink /var/www/needle-shark/current > "$backup_dir/static-current"
chmod 0644 "$release_dir"/*
python3 -m py_compile "$release_dir/maintenance.py"
systemd-analyze verify "$release_dir"/*.service "$release_dir"/*.timer
restore_configuration() {
  systemctl disable --now needle-cleanup.timer needle-monitor.timer || true
  for unit in needle-cleanup.service needle-cleanup.timer needle-monitor.service needle-monitor.timer; do
    if test -f "$backup_dir/$unit"; then
      cp -p "$backup_dir/$unit" "/etc/systemd/system/$unit"
    else
      rm -f "/etc/systemd/system/$unit"
    fi
  done
  if test -f "$backup_dir/monitor.env"; then cp -p "$backup_dir/monitor.env" /etc/needle-shark/monitor.env; fi
  if test -f "$backup_dir/current"; then
    ln -sfn "$(cat "$backup_dir/current")" /opt/needle-maintenance/current.rollback
    mv -Tf /opt/needle-maintenance/current.rollback /opt/needle-maintenance/current
  fi
  systemctl daemon-reload
  if test -f "$backup_dir/needle-monitor.timer"; then systemctl enable --now needle-monitor.timer; fi
  if test -f "$backup_dir/needle-cleanup.timer"; then systemctl enable --now needle-cleanup.timer; fi
  echo 'Maintenance install failed; prior unit configuration restored. No database restore attempted.' >&2
}
trap restore_configuration ERR
printf 'MONITOR_RECIPIENT=%s\n' "$3" > /etc/needle-shark/monitor.env
chmod 0600 /etc/needle-shark/monitor.env
printf '%s\n' "$2" > "$release_dir/COMMIT"
ln -sfn "$release_dir" /opt/needle-maintenance/current.next
mv -Tf /opt/needle-maintenance/current.next /opt/needle-maintenance/current
if test -f "$backup_dir/current"; then ln -sfn "$(cat "$backup_dir/current")" /opt/needle-maintenance/previous; fi
for unit in needle-cleanup.service needle-cleanup.timer needle-monitor.service needle-monitor.timer; do
  install -m 0644 "$release_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl start needle-cleanup.service
systemctl enable --now needle-cleanup.timer needle-monitor.timer
systemctl start needle-monitor.service
systemctl is-active --quiet needle-cleanup.timer needle-monitor.timer needle-leads nginx postgresql@16-main
trap - ERR
printf 'Maintenance installed: %s\nConfiguration backup: %s\n' "$release_dir" "$backup_dir"
REMOTE
