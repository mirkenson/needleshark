import tempfile
import unittest
from pathlib import Path

from business.render import ROOT, build, render_page


class PublicationTests(unittest.TestCase):
    def test_public_and_preview_have_separate_indexing_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            public = render_page(destination / 'public') / 'index.html'
            original = public.read_bytes()
            self.assertIn(b'index,follow,max-image-preview:large', original)
            self.assertIn(b'https://needle-shark.ru/business/', original)
            preview = build(destination / 'preview')
            self.assertIn('noindex,nofollow', (preview / 'business/index.html').read_text())
            self.assertIn('Disallow: /', (preview / 'robots.txt').read_text())
            self.assertEqual(public.read_bytes(), original)

    def test_preview_refuses_production_destinations(self):
        for destination in (ROOT, ROOT / 'dist', ROOT / 'dist/business'):
            with self.assertRaises(ValueError):
                build(destination)
