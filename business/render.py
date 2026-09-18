"""Render the approved B2B page for publication or an isolated noindex preview."""
import argparse
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html


def render_page(destination):
    destination = Path(destination).resolve()
    page_dir = destination / 'business'
    page_dir.mkdir(parents=True, exist_ok=True)
    images = {}
    shutil.copytree(ROOT / 'business/assets', page_dir / 'assets', dirs_exist_ok=True)
    manifest = json.loads((ROOT / 'business/assets/manifest.json').read_text())
    for name, key in [('hero', 'hero-jack'), ('covers', 'category-covers'),
                      ('bags', 'category-bags'), ('straps', 'category-straps'),
                      ('workshop', 'workshop-room'), ('cutting', 'workshop-cutting'),
                      *[(fabric, 'fabric-' + fabric) for fabric in
                        ['oxford', 'canvas', 'spunbond', 'cordura', 'polyester']]]:
        sizes = '(max-width: 800px) 90vw, 45vw' if name == 'hero' else '(max-width: 700px) 90vw, 40vw'
        if name == 'workshop':
            sizes = '(max-width: 700px) 90vw, 55vw'
        attrs = dict(src=f'/business/assets/{key}-800.webp',
                     srcset=', '.join(f'/business/assets/{key}-{w}.webp {w}w' for w in [480, 800, 1280]),
                     sizes=sizes, **manifest[key])
        images[name] = ' '.join(f'{attr}="{escape(str(value), quote=True)}"' for attr, value in attrs.items())
    source = Template((ROOT / 'business/index.html').read_text()).substitute(images)
    (page_dir / 'index.html').write_text(prepare_html(source, 'business/index.html'))
    for filename in ['business.css', 'business.js']:
        shutil.copy2(ROOT / 'business' / filename, page_dir / filename)
    return page_dir


def build(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or destination.is_relative_to(ROOT / 'dist'):
        raise ValueError('Prototype output must be outside the production dist directory')
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'dist', destination, dirs_exist_ok=True)
    render_page(destination)
    for page in destination.rglob('*.html'):
        html = page.read_text()
        html = re.sub(r'<meta name="robots" content="[^"]*">',
                      '<meta name="robots" content="noindex,nofollow">', html)
        page.write_text(html)
    (destination / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='/tmp/needle-shark-business-preview')
    parser.add_argument('--publish', action='store_true', help='Render approved page into dist; does not deploy')
    args = parser.parse_args()
    print(render_page(ROOT / 'dist') if args.publish else build(args.output))
