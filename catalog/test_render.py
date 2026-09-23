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
    def test_atv_sizes_have_distinct_verified_market_links(self):
        product = copy.deepcopy(PRODUCT)
        render.validate_variants(product)
        self.assertEqual(len(product['sizeOzonUrls']), 7)
        self.assertEqual(product['sizeOzonUrls']['130 × 120 × 100'], 'https://www.ozon.ru/product/3363023459/')
        self.assertEqual(product['sizeOzonUrls']['255 × 140 × 120'], 'https://www.ozon.ru/product/2360802204/')
        html = render.hero(product)
        self.assertEqual(html.count('data-ozon-url='), 7)
        self.assertIn('data-size-market="Ozon"', html)
        self.assertIn('vendor_org_211216', html)
        del product['sizeOzonUrls']['130 × 120 × 100']
        with self.assertRaises(ValueError):
            render.validate_variants(product)

    def test_every_variant_link_matches_verified_ozon_sku(self):
        products = json.loads((render.ROOT / 'catalog/products.json').read_text())['products']
        checked = 0
        for product in products:
            if not product.get('variants'):
                continue
            for variant in product['variants']:
                source = variant['source']['ozon']
                self.assertEqual(variant['ozonUrl'], f'https://www.ozon.ru/product/{source["sku"]}/')
                checked += 1
            self.assertIn('Перейти на Ozon', render.hero(product))
            self.assertNotIn('productId', json.dumps(render.variant_data(product)))
        self.assertEqual(checked, 70)

    def test_catalogue_keeps_all_links_without_js_and_escapes_search_data(self):
        product = copy.deepcopy(PRODUCT)
        product.update(name='Чехол "особый" <пример>', catalogCategory={'id': 'tech', 'label': 'Техника'})
        html = render.catalogue([product])
        self.assertIn('id="catalog-tools" hidden', html)
        self.assertIn('data-search="', html)
        self.assertIn('&quot;особый&quot; &lt;пример&gt;', html)
        self.assertIn(f'/catalog/{product["slug"]}/', html)
        self.assertNotIn('<form', html)
        self.assertIn('aria-live="polite"', html)

    def test_colour_swatches_keep_native_radios_names_and_validate_css_values(self):
        products = json.loads((render.ROOT / 'catalog/products.json').read_text())['products']
        product = copy.deepcopy(next(p for p in products if p['slug'] == 'chehol-dlya-kolyaski'))
        html = render.variant_picker(product)
        self.assertEqual(html.count('class="color-swatch"'), 6)
        self.assertEqual(html.count('type="radio"'), 6)
        self.assertIn('aria-label="Коричневый"', html)
        product['optionGroups'][0]['values'][0]['color'] = 'red; background:url(example)'
        with self.assertRaises(ValueError):
            render.variant_picker(product)

    def test_each_configuration_contains_only_its_general_view_and_details(self):
        products = json.loads((render.ROOT / 'catalog/products.json').read_text())['products']
        for product in products:
            render.validate_galleries(product)
        moto, wheel = products[1:3]
        self.assertNotIn('moto-heat', moto['galleries']['standard']['images'])
        self.assertNotIn('moto-standard', moto['galleries']['heat']['images'])
        special = {'moto-canvas-insert', 'moto-vent', 'moto-reflector'}
        self.assertFalse(special & set(moto['galleries']['standard']['images']))
        self.assertTrue(special <= set(moto['galleries']['heat']['images']))
        self.assertNotIn('wheel-set', wheel['galleries']['one']['images'])
        self.assertNotIn('wheel-single', wheel['galleries']['four']['images'])
        # The initial server-rendered thumbnails match the default variant even without JavaScript.
        for product in (moto, wheel):
            html = render.hero(product)
            thumbnails = html.split('<div class="gallery-thumbs"', 1)[1].split('</div>', 1)[0]
            selected = render.gallery_images(product)
            self.assertEqual(thumbnails.count('class="gallery-thumb"'), len(selected))
            for image in selected:
                self.assertIn(render.e(image['alt']), thumbnails)

    def test_gallery_rejects_missing_photos_and_details_from_another_configuration(self):
        product = copy.deepcopy(json.loads((render.ROOT / 'catalog/products.json').read_text())['products'][1])
        product['galleries']['standard']['kit'] = 'moto-heat'
        with self.assertRaises(ValueError):
            render.validate_galleries(product)
        product['galleries']['standard']['kit'] = 'missing-photo'
        with self.assertRaises(ValueError):
            render.validate_galleries(product)
        product['variants'][0]['galleryId'] = 'missing-gallery'
        with self.assertRaises(ValueError):
            render.validate_variants(product)

    def test_variants_have_only_confirmed_combinations_and_distinct_links(self):
        products = json.loads((render.ROOT / 'catalog/products.json').read_text())['products']
        self.assertTrue(all(p.get('status', 'published') == 'published' for p in products[:3]))
        moto, wheel = products[1:3]
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

    def test_unconfirmed_marketplace_links_are_not_invented(self):
        product = copy.deepcopy(json.loads((render.ROOT / 'catalog/products.json').read_text())['products'][1])
        product['variants'][0]['ozonUrl'] = None
        render.validate_variants(product)
        self.assertIsNone(render.variant_data(product)[0]['ozonUrl'])
        html = render.markets(product)
        self.assertNotIn('href="None"', html)
        self.assertNotIn('<a ', html)
        self.assertIn('Узнать цену и заказать', render.hero(product))

    def test_unknown_material_coating_and_sizes_are_omitted(self):
        product = copy.deepcopy(PRODUCT)
        product.update(material='', coating='', sizes=[], facts=[], materialFacts=[])
        schema = render.product_schema(product)
        self.assertNotIn('material', schema)
        self.assertNotIn('additionalProperty', schema)
        self.assertNotIn('size', schema)
        self.assertNotIn('hero-specs', render.hero(product))

    def test_size_only_label_avoids_duplicate_product_name_and_source_metadata(self):
        product = copy.deepcopy(json.loads((render.ROOT / 'catalog/products.json').read_text())['products'][1])
        product['optionGroups'] = [g for g in product['optionGroups'] if g['id'] == 'size']
        for variant in product['variants']:
            variant['options'] = {'size': variant['options']['size']}
            variant['source'] = {'file': 'internal-source.xlsx'}
        variant = render.variant_data(product)[0]
        self.assertEqual(variant['label'], variant['sizeLabel'])
        self.assertNotIn('source', variant)

    def test_drafts_have_only_an_isolated_noindex_preview(self):
        published = copy.deepcopy(PRODUCT)
        draft = copy.deepcopy(PRODUCT)
        draft.update(slug='draft-product', status='draft', name='Черновой товар')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dist = root / 'dist'
            (root / 'catalog').mkdir()
            (root / 'catalog/products.json').write_text(json.dumps({'products':[published, draft]}))
            for image in PRODUCT['images']:
                path = dist / image['src'].lstrip('/')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'test asset')
            (dist / 'index.html').write_text('Existing homepage')
            with patch.object(render, 'ROOT', root), patch.object(render, 'DIST', dist):
                render.render()
                before = (dist / 'catalog/index.html').read_bytes()
                self.assertNotIn(b'draft-product', before)
                self.assertFalse((dist / 'catalog/draft-product').exists())
                render.render(preview=True)
            self.assertEqual(before, (dist / 'catalog/index.html').read_bytes())
            preview = root / 'outputs/catalog-preview'
            html = (preview / 'catalog/draft-product/index.html').read_text()
            self.assertIn('content="noindex,nofollow"', html)
            self.assertNotIn('src="/metrika.js', html)
            self.assertNotIn('mc.yandex.ru/watch', html)
            self.assertIn('draft-product', (preview / 'catalog/index.html').read_text())
            self.assertIn('Disallow: /', (preview / 'robots.txt').read_text())

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
        self.assertNotIn('Wildberries', html)


if __name__ == '__main__':
    unittest.main()
