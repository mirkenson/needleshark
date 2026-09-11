import unittest
from html import unescape
from urllib.parse import parse_qs, urlsplit
from site_utils import prepare_html

class PublicTests(unittest.TestCase):
    def test_metadata_is_complete_idempotent_and_escaped(self):
        import json
        import re
        source = '<head><title>Чехол &amp; ткань</title><meta name="description" content="Размеры &quot;XL&quot;"></head><main><h1>Чехол</h1></main>'
        result = prepare_html(source, 'catalog/example/index.html')
        self.assertEqual(result, prepare_html(result, 'catalog/example/index.html'))
        for value in ['rel="canonical"', 'property="og:title"', 'name="robots"', 'id="site-schema"', 'rel="apple-touch-icon"']:
            self.assertEqual(result.count(value), 1)
        graph = json.loads(re.search(r'<script type="application/ld\+json" id="site-schema">(.*?)</script>', result)[1])['@graph']
        self.assertEqual(graph[-1]['name'], 'Чехол & ткань')
        self.assertEqual(graph[-1]['description'], 'Размеры "XL"')
        self.assertEqual(graph[0]['email'], 'info@neesha.ru')
        self.assertNotIn('aggregateRating', result)

    def test_internal_documents_normalized_without_changing_query(self):
        result = prepare_html('<head></head><a href="/privacy-policy.html?source=form#rights">Политика</a><a href="/blog/index.html">Блог</a>', 'index.html')
        self.assertIn('href="/privacy-policy?source=form#rights"', result)
        self.assertIn('href="/blog/"', result)

    def test_responsive_images_retain_actual_dimensions_and_small_thumbnails(self):
        from site_utils import image_attributes
        photo = image_attributes('/atv-cover.png')
        thumb = image_attributes('/catalog-assets/atv-studio.jpg', thumbnail=True)
        self.assertEqual((photo['width'], photo['height']), (900, 1124))
        self.assertTrue(photo['src'].endswith('.webp'))
        self.assertIn('900w', photo['srcset'])
        self.assertEqual(thumb['srcset'].count(','), 0)
        self.assertIn('160w', thumb['srcset'])

    def test_canonical_is_updated_after_domain_migration(self):
        source='<head><link rel="canonical" href="https://needleshark.ru/catalog/"></head>'
        result=prepare_html(source,'catalog/index.html')
        self.assertEqual(result.count('rel="canonical"'),1)
        self.assertIn('href="https://needle-shark.ru/catalog/"',result)
        for host in ('needle-shark.ru','www.needle-shark.ru','needleshark.ru','www.needleshark.ru'):
            self.assertNotIn('utm_',prepare_html(f'<head></head><a href="https://{host}/catalog/">A</a>','index.html'))

    def test_tracking_preserves_query_fragment_and_is_idempotent(self):
        source='<head></head><a href="https://example.com/item?size=XL&amp;size=L&amp;utm_campaign=existing#sizes">Buy</a>'
        result=prepare_html(source,'blog/story/index.html')
        self.assertEqual(result,prepare_html(result,'blog/story/index.html'))
        self.assertIn('https://needle-shark.ru/blog/story/',result)
        href=unescape(result.split('<a href="')[1].split('"')[0])
        parsed=urlsplit(href)
        self.assertEqual(parsed.fragment,'sizes')
        self.assertEqual(parse_qs(parsed.query)['size'],['XL','L'])
        self.assertEqual(parse_qs(parsed.query)['utm_campaign'],['existing'])
        self.assertEqual(parse_qs(parsed.query)['utm_source'],['needle-shark.ru'])

    def test_internal_special_and_resource_urls_untouched(self):
        source='<head></head><a href="/catalog/">A</a><a href="https://www.needle-shark.ru/blog/">B</a><a href="mailto:info@neesha.ru">C</a><script src="https://mc.yandex.ru/tag.js"></script><img src="https://example.com/a.png">'
        self.assertNotIn('utm_',prepare_html(source,'index.html'))
