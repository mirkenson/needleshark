#!/bin/bash
# Retire only the approved product routes, retaining queries and restoring from backup on failure.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
revision="$(git -C "$project_dir" rev-parse HEAD)"
git -C "$project_dir" diff --exit-code HEAD -- ops/b2b-retired-products.conf ops/install-b2b-redirects.sh >/dev/null
git -C "$project_dir" merge-base --is-ancestor "$revision" '@{upstream}'
ssh_key="${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}"
ssh_options=(-i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
stamp="$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}"
remote_dir="/opt/needle-shark/backups/nginx-$stamp"
ssh "${ssh_options[@]}" root@194.87.99.98 "install -d -m 0700 '$remote_dir'"
scp "${ssh_options[@]}" "$project_dir/ops/b2b-retired-products.conf" "root@194.87.99.98:$remote_dir/incoming.conf"
ssh "${ssh_options[@]}" root@194.87.99.98 bash -s -- "$remote_dir" <<'REMOTE'
set -euo pipefail
backup_dir="$1"
config=/etc/nginx/sites-available/needle-shark
snippet=/etc/nginx/snippets/needle-b2b-retired.conf
cp -p "$config" "$backup_dir/site.conf"
if test -f "$snippet"; then cp -p "$snippet" "$backup_dir/previous-snippet.conf"; fi
restore_config() {
  cp -p "$backup_dir/site.conf" "$config"
  if test -f "$backup_dir/previous-snippet.conf"; then cp -p "$backup_dir/previous-snippet.conf" "$snippet"; else rm -f "$snippet"; fi
  nginx -t && systemctl reload nginx
}
trap 'deploy_exit=$?; restore_config; exit "$deploy_exit"' ERR
# A successful static switch is a prerequisite.
test -f /var/www/needle-shark/current/napravleniya/chehly/index.html
install -m 0644 "$backup_dir/incoming.conf" "$snippet"
python3 - <<'PY'
from pathlib import Path
p=Path('/etc/nginx/sites-available/needle-shark')
s=p.read_text()
include='    include /etc/nginx/snippets/needle-b2b-retired.conf;'
if include not in s:
    anchor='    root /var/www/needle-shark/current;'
    assert s.count(anchor)==1, 'Unexpected Nginx configuration; no edits made'
    s=s.replace(anchor, anchor+'\n'+include)
    p.write_text(s)
PY
nginx -t
systemctl reload nginx
systemctl is-active --quiet nginx
trap - ERR
printf 'Retired-product redirects installed. Configuration backup: %s\n' "$backup_dir"
REMOTE
