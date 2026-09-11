"""Checks for seasonal visibility, ordering and optional product sections."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import render

PRODUCT = json.loads((render.ROOT / 'catalog/products.json').read_text())['products'][0]


class CatalogueTests(unittest.TestCase):
    def test_social_image_comes_from_this_product(self):
        product = copy.deepcopy(PRODUCT)
        product['images'].reverse()
        schema = render.product_schema(product)
        html = render.shell('', product['name'], product['description'], product['name'],
                            product_slug=product['slug'], structured=schema)
        self.assertIn(f'property="og:image" content="{schema["image"][0]}"', html)
        self.assertIn(f'property="og:image:alt" content="{product["name"]}"', html)

    def test_schema_matches_visible_facts_without_invented_offer(self):
        schema = render.product_schema(PRODUCT)
        self.assertEqual(schema['name'], PRODUCT['name'])
        self.assertEqual(schema['material'], PRODUCT['material'])
        self.assertEqual(len(schema['size']), len(PRODUCT['sizes']))
        self.assertNotIn('offers', schema)
        self.assertNotIn('aggregateRating', schema)
        self.assertNotIn('review', schema)

    def test_hidden_product_keeps_page_and_homepage(self):
        product = copy.deepcopy(PRODUCT)
        product['visible'] = False
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dist = root / 'dist'
            (root / 'catalog').mkdir()
            (root / 'catalog/products.json').write_text(json.dumps({'products': [product]}))
            for image in product['images']:
                path = dist / image['src'].lstrip('/')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'test asset')
            (dist / 'index.html').write_text('Existing homepage')
            with patch.object(render, 'ROOT', root), patch.object(render, 'DIST', dist):
                render.render()
            self.assertNotIn(f'/catalog/{product["slug"]}/', (dist / 'catalog/index.html').read_text())
            self.assertIn(product['name'], (dist / 'catalog' / product['slug'] / 'index.html').read_text())
            self.assertEqual((dist / 'index.html').read_text(), 'Existing homepage')

    def test_catalogue_order_is_driven_by_data(self):
        first, second = copy.deepcopy(PRODUCT), copy.deepcopy(PRODUCT)
        first.update(slug='earlier', order=1)
        second.update(slug='later', order=20)
        html = render.catalogue([second, first])
        self.assertLess(html.index('/catalog/earlier/'), html.index('/catalog/later/'))

    def test_disabled_section_removes_navigation_target(self):
        product = copy.deepcopy(PRODUCT)
        product['sections'].remove('sizes')
        html = render.hero(product) + render.detail_sections(product)
        self.assertNotIn('href="#sizes"', html)
        self.assertNotIn('id="sizes"', html)
        self.assertIn('data-request="Подбор размера"', html)

    def test_real_market_link_enables_only_its_marketplace(self):
        product = copy.deepcopy(PRODUCT)
        product['marketplaces'][0]['url'] = 'https://www.ozon.ru/product/example/'
        html = render.markets(product)
        self.assertIn('href="https://www.ozon.ru/product/example/"', html)
        self.assertNotIn('aria-label="Ozon: покупка пока недоступна"', html)
        self.assertIn('disabled aria-label="Wildberries: покупка пока недоступна"', html)


if __name__ == '__main__':
    unittest.main()
