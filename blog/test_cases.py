"""Case drafts must never leak into a public build or invent publication dates."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from b2b import render as site
from blog.blocks import validate_blocks
from blog.render import article_image


class CaseTests(unittest.TestCase):
    def test_draft_is_review_only_and_public_shell_has_no_dead_case_links(self):
        posts = json.loads((site.ROOT/'blog/posts.json').read_text())
        for post in posts:
            if post.get('kind') == 'case':
                post['status'] = 'draft'
        case = next(p for p in posts if p.get('kind') == 'case')
        original_read = Path.read_text
        def fixture_read(path, *args, **kwargs):
            if path == site.ROOT/'blog/posts.json':
                return json.dumps(posts, ensure_ascii=False)
            return original_read(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch.object(Path, 'read_text', fixture_read):
            preview = site.build(Path(tmp)/'preview')
            html = (preview/'cases'/case['slug']/'index.html').read_text()
            self.assertIn('noindex,nofollow',html)
            self.assertNotIn('datePublished',html)
            self.assertNotIn('Опубликовано',html)
            self.assertNotIn('/metrika.js',html)
            self.assertTrue((preview/'cases/index.html').is_file())
            self.assertFalse((preview/'blog'/case['slug']/'index.html').exists())
            self.assertNotIn(case['slug'], (preview/'blog/index.html').read_text())
            self.assertIn('data-preview="true"', html)
            self.assertEqual(html.count('class="ns-form ym-hide-content"'), 1)
            self.assertIn('/cases/' + case['slug'] + '/#contact', html)
            for forbidden in ('моего', 'Визуализация', 'с использованием ИИ', 'файлы не прикрепляются'):
                self.assertNotIn(forbidden, html)
            site.build(preview, preview_chat=True)
            for path in preview.rglob('*.html'):
                text = path.read_text()
                self.assertEqual(len(re.findall(r'<script[^>]+src="/b2b/chat\.js', text)), 1)
                self.assertNotIn('/metrika.js', text)
            # Reusing a destination must not retain draft cases or append a second form.
            site.build(preview, preview=False)
            self.assertFalse((preview/'cases/index.html').exists())
            self.assertFalse((preview/'cases'/case['slug']/'index.html').exists())
            site.build(preview)
            for path in preview.rglob('*.html'):
                self.assertIn('href="/cases/"',path.read_text())
            public = site.build(Path(tmp)/'public', preview=False)
            self.assertFalse((public/'cases/index.html').exists())
            self.assertFalse((public/'cases'/case['slug']/'index.html').exists())
            self.assertNotIn('href="/cases/"',(public/'index.html').read_text())

    def test_case_media_is_registered_and_selected_from_visible_body(self):
        case = next(p for p in json.loads((site.ROOT/'blog/posts.json').read_text()) if p.get('kind') == 'case')
        photo = article_image(case)
        self.assertEqual(photo['url'],'https://needle-shark.ru/blog/assets/robot-overall-1448.webp')
        invalid = copy.deepcopy(case)
        invalid['seoImage'] = {'asset':'robot-joint'}
        with self.assertRaises(ValueError):
            article_image(invalid)
        with self.assertRaises(ValueError):
            validate_blocks([{'type':'image','asset':'missing','caption':'Example'}])
        with self.assertRaises(ValueError):
            validate_blocks([{'type':'facts','items':[{'label':'Missing value'}]}])
        with self.assertRaises(ValueError):
            validate_blocks([{'type':'gallery','items':[]}])


if __name__ == '__main__':
    unittest.main()
