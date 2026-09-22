"""Fetch verified static files from a pinned public commit; no remote checkout/build."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from urllib.parse import quote
from urllib.request import urlopen


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def populate(files, revision, destination, reuse, opener=urlopen):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected an immutable Git commit')
    destination=Path(destination).resolve()
    reuse=Path(reuse).resolve()
    for name, expected in files.items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or name in ('', '.') or not re.fullmatch(r'[0-9a-f]{64}',expected):
            raise ValueError('Invalid release manifest')
        if not (destination/path).resolve().is_relative_to(destination):
            raise ValueError('Release path escapes destination')

    def transfer(item):
        name,expected=item
        target=destination/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_file() and digest(target)==expected:
            return 'retained'
        existing=reuse/name
        if existing.is_file() and existing.resolve().is_relative_to(reuse) and digest(existing)==expected:
            shutil.copy2(existing,target)
            return 'reused'
        temporary=target.with_name(target.name+'.download')
        url='https://raw.githubusercontent.com/mirkenson/needleshark/'+revision+'/dist/'+quote(name,safe='/')
        try:
            for attempt in range(3):
                try:
                    with opener(url,timeout=45) as response, temporary.open('wb') as stream:
                        shutil.copyfileobj(response,stream,length=262144)
                    if digest(temporary)!=expected:
                        raise ValueError('Checksum mismatch: '+name)
                    temporary.replace(target)
                    return 'downloaded'
                except (OSError,ValueError):
                    if attempt==2:
                        raise
        finally:
            temporary.unlink(missing_ok=True)

    counts={'downloaded':0,'reused':0,'retained':0}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index,result in enumerate(pool.map(transfer,files.items()),1):
            counts[result]+=1
            if index%100==0:
                print('Verified files: '+str(index)+'/'+str(len(files)),flush=True)
    print(json.dumps(counts),flush=True)
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--revision')
    parser.add_argument('--release')
    parser.add_argument('--host')
    parser.add_argument('--key')
    args=parser.parse_args()
    if args.worker:
        payload=json.load(sys.stdin)
        release=Path(payload['release'])
        if release.parent!=Path('/var/www/needle-shark/releases') or not re.fullmatch(r'[0-9TZ-]+',release.name):
            raise ValueError('Invalid remote release path')
        populate(payload['files'],payload['revision'],release,Path('/var/www/needle-shark/current'))
        return
    files={p.relative_to(args.directory).as_posix():digest(p) for p in sorted(args.directory.rglob('*')) if p.is_file()}
    payload={'files':files,'revision':args.revision,'release':args.release}
    command='python3 -c '+shlex.quote(Path(__file__).read_text())+' --worker'
    subprocess.run(['ssh','-i',args.key,'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                    '-o','ConnectTimeout=15',args.host,command],input=json.dumps(payload).encode(),check=True)


if __name__=='__main__':
    main()
