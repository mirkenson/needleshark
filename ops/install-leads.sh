#!/bin/bash
# Install a checked backend version; never publishes the static website.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
remote_host="root@194.87.99.98"
ssh_key="${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}"
release="$(date -u +%Y%m%dT%H%M%SZ)-$$"
release_dir="/opt/needle-shark/releases/$release"
ssh_options=(-i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
ssh "${ssh_options[@]}" "$remote_host" "install -d -m 0755 '$release_dir'"
scp "${ssh_options[@]}" "$project_dir/server/leads.py" "$project_dir/server/crm.py" \
  "$project_dir/server/lead_context.py" "$project_dir/server/migrations/20260910_catalog_context.sql" \
  "$remote_host:$release_dir/"
ssh "${ssh_options[@]}" "$remote_host" bash -s -- "$release" <<'REMOTE'
set -euo pipefail
release_dir="/opt/needle-shark/releases/$1"
backup_dir="/opt/needle-shark/backups/$1"
systemctl is-active --quiet needle-leads
systemctl show needle-leads --property=ExecStart --value
python3 -m py_compile "$release_dir/leads.py" "$release_dir/crm.py" "$release_dir/lead_context.py"
install -d -m 0700 "$backup_dir"
for name in leads.py crm.py lead_context.py; do
  if test -f "/opt/needle-shark/$name"; then cp -p "/opt/needle-shark/$name" "$backup_dir/$name"; fi
done
# Kept on the VPS, outside the web root and Git; contains private application data.
umask 077
sudo -u postgres pg_dump -Fc needle_shark > "$backup_dir/needle_shark.dump"
pg_restore --list "$backup_dir/needle_shark.dump" >/dev/null
sudo -u postgres psql -d needle_shark -v ON_ERROR_STOP=1 -f "$release_dir/20260910_catalog_context.sql"
restore_backend() {
  for name in leads.py crm.py lead_context.py; do
    if test -f "$backup_dir/$name"; then install -m 0644 "$backup_dir/$name" "/opt/needle-shark/$name"; fi
  done
  systemctl restart needle-leads
}
trap 'restore_backend' ERR
for name in lead_context.py crm.py leads.py; do
  install -m 0644 "$release_dir/$name" "/opt/needle-shark/$name.next"
  mv -f "/opt/needle-shark/$name.next" "/opt/needle-shark/$name"
done
systemctl restart needle-leads
systemctl is-active --quiet needle-leads
trap - ERR
printf 'Backend installed: %s\nBackup: %s\n' "$release_dir" "$backup_dir"
REMOTE
