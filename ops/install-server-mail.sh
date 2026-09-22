#!/bin/bash
# Backend-only deployment. --loop preserves all existing SMTP settings/recipients.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
mode=mail
if [[ "${1:-}" == --loop ]]; then
  mode=loop
  settings="${2:?Usage: install-server-mail.sh --loop PRIVATE_LOOP_FILE}"
  approved_recipient='-'  # Preserve this positional argument through the SSH command.
else
  settings="${1:?Usage: install-server-mail.sh PRIVATE_SMTP_FILE APPROVED_RECIPIENT}"
  approved_recipient="${2:?Approved recipient required}"
  [[ "$approved_recipient" =~ ^[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+$ ]] || exit 2
fi
remote_host="root@194.87.99.98"
ssh_key="${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}"
revision="$(git -C "$project_dir" rev-parse HEAD)"
# Require a committed backend. Documentation can be updated after live verification.
git -C "$project_dir" diff --exit-code HEAD -- server ops/install-server-mail.sh ops/configure-server-mail.py >/dev/null
git -C "$project_dir" merge-base --is-ancestor "$revision" '@{upstream}'
release="$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}"
release_dir="/opt/needle-shark/releases/$release"
ssh_options=(-i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
ssh "${ssh_options[@]}" "$remote_host" "install -d -m 0755 '$release_dir'; install -d -m 0700 '/opt/needle-shark/backups/$release'"
scp "${ssh_options[@]}" "$project_dir"/server/{leads,crm,lead_context,delivery_store,mail_delivery,loop_delivery}.py \
  "$project_dir/server/migrations/20260918_server_delivery.sql" "$project_dir/server/migrations/20260922_loop_delivery.sql" "$project_dir/ops/configure-server-mail.py" \
  "$remote_host:$release_dir/"
scp "${ssh_options[@]}" "$settings" "$remote_host:/opt/needle-shark/backups/$release/incoming.env"
ssh "${ssh_options[@]}" "$remote_host" bash -s -- "$release" "$revision" "$approved_recipient" "$mode" <<'REMOTE'
set -euo pipefail
release_dir="/opt/needle-shark/releases/$1"
backup_dir="/opt/needle-shark/backups/$1"
umask 077
chmod 0644 "$release_dir"/*.py "$release_dir"/*.sql
python3 -m py_compile "$release_dir"/*.py
systemctl is-active --quiet needle-leads
cp -p /etc/systemd/system/needle-leads.service "$backup_dir/needle-leads.service"
cp -p /etc/needle-shark/leads.env "$backup_dir/leads.env"
for name in leads.py crm.py lead_context.py; do
  if test -f "/opt/needle-shark/$name"; then cp -p "/opt/needle-shark/$name" "$backup_dir/$name"; fi
done
if test -L /opt/needle-shark/current; then readlink /opt/needle-shark/current > "$backup_dir/backend-current"; fi
if test -L /opt/needle-shark/previous; then readlink /opt/needle-shark/previous > "$backup_dir/backend-previous"; fi
readlink /var/www/needle-shark/current > "$backup_dir/static-current"
readlink /var/www/needle-shark/previous > "$backup_dir/static-previous"
# Stop before snapshot/switch: no Google deliveries or new old-format queue entries during migration.
systemctl stop needle-leads
restore_backend() {
  cp -p "$backup_dir/needle-leads.service" /etc/systemd/system/needle-leads.service
  cp -p "$backup_dir/leads.env" /etc/needle-shark/leads.env
  if test -f "$backup_dir/backend-current"; then
    ln -sfn "$(cat "$backup_dir/backend-current")" /opt/needle-shark/current.rollback
    mv -Tf /opt/needle-shark/current.rollback /opt/needle-shark/current
  fi
  if test -f "$backup_dir/backend-previous"; then
    ln -sfn "$(cat "$backup_dir/backend-previous")" /opt/needle-shark/previous
  fi
  systemctl daemon-reload
  systemctl restart needle-leads
}
trap 'restore_backend' ERR
python3 - <<'PY'
from pathlib import Path
import sqlite3
p = Path('/var/lib/needle-shark/leads.sqlite3')
if p.exists():
    with sqlite3.connect('file:' + str(p) + '?mode=ro', uri=True) as db:
        pending = db.execute('SELECT count(*) FROM leads WHERE delivered IS NULL').fetchone()[0]
        if pending:
            raise SystemExit('Pending legacy deliveries exist: migrate before switching')
PY
sudo -u postgres pg_dump -Fc needle_shark > "$backup_dir/needle_shark.dump"
pg_restore --list "$backup_dir/needle_shark.dump" >/dev/null
if test -f /var/lib/needle-shark/leads.sqlite3; then cp -p /var/lib/needle-shark/leads.sqlite3 "$backup_dir/leads.sqlite3"; fi
sudo -u postgres psql -d needle_shark -v ON_ERROR_STOP=1 -1 -f "$release_dir/20260918_server_delivery.sql"
sudo -u postgres psql -d needle_shark -v ON_ERROR_STOP=1 -1 -f "$release_dir/20260922_loop_delivery.sql"
sudo -u postgres psql -d needle_shark -v ON_ERROR_STOP=1 -c 'GRANT SELECT,INSERT,UPDATE ON lead_submissions,lead_files,lead_deliveries TO needle_app; GRANT USAGE,SELECT ON SEQUENCE lead_deliveries_id_seq TO needle_app;'
sudo -u postgres psql -d needle_shark -v ON_ERROR_STOP=1 -c 'GRANT SELECT,INSERT,UPDATE ON lead_loop_deliveries TO needle_app; GRANT USAGE,SELECT ON SEQUENCE lead_loop_deliveries_id_seq TO needle_app;'
if test "$4" = loop; then
  # This mode upgrades only the existing PostgreSQL/SMTP backend, never an old unit.
  test -s "$backup_dir/backend-current"
  grep -qx 'ExecStart=/usr/bin/python3 /opt/needle-shark/current/leads.py' "$backup_dir/needle-leads.service"
  python3 "$release_dir/configure-server-mail.py" --loop /etc/needle-shark/leads.env "$backup_dir/incoming.env"
else
  python3 "$release_dir/configure-server-mail.py" /etc/needle-shark/leads.env "$backup_dir/incoming.env" "$3"
fi
# Validate as the application user with the actual systemd environment; no secrets in process args/output.
systemd-run --quiet --wait --pipe --collect --unit="needle-mail-check-$1" \
  --property=User=needleleads --property=EnvironmentFile=/etc/needle-shark/leads.env \
  /usr/bin/python3 -c "import sys; sys.path.insert(0, '$release_dir'); import delivery_store,mail_delivery,loop_delivery; delivery_store.initialize(loop_enabled=bool(loop_delivery.webhook_url())); mail_delivery.recipients(); mail_delivery.smtp_config(); print('Application configuration and database privileges OK')"
ln -sfn "$release_dir" /opt/needle-shark/current.next
mv -Tf /opt/needle-shark/current.next /opt/needle-shark/current
if test -f "$backup_dir/backend-current"; then
  ln -sfn "$(cat "$backup_dir/backend-current")" /opt/needle-shark/previous
else
  legacy_dir="/opt/needle-shark/releases/$1-previous"
  install -d -m 0755 "$legacy_dir"
  for name in leads.py crm.py lead_context.py; do install -m 0644 "$backup_dir/$name" "$legacy_dir/$name"; done
  ln -sfn "$legacy_dir" /opt/needle-shark/previous
fi
if test "$4" = mail; then
  sed 's|^ExecStart=.*|ExecStart=/usr/bin/python3 /opt/needle-shark/current/leads.py|' "$backup_dir/needle-leads.service" > /etc/systemd/system/needle-leads.service
  systemctl daemon-reload
fi
systemctl restart needle-leads
sleep 2
systemctl is-active --quiet needle-leads
# Invalid payload exercises the actual new handler without saving or sending anything.
http_status="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8091/api/leads -H 'Origin: https://needle-shark.ru' -H 'Content-Type: application/json' -d '{}')"
test "$http_status" = 400
printf '%s\n' "$2" > "$release_dir/COMMIT"
trap - ERR
printf 'Backend installed: %s\nBackup: %s\n' "$release_dir" "$backup_dir"
REMOTE
