"""Create the shareable ZIP from an explicit public file allowlist."""
from pathlib import Path
import hashlib
import json
import zipfile

here = Path(__file__).resolve().parent
root = here.parent.parent
files = {name: here / name for name in (
    'START_HERE.txt', 'BRAND_KNOWLEDGE.md', 'AGENT_INSTRUCTIONS.txt',
    'assets/logo.svg', 'assets/logo-email.png',
    'assets/email-received.png', 'assets/email-quote.jpg',
    'fonts/manrope-cyrillic.woff2', 'fonts/manrope-latin.woff2', 'fonts/OFL.txt',
)}
files['Needle-Shark-Brand-Guide.pdf'] = root / 'output/pdf/Needle-Shark-Brand-Guide.pdf'
out = root / 'output/Needle-Shark-Visual-Knowledge-v1.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, path in files.items():
        z.write(path, 'Needle-Shark-Visual-Knowledge-v1/' + name)
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(files)
    for name, path in files.items():
        assert z.read('Needle-Shark-Visual-Knowledge-v1/' + name) == path.read_bytes()
manifest = {name: {'bytes':path.stat().st_size, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for name,path in files.items()}
(root / 'tmp/pdfs/brand-handoff/package-check.json').write_text(json.dumps({'archive_bytes':out.stat().st_size,'archive_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':manifest},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'archive':str(out),'bytes':out.stat().st_size,'files':len(files)},ensure_ascii=False))
