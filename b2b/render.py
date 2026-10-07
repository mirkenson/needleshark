"""Build an isolated B2B review site. Production sources and dist stay untouched."""
import argparse
import hashlib
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html, external_url
from catalog.render import picture, image_for

SOURCE = Path(__file__).resolve().parent
DATA = json.loads((SOURCE / 'content.json').read_text())
DIRECTIONS = DATA['directions']
MANIFEST = json.loads((ROOT / 'business/assets/manifest.json').read_text())
PHONE = '+7 911 128-51-32'
EMAIL = 'info@neesha.ru'


def e(value):
    return escape(str(value), quote=True)


def route(item):
    return '/napravleniya/' + item['slug'] + '/'


def icon(name):
    shapes = {
        'cover': '<path d="M7 31V15l8-5h18l8 5v24H7zM7 18h34M15 10v8m18-8v8M12 39v3m24-3v3M12 24h9v9h-9m17-9h8m-8 5h8"/>',
        'bag': '<path d="M6 18h36v23H6zM17 18v-6h14v6M6 25h36M12 18v23m24-23v23M22 22h4v6h-4"/>',
        'strap': '<path d="M8 14h32v10H8zM15 14v10m18-10v10M8 33h12m8 0h12M20 28h8v10h-8zM8 9v20m32-20v20"/>',
        'curtain': '<path d="M5 9h38M9 9v31l7-3 8 3 8-3 7 3V9M16 15v22m8-22v25m8-25v22"/>',
        'drawing': '<path d="M10 6h21l8 8v29H10zM31 6v9h8M16 23h14v12H16zM13 20h20m-20 18h20M19 20v18m-6-11h20"/>',
    }
    return f'<svg class="ns-icon" viewBox="0 0 48 48" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">{shapes[name]}</svg>'


def business_picture(key, alt, eager=False):
    dims = MANIFEST[key]
    return (f'<img src="/business/assets/{key}-800.webp" srcset="' + ', '.join(f'/business/assets/{key}-{w}.webp {w}w' for w in (480, 800, 1280))
            + f'" sizes="(max-width:700px) 92vw, 45vw" width="{dims["width"]}" height="{dims["height"]}" alt="{e(alt)}" loading="{"eager" if eager else "lazy"}" decoding="async">')


def button(text, href='#contact', secondary=False, topic=''):
    return f'<a class="ns-button{" ns-button-secondary" if secondary else ""}" href="{e(href)}"' + (f' data-topic="{e(topic)}"' if topic else '') + f'>{e(text)}<span aria-hidden="true">↗</span></a>'


def section_head(kicker, title, intro=''):
    return f'<div class="ns-section-head"><div><p class="ns-kicker">{kicker}</p><h2>{title}</h2></div>' + (f'<p class="ns-section-intro">{intro}</p>' if intro else '') + '</div>'


def header(contact_href='/#contact'):
    links = ''.join(f'<a href="{route(d)}">{e(d["label"])}<span aria-hidden="true">↗</span></a>' for d in DIRECTIONS)
    return f'''<a class="ns-skip" href="#main">Перейти к содержимому</a>
    <header class="ns-header"><div class="ns-container ns-header-inner">
      <a class="ns-brand" href="/" aria-label="Needle Shark — главная"><img src="/logo.svg" width="1026" height="348" alt="Needle Shark"></a>
      <nav class="ns-nav" aria-label="Основная навигация"><details class="ns-directions-menu"><summary>Направления <span aria-hidden="true">⌄</span></summary><div>{links}</div></details><a href="/business/">Производство</a><a href="/#materials">Материалы</a><a href="/#contact">Контакты</a></nav>
      <div class="ns-header-contacts"><a href="tel:+79111285132">{PHONE}</a><a href="mailto:{EMAIL}">{EMAIL}</a></div>
      {button('Рассчитать заказ', contact_href)}
      <button class="ns-menu-toggle" type="button" aria-controls="ns-mobile-menu" aria-expanded="false" hidden>Меню <span aria-hidden="true">☰</span></button>
    </div><nav id="ns-mobile-menu" class="ns-mobile-menu ns-container" aria-label="Мобильная навигация" hidden><p class="ns-kicker">Направления производства</p>{links}<div class="ns-mobile-secondary"><a href="/business/">Производство</a><a href="/#materials">Материалы</a><a href="/#process">Как заказать</a><a href="/catalog/">Готовые изделия</a><a href="/#contact">Контакты</a></div></nav></header>'''


def messengers():
    return '<div class="ns-messengers" role="group" aria-label="Мессенджеры — ссылки будут добавлены">' + ''.join(f'<button type="button" disabled title="Контакт будет добавлен">{label}<span aria-hidden="true">↗</span></button>' for label in ['Telegram', 'MAX', 'WhatsApp', 'ВКонтакте']) + '</div><p class="ns-messenger-note">Ссылки на мессенджеры будут добавлены. Сейчас можно позвонить или написать на почту.</p>'


def footer(contact_href='/#contact'):
    links = ''.join(f'<a href="{route(d)}">{e(d["label"])}</a>' for d in DIRECTIONS)
    return f'''<footer class="ns-footer"><div class="ns-container"><div class="ns-footer-grid">
      <div class="ns-footer-about"><a class="ns-brand" href="/" aria-label="Needle Shark — главная"><img src="/logo.svg" width="1026" height="348" alt="Needle Shark"></a><p>Швейное производство технических изделий в Санкт-Петербурге. Разработка и пошив под задачи вашего бизнеса.</p><span class="ns-footer-stamp">С точностью до нитки.</span></div>
      <nav aria-label="Направления в подвале"><h3>Направления</h3>{links}</nav>
      <nav aria-label="Информация о компании"><h3>Производство</h3><a href="/business/">О производстве</a><a href="/#process">Как заказать</a><a href="/#materials">Ткани и материалы</a><a href="/#faq">Вопросы и ответы</a><a href="/catalog/">Готовые изделия</a><a href="/blog/">Полезные материалы</a></nav>
      <div class="ns-footer-contact"><h3>Обсудим вашу задачу</h3><a class="ns-footer-phone" href="tel:+79111285132">{PHONE}</a><a href="mailto:{EMAIL}">{EMAIL}</a>{button('Рассчитать заказ', contact_href)}{messengers()}</div>
    </div><div class="ns-footer-bottom"><p>© Needle Shark, 2026<br><span>ИП Сергеев Даниил Игоревич · ИНН 026610829836 · Санкт-Петербург</span></p><div><a href="/privacy-policy">Политика обработки данных</a><a href="/user-agreement">Пользовательское соглашение</a><a href="#main">Наверх ↑</a></div></div></div></footer>'''


def form(topic=''):
    return f'''<section class="ns-contact" id="contact"><div class="ns-container ns-contact-grid"><div><p class="ns-kicker">НАЧНЁМ С ВАШЕЙ ЗАДАЧИ</p><h2>Расскажите,<br>что нужно <em>сшить.</em></h2><p class="ns-lead">Уточним детали, подберём материал и подготовим расчёт. Можно начать с короткого описания.</p><a class="ns-contact-phone" href="tel:+79111285132">{PHONE}</a><a class="ns-contact-email" href="mailto:{EMAIL}">{EMAIL}</a>{messengers()}</div>
    <form class="ns-form ym-hide-content" data-topic="{e(topic)}" method="post" action="/api/leads" novalidate><p class="ns-form-caption">Заявка на расчёт <span>От 1 рабочего дня*</span></p>
      <label for="lead-name">Имя <span aria-hidden="true">*</span></label><input id="lead-name" name="name" autocomplete="name" maxlength="120" placeholder="Как к вам обращаться" required>
      <div class="ns-form-row"><div><label for="lead-email">Почта</label><input id="lead-email" name="email" type="email" autocomplete="email" maxlength="254" placeholder="name@company.ru" aria-describedby="contact-hint contact-error"></div><div><label for="lead-phone">Телефон</label><input id="lead-phone" name="phone" type="tel" autocomplete="tel" maxlength="32" placeholder="+7 (___) ___-__-__" aria-describedby="contact-hint contact-error"></div></div>
      <p id="contact-hint" class="ns-field-hint">Укажите почту или телефон — достаточно одного контакта.</p><p id="contact-error" class="ns-field-error" role="alert" hidden></p>
      <label for="lead-description">Описание задачи <span aria-hidden="true">*</span></label><textarea id="lead-description" name="description" rows="4" maxlength="5000" placeholder="Какое изделие нужно, примерное количество, размеры и условия использования" required></textarea>
      <div class="ns-file-note"><span aria-hidden="true">↗</span><p>Фото, чертежи, ТЗ и 3D-модели отправьте на <a href="mailto:{EMAIL}">{EMAIL}</a> или в мессенджер. В форме файлы не прикрепляются.</p></div>
      <label class="ns-consent"><input name="consent" type="checkbox" required><span>Принимаю <a href="/user-agreement" target="_blank" rel="noopener">пользовательское соглашение</a> и даю согласие на обработку персональных данных по <a href="/privacy-policy" target="_blank" rel="noopener">политике</a>.</span></label>
      <button class="ns-button" type="submit">Получить расчёт <span aria-hidden="true">↗</span></button><p class="ns-form-status" role="status" hidden></p><p class="ns-field-hint">* После уточнения исходных данных. Срок производства согласуем отдельно.</p><noscript><p>Для отправки заявки напишите на <a href="mailto:{EMAIL}">{EMAIL}</a> или позвоните.</p></noscript>
    </form></div></section>'''


def materials():
    tabs = ''.join(f'<button type="button" id="tab-{m["id"]}" data-material="{m["id"]}">{e(m["name"])}</button>' for m in DATA['materials'])
    panels = []
    for m in DATA['materials']:
        specs = ''.join(f'<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>' for k, v in m['specs'])
        panels.append(f'''<section class="ns-material-panel" id="panel-{m['id']}" data-panel="{m['id']}" aria-label="{e(m['name'])}"><figure>{business_picture('fabric-'+m['id'], 'Фактура материала: '+m['name'])}<figcaption>{e(m['code'])} <span>Образец фактуры</span></figcaption></figure><div><p class="ns-kicker">{e(m['name'])}</p><h3>{e(m['title'])}</h3><p>{e(m['text'])}</p><dl class="ns-specs">{specs}</dl><p class="ns-material-note">{e(m['note'])}</p><div class="ns-material-links"><a class="ns-text-link" href="#contact" data-topic="Материал: {e(m['name'])}">Подобрать материал <span aria-hidden="true">↗</span></a><a class="ns-source-link" href="{e(external_url(m['source'], 'b2b_material_'+m['id']))}" target="_blank" rel="noopener noreferrer">{e(m['sourceLabel'])} ↗</a></div></div></section>''')
    return '<section class="ns-materials" id="materials"><div class="ns-container">' + section_head('МАТЕРИАЛЫ / ПОД ЗАДАЧУ', 'Начинаем с условий.<br>Подбираем ткань.', 'Хранение или перевозка, помещение или улица, лёгкий чехол или нагруженная сумка — материал зависит от задачи.') + f'<div class="ns-material-tabs" aria-label="Выбрать материал">{tabs}</div>' + ''.join(panels) + '</div></section>'


def process():
    stages = [('Задача', 'Вы описываете изделие, условия использования и нужный объём.'), ('Расчёт', 'Уточняем данные, подбираем материалы и рассчитываем стоимость от 1 рабочего дня.'), ('Согласование', 'Фиксируем конструкцию, цену, сроки и условия в договоре.'), ('Образец', 'При необходимости шьём платный образец или пробную партию перед серией.'), ('Производство', 'Шьём, проверяем качество. Менеджер сопровождает заказ на всех этапах.'), ('Доставка', 'Отправляем по России или передаём заказ на самовывоз в Санкт-Петербурге.')]
    items = ''.join(f'<li><span>{i:02}</span><h3>{t}</h3><p>{p}</p></li>' for i, (t, p) in enumerate(stages, 1))
    return '<section class="ns-container ns-section" id="process">' + section_head('КАК МЫ РАБОТАЕМ', 'От первого сообщения<br>до готовой партии.', 'На каждом этапе — понятный следующий шаг и связь с вашим менеджером.') + f'<ol class="ns-process">{items}</ol><div class="ns-guarantee"><strong>12 месяцев гарантии</strong><p>На изготовленные изделия. Условия гарантии и порядок обращения фиксируем в договоре.</p>{button("Обсудить заказ")}</div></section>'


def faq(extra=()):
    common = [('С какой партии можно начать?', 'Для уникальных изделий объём согласуем индивидуально. Готовые модели производим партиями от 20 штук. Расскажите о задаче — обсудим подходящий формат.'), ('Что влияет на стоимость?', 'Размеры и геометрия, расход и тип ткани, количество слоёв, швов и деталей, фурнитура и объём партии. Точную стоимость рассчитываем по исходным данным.'), ('Как работать с вами из другого города?', 'Обсуждаем задачу дистанционно, согласуем детали по фото и видео. Готовые изделия отправляем транспортной компанией по России. Срок и стоимость доставки уточняем отдельно.'), ('Можно использовать наши материалы?', 'Это обсуждаем до запуска: проверим, подходит ли материал для конструкции, и согласуем его доставку. Можно пришивать бирки заказчика.')]
    items = ''.join(f'<details><summary>{e(q)}<span aria-hidden="true">+</span></summary><p>{e(a)}</p></details>' for q, a in [*extra, *common])
    return '<section class="ns-container ns-section ns-faq" id="faq"><div><p class="ns-kicker">ВОПРОСЫ И ОТВЕТЫ</p><h2>До начала<br>работы.</h2></div><div class="ns-faq-list">' + items + '</div></section>'


def production():
    return '<section class="ns-container ns-section" id="production">' + section_head('ПРОИЗВОДСТВО / САНКТ-ПЕТЕРБУРГ', 'От конструкции<br>до последней строчки.', 'Сначала — назначение и условия использования. Затем — материал, лекала, раскрой и пошив.') + f'''<div class="ns-production-grid"><figure>{business_picture('workshop-room','Швейный цех — визуализация по фотографиям производства')}<figcaption>Швейное производство / визуализация по фотографиям цеха</figcaption></figure><div class="ns-production-copy"><article><span>01</span><div><h3>Разработка под вашу задачу</h3><p>Начнём с ТЗ, эскиза или образца. Разработка входит в стоимость партии.</p></div></article><article><span>02</span><div><h3>Сопровождение на всех этапах</h3><p>Согласуем точки связи и показываем ход работ по фото и видео.</p></div></article><article><span>03</span><div><h3>Контроль готовых изделий</h3><p>Проверяем партию по нашим или согласованным с вами требованиям.</p></div></article>{button('Обсудить производство')}</div></div></section>'''


def home():
    quick = ''.join(f'<a class="ns-quick-link" href="{route(d)}"><span class="ns-quick-icon">{icon(d["icon"])}</span><span><strong>{e(d["label"])}</strong><small>{e(d["tag"])}</small></span><span class="ns-arrow" aria-hidden="true">↗</span></a>' for d in DIRECTIONS)
    usps = [('По всей России', 'Доставка готовых изделий'), ('От 1 рабочего дня', 'Расчёт стоимости партии*'), ('По вашему ТЗ', 'Разработка и пошив'), ('На каждом этапе', 'Полное сопровождение заказа'), ('12 месяцев', 'Гарантия на изделия')]
    usp = ''.join(f'<div><span class="ns-usp-index">{i:02}</span><strong>{title}</strong><p>{text}</p></div>' for i, (title, text) in enumerate(usps, 1))
    hero = f'''<section class="ns-hero"><div class="ns-container ns-hero-grid"><div class="ns-hero-copy"><p class="ns-kicker"><span class="ns-location-dot"></span> NEEDLE SHARK / САНКТ-ПЕТЕРБУРГ</p><h1>Швейное производство<br><em>под вашу задачу.</em></h1><p class="ns-lead">Чехлы, сумки, ременные изделия, укрытия и шторы из технических тканей. От вашего ТЗ до готовой партии.</p><div class="ns-actions">{button('Рассчитать заказ')}{button('Выбрать направление','#directions',True)}</div><p class="ns-hero-foot">Разработка · Раскрой · Пошив · Контроль качества</p></div><aside class="ns-hero-directions" aria-label="Направления производства"><div class="ns-quick-heading"><span>ЧТО МЫ ШЬЁМ</span><span>01—05</span></div>{quick}</aside><div class="ns-usps">{usp}</div><p class="ns-usp-note">* После уточнения исходных данных. Срок изготовления согласуем под ваш заказ.</p></div></section>'''
    ozon = external_url('https://www.ozon.ru/seller/needle-shark/', 'b2b_home_reviews')
    trust = f'''<section class="ns-trust"><div class="ns-container ns-trust-grid"><div><p class="ns-kicker">ОПЫТ В ГОТОВЫХ ИЗДЕЛИЯХ</p><h2>Наш магазин на Ozon.</h2><a href="{e(ozon)}" target="_blank" rel="noopener noreferrer">Смотреть магазин и отзывы ↗</a></div><div class="ns-trust-stat"><strong>80 000+</strong><span>продаж в нашем магазине</span></div><div class="ns-trust-stat"><strong>4,9<span> / 5</span></strong><span class="ns-stars" aria-label="Рейтинг 4,9 из 5">★★★★★</span></div><div class="ns-trust-stat"><strong>24 000</strong><span>отзывов покупателей</span></div></div></section>'''
    cards = ''.join(f'<a class="ns-direction-card{" ns-custom-card" if d["slug"]=="po-tz" else ""}" href="{route(d)}"><div class="ns-direction-meta"><span>{i:02} / {e(d["tag"])}</span>{icon(d["icon"])}</div><h3>{e(d["label"])}</h3><p>{e(d["description"])}</p><span class="ns-card-link">Подробнее о направлении <span aria-hidden="true">↗</span></span></a>' for i, d in enumerate(DIRECTIONS, 1))
    dirs = '<section class="ns-container ns-section" id="directions">' + section_head('НАПРАВЛЕНИЯ ПРОИЗВОДСТВА', 'Разные изделия.<br>Внимание к каждой задаче.', 'Выберите своё направление. Если готовой категории нет — начнём с вашего технического задания.') + '<div class="ns-direction-grid">' + cards + '</div></section>'
    examples = ''.join(f'<a class="ns-example" href="{route(d)}"><figure>{business_picture(d["image"], "Иллюстрация направления: "+d["label"])}<figcaption><span>0{i} / {e(d["short"])}</span><span aria-hidden="true">↗</span></figcaption></figure><h3>{e(t)}</h3><p>{e(p)}</p></a>' for i, (d, t, p) in enumerate(zip(DIRECTIONS[:3], ['Посадка по форме объекта','Всё нужное — в одном комплекте','Крепления, которые подходят'], ['Размеры, доступ к узлам и фиксация чехла.','Объём, отделения и удобство переноски.','Длина, регулировка и согласованная фурнитура.']), 1))
    examples = '<section class="ns-examples"><div class="ns-container">' + section_head('ПРИМЕРЫ ИСПОЛНЕНИЯ', 'Детали определяют<br>готовое изделие.', 'Иллюстрации направлений. Конструкцию и комплектность вашего заказа согласуем отдельно.') + '<div class="ns-example-grid">' + examples + '</div></div></section>'
    cta = f'<section class="ns-container ns-custom-cta"><div>{icon("drawing")}<p class="ns-kicker">ЕСТЬ ЧЕРТЁЖ, ОБРАЗЕЦ ИЛИ ИДЕЯ?</p><h2>Начнём с того,<br>что есть у вас.</h2><p>Изучим исходные данные, уточним требования и предложим конструкцию под задачу.</p></div><div>{button("Обсудить пошив по ТЗ",route(DIRECTIONS[-1]))}<a href="mailto:{EMAIL}">Отправить файлы на {EMAIL} ↗</a></div></section>'
    return hero + trust + dirs + examples + materials() + production() + cta + process() + faq() + form()


def direction_page(d):
    applications = ''.join(f'<article><span>{i:02}</span><h3>{e(t)}</h3><p>{e(p)}</p></article>' for i, (t, p) in enumerate(d['applications'],1))
    construction = ''.join(f'<div><dt>{e(t)}</dt><dd>{e(p)}</dd></div>' for t,p in d['construction'])
    brief = ''.join(f'<li>{e(x)}</li>' for x in d['brief'])
    hero = f'''<div class="ns-container ns-breadcrumbs"><a href="/">Главная</a><span>/</span><a href="/#directions">Направления</a><span>/</span><span>{e(d['short'])}</span></div><section class="ns-container ns-detail-hero"><div><p class="ns-kicker">{e(d['tag'])} / САНКТ-ПЕТЕРБУРГ</p><h1>{e(d['title'])}</h1><p class="ns-lead">{e(d['intro'])}</p><div class="ns-actions">{button('Рассчитать заказ',topic=d['label'])}{button('Что нужно для расчёта','#brief',True)}</div><div class="ns-detail-promises"><span>Доставка по России</span><span>Гарантия 12 месяцев</span></div></div><figure>{business_picture(d['image'],'Иллюстрация: '+d['label'], True)}<figcaption>Иллюстрация направления / конструкция по вашей задаче</figcaption></figure></section>'''
    applications = '<section class="ns-container ns-section">' + section_head('ЗАДАЧИ И ПРИМЕНЕНИЯ', 'Что можно заказать.', 'Состав изделия зависит от объекта, условий использования и требований вашей команды.') + f'<div class="ns-application-grid">{applications}</div></section>'
    details = f'<section class="ns-construction"><div class="ns-container ns-construction-grid"><div><p class="ns-kicker">КОНСТРУКЦИЯ</p><h2>Продумываем<br>каждый узел.</h2><p>Согласуем детали до запуска производства, чтобы изделием было удобно пользоваться.</p>{button("Обсудить конструкцию",topic=d["label"])}</div><dl>{construction}</dl></div></section>'
    briefing = f'<section class="ns-container ns-section ns-brief" id="brief"><div><p class="ns-kicker">ДЛЯ РАСЧЁТА</p><h2>Чем точнее задача,<br>тем точнее расчёт.</h2><p>Не все данные есть сразу? Оставьте контакт — поможем разобраться.</p>{button("Описать задачу",topic=d["label"])}</div><ol>{brief}</ol></section>'
    others = '<section class="ns-container ns-related"><p class="ns-kicker">ДРУГИЕ НАПРАВЛЕНИЯ</p><div>' + ''.join(f'<a href="{route(x)}">{e(x["label"])} <span aria-hidden="true">↗</span></a>' for x in DIRECTIONS if x!=d) + '</div></section>'
    return hero + applications + details + materials() + briefing + process() + faq(d['faq']) + form(d['label']) + others


def catalogue(products):
    cards, categories = [], {}
    for p in products:
        category = p.get('catalogCategory', {'id':p['category'], 'label':p['category']})
        categories[category['id']] = category['label']
        market = next((m for m in p['marketplaces'] if m.get('url')), None)
        if not market:
            continue
        url = external_url(market['url'], 'b2b_catalog_'+p['slug'])
        img = picture(image_for(p,'hero'), len(cards)<4, '(max-width:600px) 92vw, (max-width:1000px) 44vw, 28vw')
        cards.append(f'''<article class="ns-product" id="{p['slug']}" data-category="{e(category['id'])}" data-search="{e(p['name']+' '+p['description']+' '+category['label'])}"><a class="ns-product-image" href="{e(url)}" target="_blank" rel="noopener noreferrer" aria-label="{e(p['name'])} на {e(market['name'])}">{img}<span aria-hidden="true">↗</span></a><p class="ns-product-category">{e(category['label'])}</p><h2>{e(p['name'])}</h2><p class="ns-product-copy">{e(p.get('catalogSummary',p['shortDescription']))}</p><a class="ns-product-market" href="{e(url)}" target="_blank" rel="noopener noreferrer">Выбрать на {e(market['name'])}<span aria-hidden="true">↗</span></a></article>''')
    filters = '<button type="button" data-filter="" aria-pressed="true">Все изделия</button>' + ''.join(f'<button type="button" data-filter="{e(k)}" aria-pressed="false">{e(v)}</button>' for k,v in categories.items())
    return f'''<section class="ns-container ns-catalog-intro"><p class="ns-kicker">ГОТОВЫЕ ИЗДЕЛИЯ / NEEDLE SHARK</p><h1>Готовые решения.<br><em>Проверенные детали.</em></h1><p class="ns-lead">Наши серийные изделия можно заказать на маркетплейсах. Размеры, комплектации, актуальные цены и наличие — на странице выбранного товара.</p><a class="ns-text-link" href="/#contact">Нужна партия или другая конструкция? Обсудим пошив ↗</a></section><section class="ns-container ns-catalog"><div class="ns-catalog-tools" hidden><label for="product-search">Найти изделие<input id="product-search" type="search" placeholder="Название или назначение" maxlength="150" autocomplete="off"></label><div class="ns-catalog-filters" role="group" aria-label="Категории">{filters}</div><p id="product-count" role="status">{len(cards)} изделий</p></div><div class="ns-product-grid">{''.join(cards)}</div><div class="ns-empty" hidden><h2>Ничего не нашлось.</h2><p>Попробуйте другое название или сбросьте фильтры.</p><button class="ns-button" id="reset-search" type="button">Показать все изделия <span aria-hidden="true">↗</span></button></div></section>'''


def preview_assets():
    def asset(name):
        version = hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()[:12]
        return f'/b2b/{name}?v={version}'
    return (f'<link rel="stylesheet" href="{asset("typography.css")}">'
            f'<link rel="stylesheet" href="{asset("site.css")}">'
            f'<script type="module" src="{asset("site.js")}"></script>')


def page(body, title, description, path):
    body = body.replace('<br>', ' <br>')
    contact_href = '#contact' if 'class="ns-form ' in body else '/#contact'
    source = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title><meta name="description" content="{e(description)}"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/typography.css">{preview_assets()}</head><body class="ns-site" data-preview="true">{header(contact_href)}<main id="main">{body}</main>{footer(contact_href)}<div class="ns-preview-badge" aria-label="Локальный прототип">Прототип · заявки не отправляются</div></body></html>'''
    return make_preview(prepare_html(source,path))


def make_preview(html):
    html = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex,nofollow">', html)
    html = re.sub(r'<script[^>]+src="[^"]*(?:metrika|analytics)\.js[^>]*></script>', '', html)
    html = re.sub(r'<noscript>\s*<div>\s*<img[^>]+mc\.yandex\.ru[^>]+>\s*</div>\s*</noscript>', '', html)
    return html


def build(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or destination.is_relative_to(ROOT / 'dist'):
        raise ValueError('Prototype must not replace production sources')
    destination.mkdir(parents=True, exist_ok=True)
    # Only copy baseline assets and unaffected sections; catalogue detail URLs are
    # handled by the review server, never deleted from the production tree.
    for item in (ROOT/'dist').iterdir():
        if item.name in {'index.html','catalog','business','sitemap.xml','robots.txt'}:
            continue
        if item.is_dir():
            shutil.copytree(item,destination/item.name,dirs_exist_ok=True)
        else:
            shutil.copy2(item,destination/item.name)
    shutil.copytree(ROOT/'business/assets',destination/'business/assets',dirs_exist_ok=True)
    (destination/'b2b').mkdir(exist_ok=True)
    for name in ('site.css','site.js','typography.css','form-validation.mjs'):
        shutil.copy2(SOURCE/name,destination/'b2b'/name)
    products = sorted((p for p in json.loads((ROOT/'catalog/products.json').read_text())['products'] if p.get('visible') and p.get('status','published')=='published'),key=lambda p:p['order'])
    pages = {'index.html':page(home(),'Швейное производство в Санкт-Петербурге | Needle Shark','Разработка и пошив чехлов, сумок, ременных изделий, укрытий и штор по ТЗ. Доставка по России, расчёт от 1 рабочего дня, гарантия 12 месяцев.','index.html')}
    for d in DIRECTIONS:
        path = route(d).lstrip('/')+'index.html'
        pages[path]=page(direction_page(d),d['label']+' на заказ в СПб | Needle Shark',d['intro'],path)
    pages['catalog/index.html']=page(catalogue(products),'Готовые изделия Needle Shark — каталог','Чехлы, сумки, ремни и другие готовые изделия Needle Shark. Выберите товар и перейдите на маркетплейс.','catalog/index.html')
    production_body = '<section class="ns-container ns-catalog-intro"><p class="ns-kicker">NEEDLE SHARK / ПРОИЗВОДСТВО</p><h1>Шьём в Петербурге.<br><em>Работаем по всей России.</em></h1><p class="ns-lead">Технические изделия под задачу бизнеса: от обсуждения конструкции до проверки готовой партии.</p></section>' + production()+materials()+process()+faq()+form()
    pages['business/index.html']=page(production_body,'Производство и условия заказа | Needle Shark','Швейное производство Needle Shark в Санкт-Петербурге. Разработка, пошив, контроль качества и доставка изделий по России.','business/index.html')
    for path,html in pages.items():
        target=destination/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(html)
    redirects={f'/catalog/{p["slug"]}/':f'/catalog/#{p["slug"]}' for p in products}
    (destination/'preview-redirects.json').write_text(json.dumps(redirects,ensure_ascii=False,indent=2)+'\n')
    # Keep article prose and legal copy unchanged, adapting only navigation and
    # product destinations inside the isolated review output.
    for target in destination.rglob('*.html'):
        html=target.read_text()
        if target.relative_to(destination).as_posix() not in pages:
            html=re.sub(r'<header\b.*?</header>',header(),html,flags=re.S)
            html=re.sub(r'<(?:div|nav)\b[^>]*\bid="mobile-menu"[^>]*>.*?</(?:div|nav)>','',html,flags=re.S)
            html=re.sub(r'<footer\b.*?</footer>',footer(),html,flags=re.S)
            html=html.replace('</head>',preview_assets()+'</head>')
            html=re.sub(r'<script[^>]+src="[^"]*/menu\.js[^>]*></script>','',html)
            if 'id="main"' not in html:
                html=re.sub(r'<main\b', '<main id="main"', html, count=1)
        for old,new in redirects.items():
            html=html.replace('href="'+old+'"','href="'+new+'"')
            html=re.sub(r'href="'+re.escape(old)+r'#[^"]*"','href="'+new+'"',html)
        target.write_text(make_preview(html))
    (destination/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    (destination/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>\n')
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'outputs/b2b-preview'))
    args=parser.parse_args()
    print(build(args.output))
