"""Checks for the isolated review build, not a production release."""
import hashlib
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from b2b import render


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def find(self, tag):
        return [attrs for name, attrs in self.tags if name == tag]


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class ReviewBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.before = snapshot(render.ROOT / 'dist')
        cls.output = render.build(Path(cls.temp.name) / 'review')
        cls.pages = {p.relative_to(cls.output).as_posix(): Document(p.read_text())
                     for p in cls.output.rglob('*.html')}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_build_is_repeatable_and_keeps_production_unchanged(self):
        first = snapshot(self.output)
        render.build(self.output)
        self.assertEqual(first, snapshot(self.output))
        self.assertEqual(self.before, snapshot(render.ROOT / 'dist'))
        for destination in [render.ROOT, render.ROOT / 'dist', render.ROOT / 'dist/review']:
            with self.assertRaises(ValueError):
                render.build(destination)

    def test_preview_has_no_tracking_or_indexable_pages(self):
        for path, doc in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(len(doc.find('h1')), 1)
                robots = [a.get('content') for a in doc.find('meta') if a.get('name') == 'robots']
                self.assertEqual(robots, ['noindex,nofollow'])
                self.assertFalse(any('metrika.js' in a.get('src', '') or 'analytics.js' in a.get('src', '') for a in doc.find('script')))
                self.assertFalse(any('mc.yandex.ru' in a.get('src', '') for a in doc.find('img')))
                self.assertEqual(len([a for a in doc.find('link') if a.get('rel') == 'canonical']), 1)
        self.assertIn('Disallow: /', (self.output / 'robots.txt').read_text())

    def test_local_links_fragments_and_assets_resolve(self):
        for path, doc in self.pages.items():
            for tag, attrs in doc.tags:
                urls = []
                if tag in ('a', 'link') and attrs.get('href'):
                    urls.append(attrs['href'])
                if attrs.get('src'):
                    urls.append(attrs['src'])
                if attrs.get('srcset'):
                    urls.extend(part.strip().split()[0] for part in attrs['srcset'].split(','))
                for href in urls:
                    parsed = urlsplit(href)
                    if parsed.scheme or parsed.netloc:
                        continue
                    target = self.output / parsed.path.lstrip('/') if parsed.path.startswith('/') else self.output / Path(path).parent / parsed.path
                    if not parsed.path:
                        target = self.output / path
                    if target.is_dir():
                        target /= 'index.html'
                    if not target.exists() and not target.suffix:
                        target = target.with_suffix('.html')
                    with self.subTest(page=path, href=href):
                        self.assertTrue(target.is_file(), str(target))
                        if parsed.fragment and target.suffix == '.html':
                            target_doc = self.pages[target.relative_to(self.output).as_posix()]
                            self.assertIn(unquote(parsed.fragment), [a['id'] for _, a in target_doc.tags if 'id' in a])
                        self.assertFalse(any(k.startswith('utm_') for k in parse_qs(parsed.query)))

    def test_catalogue_links_directly_to_market_and_legacy_pages_are_absent(self):
        redirects = json.loads((self.output / 'preview-redirects.json').read_text())
        self.assertEqual(len(redirects), 26)
        self.assertEqual(list((self.output / 'catalog').glob('**/*.html')), [self.output / 'catalog/index.html'])
        for old, new in redirects.items():
            self.assertTrue(new.startswith('/catalog/#'))
            self.assertFalse((self.output / old.lstrip('/') / 'index.html').exists())
        for doc in self.pages.values():
            for a in doc.find('a'):
                parsed = urlsplit(a.get('href', ''))
                if parsed.hostname and 'ozon.ru' in parsed.hostname:
                    self.assertEqual(parse_qs(parsed.query).get('utm_campaign'), ['vendor_org_211216'])

    def test_forms_keep_only_requested_fields_and_never_put_contacts_in_urls(self):
        for path, doc in self.pages.items():
            if not doc.find('form'):
                continue
            with self.subTest(page=path):
                self.assertEqual([a.get('name') for a in doc.find('input')], ['name', 'email', 'phone', 'consent'])
                self.assertEqual([a.get('name') for a in doc.find('textarea')], ['description'])
                self.assertEqual(doc.find('form')[0]['method'], 'post')
                self.assertFalse(any(a.get('type') == 'file' for a in doc.find('input')))
                self.assertEqual(len([a for a in doc.find('button') if 'disabled' in a]), 8)


if __name__ == '__main__':
    unittest.main()
