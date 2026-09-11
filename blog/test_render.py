import copy
import tempfile
import unittest
from pathlib import Path
from render import render

POST = dict(slug='test', status='published', date='2026-09-11', title='<script>Title</script>', description='Intro', blocks=[dict(type='paragraph', text='<b>Text</b>')])


class BlogTests(unittest.TestCase):
    def test_draft_and_unpublish(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            post = copy.deepcopy(POST)
            post['status'] = 'draft'
            render([post], out)
            self.assertFalse((out / 'test/index.html').exists())
            post['status'] = 'published'
            render([post], out)
            self.assertIn('&lt;script&gt;', (out / 'test/index.html').read_text())
            post['status'] = 'draft'
            render([post], out)
            self.assertFalse((out / 'test/index.html').exists())
            self.assertIn('Публикаций пока нет', (out / 'index.html').read_text())

    def test_reject_invalid_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for changes in [dict(slug='../escape'), dict(date='bad'), dict(status='typo'), dict(blocks=[dict(type='html', text='bad')])]:
                with self.assertRaises(ValueError):
                    render([{**POST, **changes}], Path(tmp))
            with self.assertRaises(ValueError):
                render([POST, POST], Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_newest_first_and_unowned_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'manual').mkdir()
            (out / 'manual/index.html').write_text('Manual content')
            render([{**POST, 'slug': 'older', 'date': '2026-09-10'}, POST], out)
            html = (out / 'index.html').read_text()
            self.assertLess(html.index('/blog/test/'), html.index('/blog/older/'))
            self.assertEqual((out / 'manual/index.html').read_text(), 'Manual content')

    def test_featured_preserves_homepage_and_excludes_drafts(self):
        from render import render_featured
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'index.html'
            home.write_text('BEFORE<!-- BLOG_FEATURED_START -->old<!-- BLOG_FEATURED_END -->AFTER')
            posts = [{**POST, 'slug': str(i), 'featured': True} for i in range(5)]
            posts.append({**POST, 'slug': 'draft', 'status': 'draft', 'featured': True})
            render_featured(posts, home)
            result = home.read_text()
            self.assertTrue(result.startswith('BEFORE') and result.endswith('AFTER'))
            self.assertEqual(result.count('<article>'), 3)
            self.assertNotIn('/blog/draft/', result)
