import unittest
from html import unescape
from urllib.parse import parse_qs, urlsplit
from site_utils import prepare_html

class PublicTests(unittest.TestCase):
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
