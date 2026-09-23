"""Render the catalogue as static HTML; stdlib only, homepage never touched."""
import json
import sys
import re
import argparse
import shutil
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html, image_attributes, json_ld, breadcrumbs, external_url, ORIGIN
DIST = ROOT / 'dist'
BASE = Template((ROOT / 'catalog/templates/base.html').read_text())


def e(value):
    return escape(str(value), quote=True)


def size_label(size):
    return ' × '.join(map(str, size))


def lines(value):
    return e(value).replace('\n', '<br>')


def image_for(product, role):
    gallery = product.get('galleries', {}).get(default_gallery(product))
    if gallery and role in gallery:
        return image_by_id(product, gallery[role])
    return next((img for img in product['images'] if img.get('role') == role), product['images'][0])


def default_gallery(product):
    return product['variants'][0]['galleryId'] if product.get('variants') else product.get('defaultGallery', '')


def image_by_id(product, image_id):
    return next(image for image in product['images'] if image['id'] == image_id)


def gallery_images(product, gallery_id=None):
    if not product.get('galleries'):
        return product['images']
    gallery = product['galleries'][gallery_id or default_gallery(product)]
    return [image_by_id(product, image_id) for image_id in gallery['images']]


def gallery_image_data(image):
    return {**image, 'photo': image_attributes(image['src'], '(max-width:800px) 90vw, 48vw'),
            'thumbnail': image_attributes(image['src'], '76px', True)}


def gallery_data(product):
    return {key: {**gallery, 'images': [gallery_image_data(image) for image in gallery_images(product, key)],
                  'photos': {role: gallery_image_data(image_by_id(product, gallery[role])) for role in ('material', 'fit', 'kit')}}
            for key, gallery in product.get('galleries', {}).items()}


def construction_features(product, gallery):
    cards = ''.join(f'<article>{picture(image_by_id(product, item["image"]), sizes="(max-width:540px) 90vw, (max-width:1024px) 43vw, 28vw")}<h4>{e(item["title"])}</h4><p>{e(item["text"])}</p></article>' for item in gallery['features'])
    return f'<div class="construction-grid">{cards}</div>'


def construction_details(product):
    key = default_gallery(product)
    gallery = product['galleries'][key]
    templates = ''.join(f'<template data-gallery-features="{e(name)}">{construction_features(product, item)}</template>' for name, item in product['galleries'].items())
    return f'<div class="wrap construction-details"><div class="construction-heading"><h3>Рассмотрите детали.</h3><p id="construction-label">{e(gallery["label"])}</p></div><div id="construction-content">{construction_features(product, gallery)}</div>{templates}</div>'


def validate_galleries(product):
    if not product.get('galleries'):
        return
    ids = [image['id'] for image in product['images']]
    if len(ids) != len(set(ids)) or default_gallery(product) not in product['galleries']:
        raise ValueError('Invalid product gallery or duplicate image id')
    for gallery in product['galleries'].values():
        if not gallery['images'] or len(gallery['images']) != len(set(gallery['images'])):
            raise ValueError('Empty gallery or duplicate gallery image')
        references = gallery['images'] + [gallery[role] for role in ('hero', 'material', 'fit', 'kit')] + [item['image'] for item in gallery['features']]
        if not set(references) <= set(ids):
            raise ValueError('Unknown gallery image')
        if not set(references) <= set(gallery['images']) or gallery['hero'] != gallery['images'][0]:
            raise ValueError('Page details must belong to the selected gallery')


def picture(image, eager=False, sizes='(max-width:800px) 90vw, 48vw', thumbnail=False, **attrs):
    attrs = {**image_attributes(image['src'], sizes, thumbnail), **attrs}
    extra = ' '.join(f'{e(k)}="{e(v)}"' for k, v in attrs.items())
    return f'<img alt="{e(image["alt"])}" loading="{"eager" if eager else "lazy"}" decoding="async" {extra}>'


def variant_choices(product, variant):
    return [(group['label'], next(value['label'] for value in group['values']
             if value['id'] == variant['options'][group['id']])) for group in product['optionGroups']]


def variant_data(product):
    result = []
    for variant in product.get('variants', []):
        choices = variant_choices(product, variant)
        summary = ' · '.join(value for label, value in choices if label not in ('Размер', 'Объём', 'Ширина'))
        label = ' · '.join(dict.fromkeys(value for value in (summary, variant['sizeLabel']) if value))
        summary = summary or product['name']
        public_variant = {key: value for key, value in variant.items() if key != 'source'}
        result.append({**public_variant, 'summary': summary, 'label': label,
                       'context': '\n'.join(f'{label}: {value}' for label, value in choices),
                       'ozonUrl': external_url(variant['ozonUrl'], f'catalog_{product["slug"]}_{variant["id"]}') if variant.get('ozonUrl') else None})
    return result


def variant_picker(product):
    variants = variant_data(product)
    default = variants[0]
    groups = []
    for group in product['optionGroups']:
        options = ''
        swatches = group.get('display') == 'swatches'
        for value in group['values']:
            checked = ' checked' if default['options'][group['id']] == value['id'] else ''
            note = f'<small>{e(value["note"])}</small>' if value.get('note') else ''
            if swatches:
                color = value.get('color', '')
                if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                    raise ValueError('Swatch must use a six-digit hex colour')
                options += f'<label class="color-option" title="{e(value["label"])}"><input type="radio" name="option-{e(group["id"])}" data-option="{e(group["id"])}" value="{e(value["id"])}" aria-label="{e(value["label"])}"{checked}><span class="color-swatch" style="--swatch-color:{color}" aria-hidden="true"></span></label>'
            else:
                options += f'<label class="size-option"><input type="radio" name="option-{e(group["id"])}" data-option="{e(group["id"])}" value="{e(value["id"])}"{checked}><span><strong>{e(value["label"])}</strong>{note}</span></label>'
        options_class = 'color-options' if swatches else 'size-options'
        groups.append(f'<fieldset class="size-picker variant-picker"><legend>{e(group["label"])}</legend><div class="{options_class}">{options}</div></fieldset>')
    data = json.dumps(variants, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    option_note = f'<p class="option-note">{e(product["optionNote"])}</p>' if product.get('optionNote') else ''
    return ''.join(groups) + f'<p class="variant-selection type-small" id="variant-selection" role="status">Выбрано: {e(default["label"])}</p>{option_note}<script type="application/json" id="product-variants">{data}</script>'


def variant_size_table(product):
    rows = ''
    for variant in variant_data(product):
        choices = variant['summary']
        rows += f'<tr><td>{e(choices)}</td><td>{e(variant["sizeLabel"])}</td><td><button data-select-variant="{e(variant["id"])}" aria-label="Выбрать {e(choices)} — {e(variant["sizeLabel"])}">Выбрать <span aria-hidden="true">↗</span></button></td></tr>'
    return f'<table class="size-table variant-table"><caption>{e(product["copy"]["sizeTableCaption"])}</caption><thead><tr><th scope="col">{e(product.get("variantTableLabel", "Комплектация"))}</th><th scope="col">{e(product.get("variantSizeHeading", "Размер"))}</th><th scope="col"><span class="sr-only">Выбор</span></th></tr></thead><tbody>{rows}</tbody></table>'


def validate_variants(product):
    size_links = product.get('sizeOzonUrls', {})
    if size_links:
        if set(size_links) != {size_label(size) for size in product['sizes']}:
            raise ValueError('Ozon size links must match every listed size')
        if any(not re.fullmatch(r'https://www\.ozon\.ru/product/\d+/', url) for url in size_links.values()):
            raise ValueError('Size must link to its confirmed HTTPS Ozon SKU')
    if not product.get('variants'):
        return
    groups = product['optionGroups']
    allowed = {g['id']: {v['id'] for v in g['values']} for g in groups}
    if len(allowed) != len(groups) or any(len(allowed[g['id']]) != len(g['values']) for g in groups):
        raise ValueError('Duplicate option group or value')
    ids, combinations = set(), set()
    for variant in product['variants']:
        options = variant['options']
        combination = tuple(sorted(options.items()))
        if set(options) != set(allowed) or any(value not in allowed[key] for key, value in options.items()):
            raise ValueError('Unknown or missing variant option')
        if variant['id'] in ids or combination in combinations:
            raise ValueError('Duplicate variant')
        if variant.get('ozonUrl') and not variant['ozonUrl'].startswith('https://www.ozon.ru/product/'):
            raise ValueError('Variant must link to its HTTPS Ozon product')
        if variant['galleryId'] not in product.get('galleries', {}):
            raise ValueError('Invalid variant gallery')
        ids.add(variant['id'])
        combinations.add(combination)


def markets(product, compact=False):
    links = []
    for market in product['marketplaces']:
        name = e(market['name'])
        content = f'Перейти на {name}<span aria-hidden="true">↗</span>'
        url = variant_data(product)[0]['ozonUrl'] if product.get('variants') and market['name'] == 'Ozon' else market['url']
        if url:
            if not url.startswith('https://'):
                raise ValueError('Marketplace links must use HTTPS')
            marker = ' data-variant-market="Ozon"' if product.get('variants') and not compact and market['name'] == 'Ozon' else ''
            if product.get('sizeOzonUrls') and not compact and market['name'] == 'Ozon':
                marker = ' data-size-market="Ozon"'
            links.append(f'<a class="market-button"{marker} href="{e(url)}" target="_blank" rel="noopener noreferrer">{content}</a>')
        # An unavailable marketplace is not an actionable purchase route.
    return f'<div class="marketplaces{" compact" if compact else ""}">{"".join(links)}</div>'


def shell(content, title, description, product_name='', catalog_current='false', product_slug='', structured=None, unit_label='Чехлов', source_images=False):
    if structured:
        content += json_ld(structured)
    trail = [('Главная', '/'), ('Каталог', '/catalog/')]
    if product_slug:
        trail.append((product_name, f'/catalog/{product_slug}/'))
    content += json_ld(breadcrumbs(trail))
    return prepare_html(BASE.substitute(content=content, title=e(title), description=e(description),
                           product_name=e(product_name), product_slug=e(product_slug), unit_label=e(unit_label), source_images=str(source_images).lower(), catalog_current=catalog_current, dialogs=dialogs()), 'catalog/' + (product_slug + '/' if product_slug else '') + 'index.html')


def dialogs():
    return '''<dialog class="catalog-dialog request-dialog" id="request-dialog" aria-labelledby="request-title"><button class="dialog-close" data-close aria-label="Закрыть заявку">×</button><p class="eyebrow">НАПРЯМУЮ С ПРОИЗВОДСТВОМ</p><h2 id="request-title">Обсудим ваш заказ<span class="title-dot">.</span></h2><p class="request-context" id="request-context"></p><p class="request-description">Оставьте контакт — обсудим размер, количество и условия заказа.</p>
      <form id="catalog-request" class="ym-hide-content"><input name="website" tabindex="-1" autocomplete="off" hidden aria-hidden="true"><label>Ваше имя<input name="name" autocomplete="name" placeholder="Как к вам обращаться" required maxlength="100"></label><label>Телефон или email<input name="contact" autocomplete="off" placeholder="+7 или example@mail.ru" required maxlength="150" aria-describedby="contact-error"></label><p class="field-error" id="contact-error" hidden></p><div class="request-fields"><label>Тип обращения<select name="intent"><option value="direct">Заказ напрямую</option><option value="sizing">Подбор размера</option><option value="wholesale">Партия для бизнеса</option></select></label><label>Количество, шт.<input name="quantity" type="number" min="1" max="1000000" step="1" placeholder="Например, 10"></label></div><label>Расскажите о задаче<textarea name="question" rows="3" maxlength="2000" placeholder="Модель техники, габариты, нужные размеры и ваши вопросы"></textarea></label><label class="consent"><input type="checkbox" name="consent" required><span>Принимаю <a href="/user-agreement.html" target="_blank" rel="noopener">Пользовательское соглашение</a> и даю согласие на обработку данных согласно <a href="/privacy-policy.html" target="_blank" rel="noopener">Политике</a>.</span></label><button class="button accent" type="submit">Отправить заявку <span aria-hidden="true">↗</span></button><p class="request-result" id="request-result" role="status" hidden></p></form>
    </dialog>'''


def hero(product):
    gallery = gallery_images(product)
    gallery_id = default_gallery(product)
    gallery_label = f'<p class="gallery-model" id="gallery-model">{e(product["galleries"][gallery_id]["label"])}</p>' if gallery_id else ''
    galleries = json.dumps(gallery_data(product), ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    gallery_config = f'<script type="application/json" id="product-galleries" data-default-gallery="{e(gallery_id)}">{galleries}</script>' if gallery_id else ''
    thumbnails = ''.join(f'<button class="gallery-thumb" data-gallery-src="{e(image_attributes(img["src"])["src"])}" data-gallery-srcset="{e(image_attributes(img["src"]).get("srcset", ""))}" data-gallery-alt="{e(img["alt"])}" data-gallery-label="{e(img["label"])}" aria-pressed="{"true" if i == 0 else "false"}" aria-label="{e(img["label"])}">{picture(img, sizes="76px", thumbnail=True)}</button>' for i, img in enumerate(gallery))
    sizes = ''
    for i, size in enumerate(product['sizes']):
        label = size_label(size)
        url = product.get('sizeOzonUrls', {}).get(label)
        market = f' data-ozon-url="{e(external_url(url, "catalog_" + product["slug"] + "_size_" + str(i+1)))}"' if url else ''
        checked = ' checked' if i == 0 and url else ''
        sizes += f'<label class="size-option"><input type="radio" name="product-size" value="{label}"{market}{checked}><span>{label}</span></label>'
    picker = variant_picker(product) if product.get('variants') else f'<fieldset class="size-picker"><legend>Размер, см <span>Д × Ш × В</span></legend><div class="size-options">{sizes}</div></fieldset>'
    note = f'<p class="seasonal-note">{e(product["seasonalNote"])}</p>' if product['seasonalNote'] else ''
    size_help = '<a class="size-help" href="#sizes">Как подобрать размер <span aria-hidden="true">↙</span></a>' if 'sizes' in product['sections'] else '<button class="text-link size-help" data-request="Подбор размера">Помогите подобрать размер ↗</button>'
    retail = markets(product)
    has_retail = 'href=' in retail
    purchase_note = 'Розничная цена, наличие и доставка — на Ozon.' if has_retail else 'Нужен один товар? Уточните цену, доступное количество и доставку у менеджера.'
    facts = product.get('facts', [{'label': 'Материал', 'value': product['material']}, {'label': 'Влагозащитная пропитка', 'value': product['coating']}])
    specs = ''.join(f'<div><span>{e(fact["label"])}</span><strong>{e(fact["value"])}</strong></div>' for fact in facts if fact['value'])
    hero_specs = f'<div class="hero-specs">{specs}</div>' if specs else ''
    return f'''
    <nav class="wrap breadcrumbs" aria-label="Хлебные крошки"><a href="/">Главная</a><span aria-hidden="true">/</span><a href="/catalog/">Каталог</a><span aria-hidden="true">/</span><span>{e(product['name'])}</span></nav>
    <section class="wrap detail-hero" aria-labelledby="product-title">
      <div class="detail-heading"><p class="eyebrow">NEEDLE SHARK / {e(product['category']).upper()}</p><h1 id="product-title">{e(product['name'])}</h1><p class="detail-intro">{e(product['description'])}</p>{note}</div>
      <div class="gallery">{gallery_label}{gallery_config}
        <div class="gallery-stage"><span class="product-badge">{e(product['badge'])}</span>{picture(gallery[0], True, id='gallery-image', fetchpriority='high')}<span class="photo-index" id="photo-index">01 / {len(gallery):02d}</span></div>
        <div class="gallery-bottom"><div class="gallery-thumbs" aria-label="Фотографии товара">{thumbnails}</div><p id="gallery-caption">{e(gallery[0]['label'])}</p></div>
      </div>
      <div class="detail-copy">
        {hero_specs}
        {picker}
        {size_help}
        {'<button class="text-link custom-length-request" data-request="Свой метраж">Обсудить свой метраж →</button>' if product['slug'] == 'stropa-remennaya' else ''}
        <div class="buy-block"><p class="buy-label">Заказать у производства</p><button class="button accent request-primary" data-request="Партия для бизнеса">Получить расчёт партии <span aria-hidden="true">↗</span></button><p class="direct-note">Готовые изделия — партиями от 20 штук.<br>Другая конструкция или объём — по согласованию.</p><div class="retail-buy">{retail if has_retail else '<button class="button retail-request" data-request="Заказ напрямую">Узнать цену и заказать <span aria-hidden="true">↗</span></button>'}<p class="price-note">{purchase_note}</p></div><a class="business-terms" href="/business/">Условия работы с бизнесом →</a></div>
      </div>
    </section>'''


def detail_sections(product):
    copy = product['copy']
    scenarios = ''.join(f'<article class="scenario"><span class="scenario-number">0{i+1}</span><p class="scenario-tag">{e(s["tag"])}</p><h3>{e(s["title"])}</h3><p>{e(s["text"])}</p></article>' for i, s in enumerate(product['scenarios']))
    hints = {size_label(item['size']): item for item in product.get('sizeGuidance', [])}
    size_rows = ''
    for i, size in enumerate(product['sizes']):
        size_rows += f'<tr class="size-values"><td>{i+1:02d}</td>{"".join(f"<td>{n}</td>" for n in size)}<td><button data-select-size="{size_label(size)}" aria-label="Выбрать размер {size_label(size)} см">Выбрать <span aria-hidden="true">↗</span></button></td></tr>'
        if hint := hints.get(size_label(size)):
            size_rows += f'<tr class="size-guidance"><td colspan="5"><strong>{e(hint["label"])}</strong><span>{e(hint["note"])}</span></td></tr>'
    fastenings = ''.join(f'<article><span>0{i+1}</span><div><h3>{e(item["title"])}</h3><p>{e(item["text"])}</p></div></article>' for i, item in enumerate(product.get('fastenings', [])))
    faqs = ''.join(f'<details><summary>{e(item["question"])}<span aria-hidden="true">+</span></summary><p>{e(item["answer"])}</p></details>' for item in product['faq'])
    active_gallery = product.get('galleries', {}).get(default_gallery(product), {})
    material_text = active_gallery.get('materialText', product['materialText'])
    material_facts = product.get('materialFacts', [{'label': 'Ткань', 'value': product['material']}, {'label': 'Влагозащитная пропитка', 'value': product['coating']}, {'label': 'Цвет', 'value': product['color']}])
    material_specs = ''.join(f'<div><dt>{e(fact["label"])}</dt><dd>{e(fact["value"])}</dd></div>' for fact in material_facts if fact['value'])
    kit = ''.join(f'<li><span>0{i+1}</span>{e(item)}</li>' for i, item in enumerate(product['kit']))
    sections = {
        'scenarios': f'''<section class="wrap product-section" id="scenarios"><div class="section-heading"><div><p class="eyebrow">СЦЕНАРИИ ИСПОЛЬЗОВАНИЯ</p><h2>{lines(copy['scenariosTitle'])}</h2></div><p>{lines(copy['scenariosIntro'])}</p></div><div class="scenario-grid">{scenarios}</div></section>''',
        'material': f'''<section class="material-section" id="material"><div class="wrap material-layout"><div class="material-copy"><p class="eyebrow">МАТЕРИАЛ</p><h2>{lines(copy['materialTitle'])}</h2><p id="material-description">{e(material_text)}</p><dl class="material-specs">{material_specs}</dl></div><figure class="material-photo">{picture(image_for(product, 'material'), **{'data-product-photo': 'material'})}<figcaption id="material-caption">{e(active_gallery.get('materialCaption', copy['materialCaption']))}</figcaption></figure></div></section>''',
        'sizes': f'''<section class="wrap product-section sizes-section" id="sizes"><div class="section-heading"><div><p class="eyebrow">ПОДБОР РАЗМЕРА</p><h2>{lines(copy['sizesTitle'])}</h2></div><p>{lines(copy['sizesIntro'])}</p></div><div class="sizes-layout"><div><div class="fit-photo">{picture(image_for(product, 'fit'), **{'data-product-photo': 'fit'})}<span>Длина × ширина × высота</span></div><p class="fit-note">{e(product['fitNote'])}</p><button class="text-link size-request" data-request="Подбор размера">Помогите выбрать размер <span aria-hidden="true">↗</span></button></div><div class="size-table-wrap"><table class="size-table"><caption>{e(copy['sizeTableCaption'])}</caption><thead><tr><th scope="col">№</th><th scope="col">Длина</th><th scope="col">Ширина</th><th scope="col">Высота</th><th scope="col"><span class="sr-only">Выбор</span></th></tr></thead><tbody>{size_rows}</tbody></table><p class="selected-size-note" id="selected-size-note" role="status">Выберите размер — он появится в вашей заявке.</p><button class="button accent" data-request="Заказ напрямую">Оставить заявку <span aria-hidden="true">↗</span></button></div></div></section>''',
        'kit': f'''<section class="kit-section" id="kit"><div class="wrap kit-layout"><div class="kit-photo">{picture(image_for(product, 'kit') if active_gallery else image_for(product, 'hero'), **{'data-product-photo': 'kit'})}</div><div class="kit-copy"><p class="eyebrow">КОМПЛЕКТАЦИЯ</p><h2>{lines(copy['kitTitle'])}</h2><p>{e(copy['kitDescription'])}</p><ul>{kit}</ul></div></div></section>''',
        'questions': f'''<section class="wrap product-section faq-section" id="questions"><div><p class="eyebrow">ВОПРОСЫ ОБ ИЗДЕЛИИ</p><h2>{lines(copy['faqTitle'])}</h2><p>{lines(copy['faqIntro'])}</p><button class="text-link" data-request="Подбор размера">Задать вопрос <span aria-hidden="true">↗</span></button></div><div class="faq-list">{faqs}</div></section>''',
        'wholesale': f'''<section class="wholesale-section" id="wholesale"><div class="wrap wholesale-layout"><div><p class="eyebrow">ДЛЯ БИЗНЕСА</p><h2>{lines(copy['wholesaleTitle'])}</h2></div><div><p>{e(copy['wholesaleDescription'])}</p><button class="button accent" data-request="Партия для бизнеса">Получить расчёт партии <span aria-hidden="true">↗</span></button><a href="/business/">Условия для бизнеса →</a></div></div></section>'''
    }
    labels = dict(zip(sections, ['Когда пригодится', 'Материал', 'Размеры', 'Комплектация', 'Вопросы', 'Для бизнеса']))
    if product.get('galleries') and any(gallery['features'] for gallery in product['galleries'].values()):
        sections['material'] = sections['material'].replace('</section>', construction_details(product) + '</section>')
    elif fastenings:
        sections['material'] = sections['material'].replace('</section>', f'<div class="wrap fastening-details"><h3>Детали, которые держат.</h3><div>{fastenings}</div></div></section>')
    if product.get('variants'):
        sections['sizes'] = re.sub(r'<table class="size-table">.*?</table>', lambda _: variant_size_table(product), sections['sizes'], flags=re.S)
        sections['sizes'] = sections['sizes'].replace('Длина × ширина × высота', e(product.get('measurementLabel', 'Длина × ширина × высота')))
        sections['kit'] = sections['kit'].replace(f'<ul>{kit}</ul>', f'<ul id="variant-kit">{kit}</ul>')
        default = variant_data(product)[0]
        sections['kit'] = sections['kit'].replace('<ul id="variant-kit">', f'<p class="kit-configuration" id="kit-configuration">{e(default["label"])}</p><ul id="variant-kit">')
    enabled = product['sections']
    if len(enabled) != len(set(enabled)) or any(key not in sections for key in enabled):
        raise ValueError('Unknown or duplicate product section')
    nav = ''.join(f'<a href="#{key}">{labels[key]}</a>' for key in enabled)
    body = ''.join(sections[key].replace('<p class="eyebrow">', f'<p class="eyebrow">{i+1:02d} / ', 1) for i, key in enumerate(enabled))
    return f'<nav class="product-nav" aria-label="Разделы страницы товара"><div class="wrap">{nav}</div></nav>{body}<div class="wrap back-to-catalog"><a href="/catalog/">← Вернуться в каталог</a><span>NEEDLE SHARK / С ТОЧНОСТЬЮ ДО НИТКИ</span></div>'


def catalogue(products):
    visible = sorted((p for p in products if p['visible']), key=lambda p: p['order'])
    categories = {}
    cards = []
    for product in visible:
        category = product.get('catalogCategory', {'id': product['category'], 'label': product['category']})
        bucket = categories.setdefault(category['id'], {'label': category['label'], 'count': 0})
        bucket['count'] += 1
        search_parts = [product['name'], product['description'], product['category'], category['label'],
                        product.get('material', ''), product.get('color', ''), *product.get('searchTerms', [])]
        search_parts.extend(v['id'] + ' ' + v.get('sizeLabel', '') for v in product.get('variants', []))
        search_parts.extend(v['label'] for g in product.get('optionGroups', []) for v in g['values'])
        url = f'/catalog/{product["slug"]}/'
        source_flag = ' data-source-images="true"' if product.get('sourcePhotography') else ''
        summary = product.get('catalogSummary', product.get('rangeLabel', product['material']))
        has_market = any(m.get('url') for m in product['marketplaces'])
        route = 'Розница на Ozon · партии у производства' if has_market else 'Цена и условия — по запросу'
        cards.append(f'''<article class="catalog-card" data-category="{e(category['id'])}" data-search="{e(' '.join(search_parts))}"{source_flag}><a class="catalog-card-image" href="{url}" aria-label="{e(product['name'])} — подробнее">{picture(product['images'][0], len(cards) < 4, sizes='(max-width:540px) 120px, (max-width:1000px) 44vw, (max-width:1279px) 29vw, 22vw')}<span class="card-open" aria-hidden="true">↗</span></a><div class="card-meta"><span>{e(category['label'])}</span></div><h2><a href="{url}">{e(product['name'])}</a></h2><p class="card-spec">{e(summary)}</p><p class="card-route">{route}</p><a class="card-detail-link" href="{url}">Выбрать и заказать <span aria-hidden="true">→</span></a></article>''')
    category_buttons = f'<button type="button" data-category-filter="" data-category-label="Все категории" aria-pressed="true" aria-controls="catalog-grid" data-track="catalog_category_all">Все изделия <span>{len(cards)}</span></button>'
    category_buttons += ''.join(f'<button type="button" data-category-filter="{e(key)}" data-category-label="{e(value["label"])}" aria-pressed="false" aria-controls="catalog-grid" data-track="catalog_category_{e(key)}">{e(value["label"])} <span>{value["count"]}</span></button>' for key, value in categories.items())
    controls = f'''<div class="catalog-tools" id="catalog-tools" hidden><div class="catalog-search" role="search" aria-label="Поиск по каталогу"><label class="sr-only" for="catalog-search">Найти изделие</label><div class="catalog-search-field"><svg aria-hidden="true" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><input id="catalog-search" class="ym-disable-keys" type="search" placeholder="Название, размер или артикул" maxlength="150" autocomplete="off" aria-controls="catalog-grid" aria-describedby="catalog-results"></div></div><details class="category-picker" id="category-picker" open><summary><span id="category-label">Все категории</span><span aria-hidden="true">⌄</span></summary><div class="catalog-categories" role="group" aria-label="Категории товаров">{category_buttons}</div></details><button type="button" class="catalog-reset text-link" id="catalog-reset" hidden>Сбросить поиск и категорию <span aria-hidden="true">×</span></button></div>'''
    return f'''<nav class="wrap breadcrumbs" aria-label="Хлебные крошки"><a href="/">Главная</a><span aria-hidden="true">/</span><span>Каталог</span></nav><section class="wrap catalog-intro"><div><h1>Каталог изделий<span class="title-dot">.</span></h1><p>Для себя и для бизнеса. Выберите вариант и способ заказа.</p></div><a class="catalog-b2b-link" href="/business/"><span>Для вашего бизнеса</span><strong>Партии и пошив на заказ ↗</strong><span>Готовые изделия — от 20 штук</span></a></section><section class="wrap catalog-collection" aria-labelledby="catalog-heading"><div class="collection-heading"><h2 id="catalog-heading" class="sr-only">Найдите своё изделие</h2><span id="catalog-results" role="status" aria-live="polite" aria-atomic="true">{len(cards)} из {len(cards)} изделий</span></div>{controls}<div class="catalog-empty" id="catalog-empty" hidden><h3>Ничего не найдено</h3><p>Попробуйте другое название или сбросьте категорию. Нужна помощь? <a href="/business/#contact">Расскажите о задаче</a>.</p></div><div class="catalog-grid" id="catalog-grid">{''.join(cards)}</div></section><section class="wrap catalogue-business"><div><p class="eyebrow">ПОШИВ ПОД ВАШУ ЗАДАЧУ</p><h2>Нужна другая<br>конструкция?</h2></div><div><p>Начнём с фотографии, образца или описания. Разработку, количество и сроки согласуем с вами.</p><a class="button accent" href="/business/#contact">Обсудить своё изделие <span aria-hidden="true">↗</span></a></div></section>'''


def product_schema(product):
    url = ORIGIN + '/catalog/' + product['slug'] + '/'
    # Descriptive Product only. No invented price, availability, SKU or borrowed shop rating.
    schema = {'@context': 'https://schema.org', '@type': 'Product', '@id': url + '#product',
            'url': url, 'name': product['name'], 'description': product['description'],
            'image': [ORIGIN + image_attributes(img['src'])['src'] for img in product['images']],
            'brand': {'@type': 'Brand', 'name': 'Needle Shark'},
            'manufacturer': {'@id': ORIGIN + '/#organization'},
            'mainEntityOfPage': {'@id': url + '#webpage'},
            'material': product['material'], 'color': product['color'],
            'category': product['category'],
            'size': list(dict.fromkeys(v['sizeLabel'] for v in product['variants'] if v['sizeLabel'])) if product.get('variants') else [size_label(size) + ' см (Д × Ш × В)' for size in product['sizes']],
            'additionalProperty': [{'@type': 'PropertyValue', 'name': 'Влагозащитная пропитка', 'value': product['coating']}]}
    for field in ('material', 'color', 'size'):
        if not schema[field]:
            del schema[field]
    if not product['coating']:
        del schema['additionalProperty']
    return schema


def render(preview=False):
    products = json.loads((ROOT / 'catalog/products.json').read_text())['products']
    if any(p.get('status', 'published') not in ('draft', 'published') for p in products):
        raise ValueError('Unknown product status')
    products = [p for p in products if preview or p.get('status', 'published') == 'published']
    output = ROOT / 'outputs/catalog-preview' if preview else DIST
    if preview:
        shutil.copytree(DIST, output, dirs_exist_ok=True)
    slugs = set()
    for product in products:
        validate_variants(product)
        validate_galleries(product)
        slug = product['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in slugs:
            raise ValueError(f'Invalid or duplicate slug: {slug}')
        slugs.add(slug)
        for img in product['images']:
            if not (DIST / img['src'].lstrip('/')).is_file():
                raise ValueError(f'Missing image: {img["src"]}')
        page_dir = output / 'catalog' / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        title = product.get('seoTitle', f'{product["name"]} — {product["material"]}, {len(product["sizes"])} размеров | Needle Shark')
        html = shell(hero(product) + detail_sections(product), title, product['seoDescription'], product['name'], product_slug=slug, structured=product_schema(product), unit_label=product.get('unitLabel', 'Чехлов'), source_images=product.get('sourcePhotography', False))
        (page_dir / 'index.html').write_text(html)
    visible = sorted((p for p in products if p['visible']), key=lambda p: p['order'])
    collection = {'@context': 'https://schema.org', '@type': 'CollectionPage',
                  '@id': ORIGIN + '/catalog/#webpage', 'name': 'Каталог изделий Needle Shark',
                  'mainEntity': {'@type': 'ItemList', 'itemListElement': [
                      {'@type': 'ListItem', 'position': i + 1, 'name': p['name'],
                       'url': ORIGIN + '/catalog/' + p['slug'] + '/'} for i, p in enumerate(visible)]}}
    description = 'Каталог Needle Shark: чехлы, сумки, ремни, текстильные аксессуары и материалы. Выбор размера и комплектации, розничный заказ и партии для бизнеса.'
    if preview:
        description = 'Каталог Needle Shark: чехлы, сумки, ремни и текстильные аксессуары. Размеры, цвета, комплектации и заказ напрямую.'
    (output / 'catalog/index.html').write_text(shell(catalogue(products), 'Каталог чехлов и изделий из технических тканей | Needle Shark', description, catalog_current='page', structured=collection))
    if preview:
        for page in output.rglob('*.html'):
            html = re.sub(r'<meta name="robots"[^>]*>', '<meta name="robots" content="noindex,nofollow">', page.read_text())
            # Local reviews must not send pageviews or noscript pixels to production analytics.
            html = re.sub(r'<script src="/metrika\.js[^\"]*"[^>]*></script>', '', html)
            html = re.sub(r'<noscript>.*?</noscript>', '', html, flags=re.S)
            page.write_text(html)
        (output / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    print(f'Rendered catalogue and {len(products)} product page(s) in {output}. Homepage source unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='Include drafts in an isolated, noindex local preview')
    render(preview=parser.parse_args().preview)
