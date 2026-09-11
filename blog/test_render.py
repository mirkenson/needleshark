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

    def test_article_inherits_counter_and_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            render([POST], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertEqual(html.count('src="/metrika.js?v=20260911"'), 1)
            self.assertIn('https://mc.yandex.ru/watch/112428810', html)
            self.assertIn('src="/analytics.js?v=20260911-publish"', html)
            self.assertIn('href="/blog/"', html.split('</header>')[0])

    def test_cta_metadata_and_optional_faq(self):
        import json
        import re
        post = {**POST, 'author': 'Тестовый автор', 'updated': '2026-09-12', 'seoTitle': 'SEO title', 'blocks': [
            dict(type='paragraph', text='Перед CTA'),
            dict(type='cta', id='selection', lead='Подводка', text='Предложение', label='Каталог', url='/catalog/'),
            dict(type='paragraph', text='После CTA'),
            dict(type='faq', items=[dict(question='Вопрос?', answer='Ответ.')])
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertLess(html.index('Перед CTA'), html.index('class="article-cta"'))
            self.assertLess(html.index('class="article-cta"'), html.index('После CTA'))
            self.assertIn('data-blog-cta="selection" data-article="test"', html)
            self.assertIn('<link rel="canonical" href="https://needleshark.ru/blog/test/">', html)
            self.assertIn('<title>SEO title</title>', html)
            self.assertEqual(html.count('<h1>'), 1)
            self.assertIn('<h3>Вопрос?</h3>', html)
            data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
            self.assertEqual(data['headline'], POST['title'])
            self.assertEqual(data['author']['name'], post['author'])
            self.assertNotIn('image', data)

    def test_reject_unsafe_cta_urls(self):
        for url in ['javascript:alert(1)', '//evil.example', '/\\evil.example', 'https://user:pass@example.com', 'https://example.com/ bad']:
            post = {**POST, 'blocks': [dict(type='cta', id='link', lead='a', text='b', label='c', url=url)]}
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                render([post], Path(tmp))

    def test_sources_escape_text_and_reject_unsafe_links(self):
        post = {**POST, 'blocks': [dict(type='sources', items=[dict(title='<b>Manual</b>', url='https://example.com/manual')])]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertIn('&lt;b&gt;Manual&lt;/b&gt;', html)
            post['blocks'][0]['items'][0]['url'] = 'javascript:alert(1)'
            with self.assertRaises(ValueError):
                render([post], Path(tmp))
