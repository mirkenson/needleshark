"""Render the catalogue as static HTML; stdlib only, homepage never touched."""
import json
import sys
import re
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html
DIST = ROOT / 'dist'
BASE = Template((ROOT / 'catalog/templates/base.html').read_text())


def e(value):
    return escape(str(value), quote=True)


def size_label(size):
    return ' × '.join(map(str, size))


def lines(value):
    return e(value).replace('\n', '<br>')


def image_for(product, role):
    return next((img for img in product['images'] if img.get('role') == role), product['images'][0])


def picture(image, eager=False, **attrs):
    extra = ' '.join(f'{e(k)}="{e(v)}"' for k, v in attrs.items())
    return f'<img src="{e(image["src"])}" alt="{e(image["alt"])}" width="1536" height="1024" loading="{"eager" if eager else "lazy"}" {extra}>'


def markets(product, compact=False):
    links = []
    for market in product['marketplaces']:
        name = e(market['name'])
        content = f'{name}<span aria-hidden="true">↗</span>'
        if market['url']:
            if not market['url'].startswith('https://'):
                raise ValueError('Marketplace links must use HTTPS')
            links.append(f'<a class="market-button" href="{e(market["url"])}" target="_blank" rel="noopener noreferrer">{content}</a>')
        else:
            links.append(f'<button class="market-button" type="button" disabled aria-label="{name}: покупка пока недоступна">{name}<small>Пока недоступно</small></button>')
    return f'<div class="marketplaces{" compact" if compact else ""}">{"".join(links)}</div>'


def shell(content, title, description, product_name='', catalog_current='false', product_slug=''):
    return prepare_html(BASE.substitute(content=content, title=e(title), description=e(description),
                           product_name=e(product_name), product_slug=e(product_slug), catalog_current=catalog_current, dialogs=dialogs()), 'catalog/' + (product_slug + '/' if product_slug else '') + 'index.html')


def dialogs():
    return '''<dialog class="catalog-dialog request-dialog" id="request-dialog" aria-labelledby="request-title"><button class="dialog-close" data-close aria-label="Закрыть заявку">×</button><p class="eyebrow">НАПРЯМУЮ С ПРОИЗВОДСТВОМ</p><h2 id="request-title">Обсудим ваш заказ<span class="title-dot">.</span></h2><p class="request-context" id="request-context"></p><p class="request-description">Оставьте контакт — обсудим размер, количество и условия заказа.</p>
      <form id="catalog-request" class="ym-hide-content"><input name="website" tabindex="-1" autocomplete="off" hidden aria-hidden="true"><label>Ваше имя<input name="name" autocomplete="name" placeholder="Как к вам обращаться" required maxlength="100"></label><label>Телефон или email<input name="contact" autocomplete="off" placeholder="+7 или example@mail.ru" required maxlength="150" aria-describedby="contact-error"></label><p class="field-error" id="contact-error" hidden></p><div class="request-fields"><label>Тип обращения<select name="intent"><option value="direct">Заказ напрямую</option><option value="sizing">Подбор размера</option><option value="wholesale">Партия для бизнеса</option></select></label><label>Количество, шт.<input name="quantity" type="number" min="1" max="1000000" step="1" placeholder="Например, 10"></label></div><label>Расскажите о задаче<textarea name="question" rows="3" maxlength="2000" placeholder="Модель техники, габариты, нужные размеры и ваши вопросы"></textarea></label><label class="consent"><input type="checkbox" name="consent" required><span>Принимаю <a href="/user-agreement.html" target="_blank" rel="noopener">Пользовательское соглашение</a> и даю согласие на обработку данных согласно <a href="/privacy-policy.html" target="_blank" rel="noopener">Политике</a>.</span></label><button class="button accent" type="submit">Отправить заявку <span aria-hidden="true">↗</span></button><p class="request-result" id="request-result" role="status" hidden></p></form>
    </dialog>'''


def hero(product):
    gallery = product['images']
    thumbnails = ''.join(f'<button class="gallery-thumb" data-gallery-src="{e(img["src"])}" data-gallery-alt="{e(img["alt"])}" data-gallery-label="{e(img["label"])}" aria-pressed="{"true" if i == 0 else "false"}" aria-label="{e(img["label"])}">{picture(img)}</button>' for i, img in enumerate(gallery))
    sizes = ''.join(f'<label class="size-option"><input type="radio" name="product-size" value="{size_label(s)}"><span>{size_label(s)}</span></label>' for s in product['sizes'])
    note = f'<p class="seasonal-note">{e(product["seasonalNote"])}</p>' if product['seasonalNote'] else ''
    size_help = '<a class="size-help" href="#sizes">Как подобрать размер <span aria-hidden="true">↙</span></a>' if 'sizes' in product['sections'] else '<button class="text-link size-help" data-request="Подбор размера">Помогите подобрать размер ↗</button>'
    purchase_note = "Цена и доставка — на выбранном маркетплейсе." if any(m["url"] for m in product["marketplaces"]) else "Переходы на маркетплейсы временно недоступны. Заказать можно напрямую — оставьте заявку ниже."
    return f'''
    <div class="wrap breadcrumbs"><a href="/">Главная</a><span aria-hidden="true">/</span><a href="/catalog/">Каталог</a><span aria-hidden="true">/</span><span>{e(product['name'])}</span></div>
    <section class="wrap detail-hero" aria-labelledby="product-title">
      <div class="gallery">
        <div class="gallery-stage"><span class="product-badge">{e(product['badge'])}</span>{picture(gallery[0], True, id='gallery-image', fetchpriority='high')}<span class="photo-index" id="photo-index">01 / {len(gallery):02d}</span></div>
        <div class="gallery-bottom"><div class="gallery-thumbs" aria-label="Фотографии товара">{thumbnails}</div><p id="gallery-caption">{e(gallery[0]['label'])}</p></div>
      </div>
      <div class="detail-copy"><p class="eyebrow">NEEDLE SHARK / {e(product['category']).upper()}</p><h1 id="product-title">{e(product['name'])}<span class="title-dot">.</span></h1><p class="detail-intro">{e(product['description'])}</p>{note}
        <div class="hero-specs"><div><span>Материал</span><strong>{e(product['material'])}</strong></div><div><span>Влагозащитная пропитка</span><strong>{e(product['coating'])}</strong></div></div>
        <fieldset class="size-picker"><legend>Размер, см <span>Д × Ш × В</span></legend><div class="size-options">{sizes}</div></fieldset>
        {size_help}
        <div class="buy-block"><p class="buy-label">Способы заказа</p>{markets(product)}<p class="price-note">{purchase_note}</p><button class="button accent request-primary" data-request="Заказ напрямую">Оставить заявку <span aria-hidden="true">↗</span></button><p class="direct-note">Заказ напрямую · подбор размера · партии для бизнеса</p></div>
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
    kit = ''.join(f'<li><span>0{i+1}</span>{e(item)}</li>' for i, item in enumerate(product['kit']))
    sections = {
        'scenarios': f'''<section class="wrap product-section" id="scenarios"><div class="section-heading"><div><p class="eyebrow">СЦЕНАРИИ ИСПОЛЬЗОВАНИЯ</p><h2>{lines(copy['scenariosTitle'])}</h2></div><p>{lines(copy['scenariosIntro'])}</p></div><div class="scenario-grid">{scenarios}</div></section>''',
        'material': f'''<section class="material-section" id="material"><div class="wrap material-layout"><div class="material-copy"><p class="eyebrow">МАТЕРИАЛ</p><h2>{lines(copy['materialTitle'])}</h2><p>{e(product['materialText'])}</p><dl class="material-specs"><div><dt>Ткань</dt><dd>{e(product['material'])}</dd></div><div><dt>Влагозащитная пропитка</dt><dd>{e(product['coating'])}</dd></div><div><dt>Цвет</dt><dd>{e(product['color'])}</dd></div></dl></div><figure class="material-photo">{picture(image_for(product, 'material'))}<figcaption>{e(copy['materialCaption'])}</figcaption></figure></div></section>''',
        'sizes': f'''<section class="wrap product-section sizes-section" id="sizes"><div class="section-heading"><div><p class="eyebrow">ПОДБОР РАЗМЕРА</p><h2>{lines(copy['sizesTitle'])}</h2></div><p>{lines(copy['sizesIntro'])}</p></div><div class="sizes-layout"><div><div class="fit-photo">{picture(image_for(product, 'fit'))}<span>Длина × ширина × высота</span></div><p class="fit-note">{e(product['fitNote'])}</p><button class="text-link size-request" data-request="Подбор размера">Помогите выбрать размер <span aria-hidden="true">↗</span></button></div><div class="size-table-wrap"><table class="size-table"><caption>{e(copy['sizeTableCaption'])}</caption><thead><tr><th scope="col">№</th><th scope="col">Длина</th><th scope="col">Ширина</th><th scope="col">Высота</th><th scope="col"><span class="sr-only">Выбор</span></th></tr></thead><tbody>{size_rows}</tbody></table><p class="selected-size-note" id="selected-size-note" role="status">Выберите размер — он появится в вашей заявке.</p><button class="button accent" data-request="Заказ напрямую">Оставить заявку <span aria-hidden="true">↗</span></button></div></div></section>''',
        'kit': f'''<section class="kit-section" id="kit"><div class="wrap kit-layout"><div class="kit-photo">{picture(image_for(product, 'hero'))}</div><div class="kit-copy"><p class="eyebrow">КОМПЛЕКТАЦИЯ</p><h2>{lines(copy['kitTitle'])}</h2><p>{e(copy['kitDescription'])}</p><ul>{kit}</ul></div></div></section>''',
        'questions': f'''<section class="wrap product-section faq-section" id="questions"><div><p class="eyebrow">ВОПРОСЫ ОБ ИЗДЕЛИИ</p><h2>{lines(copy['faqTitle'])}</h2><p>{lines(copy['faqIntro'])}</p><button class="text-link" data-request="Подбор размера">Задать вопрос <span aria-hidden="true">↗</span></button></div><div class="faq-list">{faqs}</div></section>''',
        'wholesale': f'''<section class="wholesale-section" id="wholesale"><div class="wrap wholesale-layout"><div><p class="eyebrow">ДЛЯ БИЗНЕСА</p><h2>{lines(copy['wholesaleTitle'])}</h2></div><div><p>{e(copy['wholesaleDescription'])}</p><button class="button accent" data-request="Партия для бизнеса">Обсудить партию <span aria-hidden="true">↗</span></button><a href="/#about">Узнать о производстве →</a></div></div></section>'''
    }
    labels = dict(zip(sections, ['Когда пригодится', 'Материал', 'Размеры', 'Комплектация', 'Вопросы', 'Для бизнеса']))
    if fastenings:
        sections['material'] = sections['material'].replace('</section>', f'<div class="wrap fastening-details"><h3>Детали, которые держат.</h3><div>{fastenings}</div></div></section>')
    enabled = product['sections']
    if len(enabled) != len(set(enabled)) or any(key not in sections for key in enabled):
        raise ValueError('Unknown or duplicate product section')
    nav = ''.join(f'<a href="#{key}">{labels[key]}</a>' for key in enabled)
    body = ''.join(sections[key].replace('<p class="eyebrow">', f'<p class="eyebrow">{i+1:02d} / ', 1) for i, key in enumerate(enabled))
    return f'<nav class="product-nav" aria-label="Разделы страницы товара"><div class="wrap">{nav}</div></nav>{body}<div class="wrap back-to-catalog"><a href="/catalog/">← Вернуться в каталог</a><span>NEEDLE SHARK / С ТОЧНОСТЬЮ ДО НИТКИ</span></div>'


def catalogue(products):
    cards = []
    for product in sorted(products, key=lambda p: p['order']):
        if not product['visible']:
            continue
        url = f'/catalog/{product["slug"]}/'
        cards.append(f'''<article class="catalog-card"><a class="catalog-card-image" href="{url}" aria-label="{e(product['name'])} — подробнее">{picture(product['images'][0], True)}<span class="product-badge">{e(product['badge'])}</span><span class="card-open" aria-hidden="true">↗</span></a><div class="card-meta"><span>{e(product['material'])} / {e(product['coating'])}</span><span>{len(product['sizes'])} размеров</span></div><h2><a href="{url}">{e(product['name'])}</a></h2><p>{e(product['shortDescription'])}</p><a class="card-detail-link" href="{url}">Подробнее об изделии <span aria-hidden="true">→</span></a><div class="card-buy"><span>На маркетплейсах</span>{markets(product, True)}</div></article>''')
    return f'''<div class="wrap breadcrumbs"><a href="/">Главная</a><span aria-hidden="true">/</span><span>Каталог</span></div><section class="wrap catalog-intro"><div><p class="eyebrow">NEEDLE SHARK / ГОТОВЫЕ ИЗДЕЛИЯ</p><h1>Защита в каждой<br><span class="accent-word">детали.</span></h1></div><p>Изделия из технических тканей.<br>Выбирайте для себя или заказывайте<br class="desktop-break"> партию напрямую у производства.</p></section><section class="wrap catalog-collection" aria-labelledby="catalog-heading"><div class="collection-heading"><h2 id="catalog-heading">Каталог изделий</h2><span>{len(cards):02d} / {"изделие" if len(cards) == 1 else "изделий"}</span></div><div class="catalog-grid">{''.join(cards)}</div></section><section class="wrap catalogue-business"><div><p class="eyebrow">ПРОИЗВОДСТВО ПОД ВАШУ ЗАДАЧУ</p><h2>Нужна партия<br>или особый размер?</h2></div><div><p>Расскажите, для какой техники нужны изделия, в каком количестве и какие размеры важны. Обсудим решение с производством.</p><button class="button accent" data-request="Партия для бизнеса">Обсудить задачу <span aria-hidden="true">↗</span></button></div></section>'''


def render():
    products = json.loads((ROOT / 'catalog/products.json').read_text())['products']
    slugs = set()
    for product in products:
        slug = product['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in slugs:
            raise ValueError(f'Invalid or duplicate slug: {slug}')
        slugs.add(slug)
        for img in product['images']:
            if not (DIST / img['src'].lstrip('/')).is_file():
                raise ValueError(f'Missing image: {img["src"]}')
        page_dir = DIST / 'catalog' / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        html = shell(hero(product) + detail_sections(product), f'{product["name"]} — {product["material"]}, {len(product["sizes"])} размеров | Needle Shark', product['seoDescription'], product['name'], product_slug=slug)
        (page_dir / 'index.html').write_text(html)
    (DIST / 'catalog/index.html').write_text(shell(catalogue(products), 'Каталог изделий из технических тканей | Needle Shark', 'Готовые изделия Needle Shark: чехлы для техники из Oxford. Выбор размера, покупка на маркетплейсах и заказ партии у производителя.', catalog_current='page'))
    print(f'Rendered catalogue and {len(products)} product page(s). Homepage unchanged.')


if __name__ == '__main__':
    render()
