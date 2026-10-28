#!/bin/bash
# Upgrade an existing reporter only. Does not execute reports/tests or send messages.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
revision="$(git -C "$project_dir" rev-parse HEAD)"
git -C "$project_dir" diff --exit-code HEAD -- server/metrika_reports.py server/metrika_pages.json ops/upgrade-metrika.sh >/dev/null
git -C "$project_dir" merge-base --is-ancestor "$revision" '@{upstream}'
host=root@194.87.99.98
options=(-i "${NEEDLE_SHARK_SSH_KEY:-$HOME/.ssh/needle_shark_ed25519}" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15)
release="$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp "$project_dir"/server/{metrika_reports.py,metrika_pages.json} "$stage/"
python3 - "$stage" "$revision" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
(p/'COMMIT').write_text(sys.argv[2]+'\n')
(p/'update-manifest.json').write_text(json.dumps({x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in p.iterdir()}))
PY
ssh "${options[@]}" "$host" "install -d -m 0700 '/opt/needle-metrika/backups/$release/update'"
scp "${options[@]}" "$stage"/* "$host:/opt/needle-metrika/backups/$release/update/"
ssh "${options[@]}" "$host" python3 - "$release" <<'PY'
import fcntl,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
base=Path('/opt/needle-metrika'); backup=base/'backups'/sys.argv[1]; incoming=backup/'update'
state=Path('/var/lib/needle-metrika/state.json')
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def pointer(path): return os.readlink(path) if path.is_symlink() else None
def swap(path,target):
    temp=path.with_name(path.name+'.upgrade')
    temp.symlink_to(target); os.replace(temp,path)
with (state.parent/'lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    current=base/'current'; previous=base/'previous'
    old=current.resolve(strict=True)
    if old.parent != base/'releases': raise SystemExit('Unexpected current release')
    manifest=json.loads((incoming/'update-manifest.json').read_text())
    if set(manifest)!={'COMMIT','metrika_reports.py','metrika_pages.json'}: raise SystemExit('Unexpected update files')
    for name,sha in manifest.items():
        if digest(incoming/name)!=sha: raise SystemExit('Upload hash mismatch')
    pointers={str(p):pointer(p) for p in [current,previous,Path('/opt/needle-shark/current'),Path('/var/www/needle-shark/current')]}
    protected=[state,Path('/etc/needle-shark/metrika.env'),Path('/etc/systemd/system/needle-metrika.service'),Path('/etc/systemd/system/needle-metrika.timer')]
    hashes={str(p):digest(p) for p in protected}
    (backup/'before.json').write_text(json.dumps({'pointers':pointers,'hashes':hashes},indent=2))
    release=base/'releases'/sys.argv[1]
    release.mkdir(mode=0o755)
    for source in old.iterdir():
        if source.is_file() and source.name not in {'manifest.json','COMMIT'}:
            shutil.copyfile(source,release/source.name); os.chmod(release/source.name,0o644)
    for name in manifest:
        shutil.copyfile(incoming/name,release/name); os.chmod(release/name,0o644)
    for name,sha in manifest.items():
        if digest(release/name)!=sha: raise SystemExit('Release hash mismatch')
    (release/'manifest.json').write_text(json.dumps({p.name:digest(p) for p in release.iterdir() if p.is_file()},indent=2))
    try:
        swap(previous,str(old)); swap(current,str(release))
        for p in protected:
            if digest(p)!=hashes[str(p)]: raise RuntimeError('Protected file changed')
        for path,target in pointers.items():
            if path not in (str(current),str(previous)) and pointer(Path(path))!=target: raise RuntimeError('Site pointer changed')
        subprocess.run(['systemctl','is-active','--quiet','needle-metrika.timer'],check=True)
    except Exception:
        swap(current,str(old))
        if pointers[str(previous)] is None:
            if previous.is_symlink(): previous.unlink()
        else: swap(previous,pointers[str(previous)])
        raise
    print(json.dumps({'release':str(release),'previous':str(old),'commit':(release/'COMMIT').read_text().strip(),
                      'installed_hashes':manifest,'protected_files_unchanged':True,'report_executed':False,'messages_sent':False}))
PY
