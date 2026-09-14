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
    def test_variants_have_only_confirmed_combinations_and_distinct_links(self):
        products = json.loads((render.ROOT / 'catalog/products.json').read_text())['products']
        self.assertEqual(len(products), 3)
        moto, wheel = products[1:]
        for product in (moto, wheel):
            render.validate_variants(product)
            data = render.variant_data(product)
            self.assertEqual(len({v['ozonUrl'] for v in data}), len(data))
            self.assertTrue(all('utm_campaign=vendor_org_211216' in v['ozonUrl'] for v in data))
        self.assertEqual({v['options']['size'] for v in moto['variants'] if v['options']['configuration'] == 'heat'}, {'m', 'l'})
        self.assertEqual(moto['variants'][0]['legacySize'], '170 × 90 × 100')
        self.assertEqual([v['unitsPerPack'] for v in wheel['variants']], [4, 1])
        self.assertEqual(wheel['variants'][0]['legacySize'], '')
        self.assertNotIn('Д × Ш × В', str(render.product_schema(wheel)['size']))

    def test_variant_context_uses_existing_server_contract_and_supports_colours(self):
        import sys
        sys.path.insert(0, str(render.ROOT / 'server'))
        from lead_context import validate_context, google_payload
        product = copy.deepcopy(json.loads((render.ROOT / 'catalog/products.json').read_text())['products'][2])
        product['optionGroups'].insert(1, {'id': 'color', 'label': 'Цвет', 'values': [{'id': 'black', 'label': 'Чёрный'}]})
        for variant in product['variants']:
            variant['options']['color'] = 'black'
        render.validate_variants(product)
        for variant in render.variant_data(product):
            context = validate_context({'product_slug': product['slug'], 'product_name': product['name'],
                                        'product_size': variant['legacySize'], 'quantity': 2 * variant['unitsPerPack']})
            lead = google_payload({**context, 'question': variant['context'] + '\n' + variant['sizeLabel']})
            self.assertIn('Цвет: Чёрный', lead['question'])
            self.assertIn('Комплектация:', lead['question'])
            self.assertIn('R17–R22', lead['question'])

    def test_duplicate_and_unknown_variant_options_are_rejected(self):
        product = copy.deepcopy(json.loads((render.ROOT / 'catalog/products.json').read_text())['products'][1])
        product['variants'].append(copy.deepcopy(product['variants'][0]))
        with self.assertRaises(ValueError):
            render.validate_variants(product)
        product['variants'].pop()
        product['variants'][0]['options']['size'] = 'unknown'
        with self.assertRaises(ValueError):
            render.validate_variants(product)

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
