"""Build the isolated B2B prototype without changing the publishable dist tree."""
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


def build(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or destination.is_relative_to(ROOT / 'dist'):
        raise ValueError('Prototype output must be outside the production dist directory')
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'dist', destination, dirs_exist_ok=True)
    page_dir = destination / 'business'
    page_dir.mkdir(exist_ok=True)
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
    for filename in ['business.css', 'business.js', 'preview-navigation.css']:
        shutil.copy2(ROOT / 'business' / filename, page_dir / filename)
    # Only the preview copies receive the new navigation destination.
    for page in destination.rglob('*.html'):
        html = page.read_text()
        html = re.sub(r'href="(?:/)?#business"(?=[^>]*>Для бизнеса</a>)', 'href="/business/"', html)
        if page == destination / 'index.html':
            # Expose the requested destination on phones using the site's existing menu.
            html = html.replace('<header class="wrap">', '<header class="wrap home-business-nav">')
            mobile = '<button class="menu-toggle" aria-expanded="false" aria-controls="mobile-menu">Меню <span aria-hidden="true">☰</span></button></header><nav id="mobile-menu" class="mobile-menu wrap" aria-label="Мобильная навигация" hidden><a href="/catalog/">Каталог изделий</a><a href="/blog/">Блог</a><a href="/#about">Производство</a><a href="/business/">Для бизнеса</a><a href="#contact">Обсудить заказ ↗</a></nav>'
            html = html.replace('</header>', mobile, 1)
            html = html.replace('</head>', '<link rel="stylesheet" href="/navigation.css?v=20260911-opt1"><link rel="stylesheet" href="/business/preview-navigation.css"><script src="/menu.js?v=20260911-opt1" defer></script></head>')
        html = re.sub(r'<meta name="robots" content="[^"]*">',
                      '<meta name="robots" content="noindex,nofollow">', html)
        page.write_text(html)
    (destination / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='/tmp/needle-shark-business-preview')
    args = parser.parse_args()
    print(build(args.output))
