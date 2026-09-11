#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
remote_host="needledeploy@194.87.99.98"
ssh_key="${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}"
release="$(date -u +%Y%m%dT%H%M%SZ)-$$"
remote_release="/var/www/needle-shark/releases/$release"
ssh_options=(-i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
test -f "$project_dir/dist/index.html"
ssh "${ssh_options[@]}" "$remote_host" "mkdir -p '$remote_release'"
scp -r "${ssh_options[@]}" "$project_dir"/dist/* "$remote_host:$remote_release/"
ssh "${ssh_options[@]}" "$remote_host" "set -eu; test -s '$remote_release/index.html'; chmod -R u=rwX,go=rX '$remote_release'; cd /var/www/needle-shark; if test -L current; then ln -sfn \"\$(readlink current)\" previous; fi; ln -s '$remote_release' 'next-$release'; mv -Tf 'next-$release' current"
printf 'Published: https://needle-shark.ru/ (release %s)\n' "$release"
