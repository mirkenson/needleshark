#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
remote_host="needledeploy@194.87.99.98"
ssh_key="${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}"
release="$(date -u +%Y%m%dT%H%M%SZ)-$$"
remote_release="/var/www/needle-shark/releases/$release"
ssh_options=(-i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
transfer_mode="${1:-local}"
case "$transfer_mode" in local|--from-github) ;; *) printf 'Usage: %s [--from-github]\n' "$0" >&2; exit 2 ;; esac
test -f "$project_dir/dist/index.html"
revision="$(git -C "$project_dir" rev-parse HEAD)"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
git -C "$project_dir" diff --exit-code HEAD -- dist >/dev/null
test -z "$(git -C "$project_dir" ls-files --others --exclude-standard -- dist)"
git -C "$project_dir" merge-base --is-ancestor "$revision" '@{upstream}'
manifest="$(mktemp)"
trap 'rm -f "$manifest"' EXIT
python3 - "$project_dir/dist" > "$manifest" <<'PY'
from pathlib import Path
import hashlib,sys
root=Path(sys.argv[1])
for path in sorted(root.rglob('*')):
    if path.is_symlink():
        raise ValueError('Release assets must be regular files')
    if path.is_file():
        name=path.relative_to(root).as_posix()
        if '\n' in name or '\\' in name:
            raise ValueError('Unsupported release filename')
        print(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name)
PY
ssh "${ssh_options[@]}" "$remote_host" "mkdir -p '$remote_release'"
if [[ "$transfer_mode" == --from-github ]]; then
  # Reuse matching current files and fetch missing assets from the immutable public revision.
  python3 "$project_dir/ops/fetch-static-release.py" --directory "$project_dir/dist" --revision "$revision" --release "$remote_release" --host "$remote_host" --key "$ssh_key"
else
  scp -r "${ssh_options[@]}" "$project_dir"/dist/* "$remote_host:$remote_release/"
fi
ssh "${ssh_options[@]}" "$remote_host" "cd '$remote_release' && sha256sum --check --status" < "$manifest"
ssh "${ssh_options[@]}" "$remote_host" "set -eu; test -s '$remote_release/index.html'; chmod -R u=rwX,go=rX '$remote_release'; cd /var/www/needle-shark; if test -L current; then ln -sfn \"\$(readlink current)\" previous; fi; ln -s '$remote_release' 'next-$release'; mv -Tf 'next-$release' current"
printf 'Published: https://needle-shark.ru/ (release %s, commit %s)\n' "$release" "$revision"
