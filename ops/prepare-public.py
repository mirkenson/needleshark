"""Finalize generated HTML and build sitemap from approved content only."""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html, public_path, ORIGIN
DIST = ROOT / 'dist'
for page in DIST.rglob('*.html'):
    page.write_text(prepare_html(page.read_text(), page.relative_to(DIST)))
paths = ['index.html', 'catalog/index.html', 'blog/index.html', 'privacy-policy.html', 'user-agreement.html']
paths += ['catalog/' + p['slug'] + '/index.html' for p in json.loads((ROOT/'catalog/products.json').read_text())['products']]
paths += ['blog/' + p['slug'] + '/index.html' for p in json.loads((ROOT/'blog/posts.json').read_text()) if p['status']=='published']
for path in paths:
    if not (DIST/path).is_file():
        raise ValueError('Missing public page: ' + path)
(DIST/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{escape(ORIGIN + public_path(p))}</loc></url>\n' for p in paths) + '</urlset>\n')
(DIST/'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: https://needleshark.ru/sitemap.xml\n')
