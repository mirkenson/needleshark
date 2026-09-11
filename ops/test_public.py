import unittest
from html import unescape
from urllib.parse import parse_qs, urlsplit
from site_utils import prepare_html

class PublicTests(unittest.TestCase):
    def test_tracking_preserves_query_fragment_and_is_idempotent(self):
        source='<head></head><a href="https://example.com/item?size=XL&amp;size=L&amp;utm_campaign=existing#sizes">Buy</a>'
        result=prepare_html(source,'blog/story/index.html')
        self.assertEqual(result,prepare_html(result,'blog/story/index.html'))
        self.assertIn('https://needleshark.ru/blog/story/',result)
        href=unescape(result.split('<a href="')[1].split('"')[0])
        parsed=urlsplit(href)
        self.assertEqual(parsed.fragment,'sizes')
        self.assertEqual(parse_qs(parsed.query)['size'],['XL','L'])
        self.assertEqual(parse_qs(parsed.query)['utm_campaign'],['existing'])
        self.assertEqual(parse_qs(parsed.query)['utm_source'],['needleshark.ru'])

    def test_internal_special_and_resource_urls_untouched(self):
        source='<head></head><a href="/catalog/">A</a><a href="https://www.needleshark.ru/blog/">B</a><a href="mailto:info@neesha.ru">C</a><script src="https://mc.yandex.ru/tag.js"></script><img src="https://example.com/a.png">'
        self.assertNotIn('utm_',prepare_html(source,'index.html'))
