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
published_posts = [p for p in json.loads((ROOT/'blog/posts.json').read_text()) if p['status']=='published']
paths += ['blog/' + p['slug'] + '/index.html' for p in published_posts]
for path in paths:
    if not (DIST/path).is_file():
        raise ValueError('Missing public page: ' + path)
# Only real editorial dates, never a new lastmod on every build.
dates = {'blog/' + p['slug'] + '/index.html': p.get('updated', p['date']) for p in published_posts}
entries = []
for path in paths:
    lastmod = f'<lastmod>{escape(dates[path])}</lastmod>' if path in dates else ''
    entries.append(f'  <url><loc>{escape(ORIGIN + public_path(path))}</loc>{lastmod}</url>\n')
(DIST/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(entries) + '</urlset>\n')
(DIST/'robots.txt').write_text(f'User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {ORIGIN}/sitemap.xml\n')
