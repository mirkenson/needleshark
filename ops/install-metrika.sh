#!/bin/bash
# Independent reporter release. No lead backend, database or static site changes.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
settings="${1:?Usage: install-metrika.sh PRIVATE_METRIKA_ENV}"
revision="$(git -C "$project_dir" rev-parse HEAD)"
git -C "$project_dir" diff --exit-code HEAD -- server ops >/dev/null
git -C "$project_dir" merge-base --is-ancestor "$revision" '@{upstream}'
host=root@194.87.99.98
options=(-i "${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
release="$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp "$project_dir"/server/{metrika_reports.py,metrika_pages.json,loop_delivery.py,lead_context.py} "$stage/"
cp "$project_dir"/ops/{needle-metrika.service,needle-metrika.timer,configure-server-mail.py} "$stage/"
python3 - "$stage" <<'PY'
import hashlib, json, sys
from pathlib import Path
p=Path(sys.argv[1])
(p/'manifest.json').write_text(json.dumps({x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in p.iterdir()}))
PY
ssh "${options[@]}" "$host" "install -d -m 0755 '/opt/needle-metrika/releases/$release'; install -d -m 0700 '/opt/needle-metrika/backups/$release'"
scp "${options[@]}" "$stage"/* "$host:/opt/needle-metrika/releases/$release/"
scp "${options[@]}" "$settings" "$host:/opt/needle-metrika/backups/$release/incoming.env"
ssh "${options[@]}" "$host" bash -s -- "$release" "$revision" <<'REMOTE'
set -euo pipefail
umask 077
release_dir="/opt/needle-metrika/releases/$1"
backup_dir="/opt/needle-metrika/backups/$1"
chmod 0600 "$backup_dir/incoming.env"
chmod 0644 "$release_dir"/*
# Inspect/snapshot actual configuration and pointers before any service/configuration change.
systemctl cat needle-leads needle-monitor.service needle-monitor.timer > "$backup_dir/existing-units.txt"
for unit in needle-metrika.service needle-metrika.timer; do
  if test -f "/etc/systemd/system/$unit"; then cp -p "/etc/systemd/system/$unit" "$backup_dir/$unit"; fi
done
if test -f /etc/needle-shark/metrika.env; then cp -p /etc/needle-shark/metrika.env "$backup_dir/metrika.env"; fi
for name in current previous; do
  if test -L "/opt/needle-metrika/$name"; then readlink "/opt/needle-metrika/$name" > "$backup_dir/$name"; fi
done
readlink /opt/needle-shark/current > "$backup_dir/backend-current"
readlink /var/www/needle-shark/current > "$backup_dir/static-current"
systemctl is-enabled needle-metrika.timer > "$backup_dir/timer-enabled" 2>/dev/null || true
systemctl is-active needle-metrika.timer > "$backup_dir/timer-active" 2>/dev/null || true
python3 - "$release_dir" "$backup_dir/incoming.env" <<'PY'
import hashlib,json,os,re,runpy,sys
from pathlib import Path
release=Path(sys.argv[1])
for name, expected in json.loads((release/'manifest.json').read_text()).items():
    if hashlib.sha256((release/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Release hash mismatch')
sys.path.insert(0,str(release))
helper=runpy.run_path(str(release/'configure-server-mail.py'))
settings=helper['read_env'](sys.argv[2])
if set(settings)!={'METRIKA_TOKEN'} or not re.fullmatch(r'[A-Za-z0-9_-]{30,1024}',settings['METRIKA_TOKEN']):
    raise SystemExit('Expected a private read-only Metrika token file')
from loop_delivery import webhook_url
url=helper['read_env']('/etc/needle-shark/leads.env').get('LOOP_LEADS_WEBHOOK_URL')
if not webhook_url(url): raise SystemExit('Existing LOOP channel not configured')
os.environ.update(settings)
# Live read-only API validation before installing credentials or switching release.
from metrika_reports import main
sys.argv=['metrika_reports.py','check']
main()
helper['write_env'](str(release/'../..'/'metrika.env.next'),dict(settings,LOOP_LEADS_WEBHOOK_URL=url))
PY
python3 -m py_compile "$release_dir"/*.py
systemd-analyze verify "$release_dir/needle-metrika.service" "$release_dir/needle-metrika.timer"
restore() {
  result=$?
  trap - EXIT
  if [[ "$result" -eq 0 ]]; then return; fi
  set +e
  systemctl disable --now needle-metrika.timer
  systemctl stop needle-metrika.service
  for unit in needle-metrika.service needle-metrika.timer; do
    if test -f "$backup_dir/$unit"; then
      cp -p "$backup_dir/$unit" "/etc/systemd/system/$unit"
    else
      rm -f "/etc/systemd/system/$unit"
    fi
  done
  if test -f "$backup_dir/metrika.env"; then
    cp -p "$backup_dir/metrika.env" /etc/needle-shark/metrika.env
  else
    rm -f /etc/needle-shark/metrika.env
  fi
  for name in current previous; do
    if test -f "$backup_dir/$name"; then
      ln -sfn "$(cat "$backup_dir/$name")" "/opt/needle-metrika/$name.rollback"
      mv -Tf "/opt/needle-metrika/$name.rollback" "/opt/needle-metrika/$name"
    else
      rm -f "/opt/needle-metrika/$name"
    fi
  done
  systemctl daemon-reload
  if [[ "$(cat "$backup_dir/timer-enabled")" == enabled ]]; then systemctl enable needle-metrika.timer; fi
  if [[ "$(cat "$backup_dir/timer-active")" == active ]]; then systemctl start needle-metrika.timer; fi
  echo 'Reporter installation failed; previous reporter configuration restored. Lead service unchanged.' >&2
  exit "$result"
}
trap restore EXIT
systemctl stop needle-metrika.timer 2>/dev/null || true
systemctl stop needle-metrika.service 2>/dev/null || true
install -m 0600 /opt/needle-metrika/metrika.env.next /etc/needle-shark/metrika.env
rm /opt/needle-metrika/metrika.env.next
printf '%s\n' "$2" > "$release_dir/COMMIT"
ln -sfn "$release_dir" /opt/needle-metrika/current.next
mv -Tf /opt/needle-metrika/current.next /opt/needle-metrika/current
if test -f "$backup_dir/current"; then ln -sfn "$(cat "$backup_dir/current")" /opt/needle-metrika/previous; fi
for unit in needle-metrika.service needle-metrika.timer; do
  install -m 0644 "$release_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
# First initialization sets activation time; it does not replay historical reports.
systemctl start needle-metrika.service
systemctl enable --now needle-metrika.timer
systemctl is-active --quiet needle-metrika.timer needle-leads nginx postgresql@16-main needle-monitor.timer needle-cleanup.timer
test "$(readlink /opt/needle-shark/current)" = "$(cat "$backup_dir/backend-current")"
test "$(readlink /var/www/needle-shark/current)" = "$(cat "$backup_dir/static-current")"
trap - EXIT
printf 'Metrika reporter installed: %s\nConfiguration backup: %s\n' "$release_dir" "$backup_dir"
REMOTE
