"""Validate ready static pages and local links without contacting third parties."""
import json
import hashlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import ORIGIN, public_path, prepare_html
DIST = ROOT / 'dist'


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.links, self.headings, self.metadata = [], [], [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if re.fullmatch(r'h[1-6]', tag):
            self.headings.append(tag)
        if tag in ('meta', 'link'):
            self.metadata.append(attrs)
        for attr in ('href', 'src'):
            if attr in attrs:
                self.links.append(attrs[attr])
        if 'srcset' in attrs:
            self.links.extend(item.strip().split()[0] for item in attrs['srcset'].split(','))
        if tag == 'img':
            assert 'alt' in attrs, 'Image without alt'
            if attrs.get('src', '').startswith(('https:', 'http:')):
                return  # Existing analytics noscript pixel.
            assert 'width' in attrs and 'height' in attrs, 'Image without intrinsic dimensions'


def resolve(base, url):
    target = DIST / url.lstrip('/') if url.startswith('/') else base.parent / url
    target = target.resolve()
    assert target.is_relative_to(DIST.resolve()), 'Link escapes public directory'
    if target.is_dir():
        target /= 'index.html'
    if not target.exists() and not target.suffix:
        target = target.with_suffix('.html')
    return target


def check():
    pages = {}
    for path in DIST.rglob('*.html'):
        source = path.read_text()
        page = Page(source)
        pages[path.resolve()] = page
        assert page.headings.count('h1') == 1, f'{path}: expected one H1'
        assert len(page.ids) == len(set(page.ids)), f'{path}: duplicate id'
        assert 'noindex' not in source.lower(), f'{path}: noindex'
        assert source == prepare_html(source, path.relative_to(DIST)), f'{path}: publication preparation is stale'
        assert len(re.findall(r'<title>[^<]+</title>', source)) == 1, f'{path}: title'
        for field in ['description', 'robots']:
            assert sum(m.get('name') == field for m in page.metadata) == 1, f'{path}: {field}'
        for field in ['canonical', 'apple-touch-icon', 'manifest']:
            assert sum(m.get('rel') == field for m in page.metadata) == 1, f'{path}: {field}'
        assert any(m.get('href') == ORIGIN + public_path(path.relative_to(DIST)) for m in page.metadata)
        for raw in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', source, re.S):
            json.loads(raw)
    for path, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            target = resolve(path, unquote(url.path)) if url.path else path
            assert target.exists(), f'{path}: missing {link}'
            if url.fragment and target in pages:
                assert unquote(url.fragment) in pages[target].ids, f'{path}: missing anchor {link}'
    css = '\n'.join(p.read_text() for p in DIST.glob('*.css'))
    definitions = set(re.findall(r'(--[\w-]+)\s*:', css))
    references = set(re.findall(r'var\((--[\w-]+)', css))
    assert references <= definitions, f'Undefined CSS tokens: {references - definitions}'
    assert '@import' not in css, 'External/imported stylesheet blocks rendering'
    for url in re.findall(r'url\([\'"]?([^\)\'"]+)', css):
        assert resolve(DIST / 'style.css', url).exists(), f'Missing CSS resource: {url}'
    tree = ElementTree.parse(DIST / 'sitemap.xml')
    urls = [node.text for node in tree.findall('.//{*}loc')]
    assert set(urls) == {ORIGIN + public_path(p.relative_to(DIST)) for p in pages}, 'Sitemap must match generated public pages'
    assert len(urls) == len(set(urls)), 'Duplicate sitemap URL'
    for icon in json.loads((DIST / 'site.webmanifest').read_text())['icons']:
        assert (DIST / icon['src'].lstrip('/')).is_file()
    manifest = json.loads((ROOT / 'ops/image-manifest.json').read_text())
    for source, entry in manifest.items():
        original = DIST / source.lstrip('/')
        assert hashlib.sha256(original.read_bytes()).hexdigest() == entry['sha256'], f'Image changed; optimize again: {source}'
        for variant in entry['variants']:
            asset = DIST / variant['src'].lstrip('/')
            assert asset.is_file() and asset.stat().st_size == variant['bytes'], f'Missing/changed derivative: {asset}'
    print(f'Checked {len(pages)} pages: metadata, JSON-LD, sitemap, local assets, links, anchors and CSS tokens.')


if __name__ == '__main__':
    check()
