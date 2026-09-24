import copy
import tempfile
import unittest
from pathlib import Path
from render import render

POST = dict(slug='test', status='published', date='2026-09-11', title='<script>Title</script>', description='Intro', blocks=[dict(type='paragraph', text='<b>Text</b>')])


class BlogTests(unittest.TestCase):
    def test_source_label_is_optional_and_escaped(self):
        post = {**POST, 'blocks': [dict(type='sources', label='<b>Характеристики</b>', items=[dict(title='Каталог', url='/catalog/')])]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertIn('&lt;b&gt;Характеристики&lt;/b&gt;', html)
            post['blocks'][0]['label'] = ''
            with self.assertRaises(ValueError):
                render([post], Path(tmp))

    def test_isolated_preview_keeps_drafts_out_of_production(self):
        import json
        from unittest.mock import patch
        import preview
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'dist').mkdir()
            (root / 'dist/index.html').write_text('PRODUCTION SENTINEL')
            (root / 'blog').mkdir()
            draft = {**POST, 'slug': 'draft', 'status': 'draft'}
            source = json.dumps([POST, draft])
            (root / 'blog/posts.json').write_text(source)
            with patch.object(preview, 'ROOT', root):
                preview.main()
            self.assertEqual((root / 'blog/posts.json').read_text(), source)
            self.assertEqual((root / 'dist/index.html').read_text(), 'PRODUCTION SENTINEL')
            out = root / 'outputs/blog-preview'
            html = (out / 'blog/draft/index.html').read_text()
            self.assertIn('noindex,nofollow', html)
            self.assertIn('Черновик от', html)
            self.assertNotIn('datePublished', html)
            self.assertNotIn('/metrika.js', html)
            self.assertNotIn('mc.yandex.ru/watch', html)
            self.assertIn('Опубликовано', (out / 'blog/test/index.html').read_text())
            self.assertIn('Disallow: /', (out / 'robots.txt').read_text())
            self.assertNotIn('<loc>', (out / 'sitemap.xml').read_text())

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

    def test_homepage_shows_latest_three_published_posts_regardless_of_featured(self):
        from render import render_featured
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'index.html'
            home.write_text('BEFORE<!-- BLOG_FEATURED_START -->old<!-- BLOG_FEATURED_END -->AFTER')
            posts = [
                {**POST, 'slug': 'older-featured', 'featured': True},
                {**POST, 'slug': 'second-a', 'date': '2026-09-12', 'featured': False},
                {**POST, 'slug': 'newest', 'date': '2026-09-13'},
                {**POST, 'slug': 'second-z', 'date': '2026-09-12', 'featured': False},
                {**POST, 'slug': 'draft', 'date': '2026-09-14', 'status': 'draft', 'featured': True},
            ]
            render_featured(posts, home)
            result = home.read_text()
            self.assertTrue(result.startswith('BEFORE') and result.endswith('AFTER'))
            self.assertEqual(result.count('<article>'), 3)
            self.assertNotIn('/blog/draft/', result)
            self.assertNotIn('/blog/older-featured/', result)
            self.assertLess(result.index('/blog/newest/'), result.index('/blog/second-z/'))
            self.assertLess(result.index('/blog/second-z/'), result.index('/blog/second-a/'))
            render_featured(posts, home)
            self.assertEqual(home.read_text(), result)

    def test_article_inherits_counter_and_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            render([POST], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertEqual(html.count('src="/metrika.js?v=20260911"'), 1)
            self.assertIn('https://mc.yandex.ru/watch/112428810', html)
            self.assertRegex(html, r'src="/analytics\.js\?v=[^\"]+"')
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
            self.assertIn('<link rel="canonical" href="https://needle-shark.ru/blog/test/">', html)
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

    def test_editorial_text_and_nested_source_backlinks(self):
        import json
        import re
        source = dict(type='sources', items=[dict(title='Manual', url='https://example.com/manual')])
        post = {**POST, 'blocks': [
            dict(type='heading', id='preparation', text='Preparation'),
            dict(type='paragraph', text='**<script>bad()</script>** and ==dry=='), source,
            dict(type='accordion', title='Details', items=[dict(label='Read more', blocks=[source])])
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertIn('<strong>&lt;script&gt;bad()&lt;/script&gt;</strong>', html)
            self.assertIn('<mark>dry</mark>', html)
            self.assertEqual(html.count('id="note-1"'), 1)
            self.assertEqual(html.count('role="doc-noteref"'), 2)
            ids = re.findall(r'\bid="([^"]+)"', html)
            self.assertEqual(len(ids), len(set(ids)))
            for ref in re.findall(r'href="#([^"]+)"', html):
                self.assertIn(ref, ids)
            schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
            self.assertEqual(schema['citation'], ['https://example.com/manual'])

    def test_tabs_content_is_readable_before_javascript(self):
        import re
        post = {**POST, 'blocks': [dict(type='tabs', title='Choose a place', items=[
            dict(label='Garage', blocks=[dict(type='paragraph', text='Garage advice')]),
            dict(label='Outside', blocks=[dict(type='paragraph', text='Outside advice')])])
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertIn('class="article-tab-list" aria-labelledby="tabs-1-title" hidden', html)
            panels = re.findall(r'<section[^>]*class="article-tab-panel"[^>]*>', html)
            self.assertEqual(len(panels), 2)
            self.assertTrue(all('hidden' not in panel for panel in panels))
            self.assertIn('Garage advice', html)
            self.assertIn('Outside advice', html)

    def test_reject_invalid_editorial_data_before_writing(self):
        cta = dict(type='cta', id='catalog', lead='Choose', text='Cover', label='Catalogue', url='/catalog/')
        invalid = [
            [dict(type='image', product='missing', image='photo', caption='Photo')],
            [dict(type='image', product='chehol-na-kvadrocikl', image='missing', caption='Photo')],
            [dict(type='callout', title='Note', text='Text', tone='invalid')],
            [{**cta, 'links': [dict(id='ozon', label='Link', url='javascript:alert(1)')]}],
            [{**cta, 'links': [dict(id='catalog', label='Link', url='/catalog/')]}],
            [dict(type='heading', id='same', text='A'), dict(type='heading', id='same', text='B')],
            [dict(type='tabs', title='Tabs', items=[dict(label='One', blocks=[cta]), dict(label='Two', blocks=[cta])])],
        ]
        for blocks in invalid:
            with self.subTest(blocks=blocks), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    render([{**POST, 'blocks': blocks}], Path(tmp))
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_product_photo_and_secondary_cta_use_shared_assets_and_tracking(self):
        from urllib.parse import parse_qs, urlsplit
        from html import unescape
        import re
        post = {**POST, 'blocks': [dict(type='cta', id='catalog', lead='Choose', text='Cover', label='Catalogue', url='/catalog/',
            image=dict(product='chehol-na-kvadrocikl', image='atv-studio', caption='<b>Photo</b>'),
            links=[dict(id='ozon', label='Ozon', url='https://www.ozon.ru/product/2360802204/')])]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertIn('srcset="/images/', html)
            self.assertIn('loading="lazy"', html)
            self.assertIn('&lt;b&gt;Photo&lt;/b&gt;', html)
            self.assertIn('data-blog-cta="ozon" data-article="test"', html)
            url = unescape(re.search(r'href="(https://www.ozon.ru/[^"]+)"', html)[1])
            self.assertEqual(parse_qs(urlsplit(url).query)['utm_campaign'], ['vendor_org_211216'])

    def test_interactive_ids_and_article_tracking_context(self):
        post = {**POST, 'blocks': [dict(type='checklist', id='preflight', title='Checklist', items=['One', 'Two'])]}
        with tempfile.TemporaryDirectory() as tmp:
            render([post], Path(tmp))
            html = (Path(tmp) / 'test/index.html').read_text()
            self.assertIn('class="wrap blog-article" data-article="test"', html)
            self.assertIn('data-blog-block="preflight"', html)
            post['blocks'].append(dict(type='accordion', id='preflight', title='Details', items=[dict(label='More', blocks=[dict(type='paragraph', text='Text')])]))
            with self.assertRaises(ValueError):
                render([post], Path(tmp))
