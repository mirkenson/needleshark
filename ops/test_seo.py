import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from ops.seo_checks import Metadata, check_inventory, check_page, registry
from site_utils import prepare_html

ROOT = Path(__file__).resolve().parents[1]


class SEOContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = {r['canonical']: r for r in registry()}
        cls.pages = {url: Metadata((ROOT / 'dist' / r['file']).read_text()) for url, r in cls.records.items()}

    def reject(self, url, source):
        with self.assertRaises(AssertionError):
            check_page(self.records[url], Metadata(source), self.pages, ROOT / 'dist')

    def mutate_schema(self, url, kind, mutate):
        def rewrite(match):
            from ops.seo_checks import nodes
            data = json.loads(match[2])
            for node in nodes(data):
                if node.get('@type') == kind:
                    mutate(node)
            return match[1] + json.dumps(data, ensure_ascii=False) + match[3]
        source = re.sub(r'(<script type="application/ld\+json"[^>]*>)(.*?)(</script>)', rewrite, self.pages[url].source, flags=re.S)
        self.reject(url, source)

    def test_registered_pages_pass(self):
        for url, record in self.records.items():
            with self.subTest(url=url):
                check_page(record, self.pages[url], self.pages, ROOT / 'dist')

    def test_inventory_rejects_missing_or_unknown_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            records = [{'file': 'index.html'}]
            with self.assertRaises(AssertionError):
                check_inventory(dist, records)
            (dist / 'index.html').write_text('known')
            check_inventory(dist, records)
            (dist / 'unexpected.html').write_text('unknown')
            with self.assertRaises(AssertionError):
                check_inventory(dist, records)

    def test_canonical_is_not_satisfied_by_other_href_or_body(self):
        url = 'https://needle-shark.ru/catalog/'
        source = self.pages[url].source
        tag = '<link rel="canonical" href="' + url + '">'
        for broken in [source.replace(tag, tag.replace('canonical','alternate')),
                       source.replace(tag, '').replace('</body>', tag+'</body>'),
                       source.replace(tag, tag*2), source.replace(tag, tag.replace(url,'https://needle-shark.ru/')),
                       source.replace(tag, tag.replace(url,url+'?utm_source=qa'))]:
            self.reject(url, broken)

    def test_preparation_normalizes_legacy_canonical_syntax_once(self):
        source = "<head><title>Test</title><LINK href='old' REL='CANONICAL'></head><body><link rel=canonical href=wrong></body>"
        result = prepare_html(source, 'catalog/index.html')
        self.assertEqual(result, prepare_html(result, 'catalog/index.html'))
        p = Metadata(result)
        self.assertEqual([(a['href'],inside) for t,a,inside in p.tags if t=='link' and a.get('rel')=='canonical'], [('https://needle-shark.ru/catalog/',True)])

    def test_social_identity_and_image_cannot_silently_fall_back(self):
        url = 'https://needle-shark.ru/napravleniya/chehly/'
        source = self.pages[url].source
        self.reject(url,source.replace('property="og:url" content="'+url, 'property="og:url" content="https://needle-shark.ru/'))
        self.reject(url,source.replace(self.records[url]['image'],'https://needle-shark.ru/brand-preview.png'))

    def test_service_and_provider_must_keep_canonical_identity(self):
        url = 'https://needle-shark.ru/napravleniya/chehly/'
        self.mutate_schema(url,'Service',lambda n:n.update(url='https://needle-shark.ru/catalog/retired/'))
        self.mutate_schema(url,'Service',lambda n:n.update(provider={'@id':'https://needleshark.ru/#organization'}))
        self.mutate_schema(url,'Service',lambda n:n.update({'@type':'Thing'}))

    def test_itemlist_matches_visible_card_order_and_count(self):
        for url in ['https://needle-shark.ru/catalog/','https://needle-shark.ru/blog/']:
            self.mutate_schema(url,'ItemList',lambda n:n['itemListElement'].reverse())
            self.mutate_schema(url,'ItemList',lambda n:n.update(numberOfItems=0))

    def test_article_dates_and_image_match_visible_content(self):
        url = 'https://needle-shark.ru/blog/zimnee-hranenie-motocikla-i-kvadrocikla/'
        self.mutate_schema(url,'BlogPosting',lambda n:n.update(dateModified='2099-01-01'))
        self.mutate_schema(url,'ImageObject',lambda n:n.update(url='https://needle-shark.ru/brand-preview.png'))

    def test_article_image_selection_requires_visible_image(self):
        from blog.render import validate
        post = copy.deepcopy(json.loads((ROOT/'blog/posts.json').read_text())[0])
        post['seoImage']={'product':'chehol-na-kvadrocikl','image':'not-in-article'}
        with self.assertRaises(ValueError):
            validate([post])

    def test_invented_offer_is_rejected(self):
        url = 'https://needle-shark.ru/napravleniya/chehly/'
        self.mutate_schema(url,'Service',lambda n:n.update(offers={'@type':'Offer','price':0}))


if __name__ == '__main__':
    unittest.main()
