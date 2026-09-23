"""Safe, reusable editorial blocks. Reading works before JavaScript enhancement."""
import json
import re
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from site_utils import image_attributes

ROOT = Path(__file__).resolve().parent.parent
SEGMENT = r'[a-z0-9]+(?:-[a-z0-9]+)*'


def e(value):
    return escape(str(value), quote=True)


def rich(text):
    # Only two inline treatments; HTML and URLs remain escaped plain text.
    return re.sub(r'\*\*(.+?)\*\*|==(.+?)==',
                  lambda m: '<strong>' + m[1] + '</strong>' if m[1] else '<mark>' + m[2] + '</mark>', e(text))


def safe_url(value):
    parts = urlsplit(value)
    return (not re.search(r'[\s\\]', value) and
            ((value.startswith('/') and not value.startswith('//')) or
             (parts.scheme == 'https' and bool(parts.hostname) and not parts.username and not parts.password)))


def require_text(data, *keys):
    if any(not isinstance(data.get(key), str) or not data[key].strip() for key in keys):
        raise ValueError('Missing text: ' + ', '.join(keys))


@lru_cache(maxsize=1)
def products():
    data = json.loads((ROOT / 'catalog/products.json').read_text())
    return {product['slug']: product for product in data['products']}


def catalog_image(data):
    product = products().get(data.get('product'))
    item = next((item for item in product['images'] if item['id'] == data.get('image')), None) if product else None
    if not item:
        raise ValueError('Use an existing catalogue product and image id')
    image_attributes(item['src'])  # Reject missing responsive assets before writing pages.
    require_text(data, 'caption')
    return item


def walk(blocks):
    for block in blocks:
        yield block
        if block['type'] in ('tabs', 'accordion'):
            for item in block['items']:
                yield from walk(item['blocks'])


def validate_blocks(blocks):
    cta_ids, heading_ids, interaction_ids = set(), set(), set()
    for block in walk(blocks):
        kind = block['type']
        if kind in ('tabs', 'accordion', 'checklist') and 'id' in block:
            require_text(block, 'id')
            if not re.fullmatch(SEGMENT, block['id']) or block['id'] in interaction_ids:
                raise ValueError('Interactive block ids must be unique URL segments')
            interaction_ids.add(block['id'])
        if kind in ('paragraph', 'heading'):
            require_text(block, 'text')
            if kind == 'heading':
                if 'id' in block:
                    identifier = block['id']
                    if not isinstance(identifier, str) or not re.fullmatch(SEGMENT, identifier) or identifier in heading_ids or re.fullmatch(r'auto-\d+', identifier):
                        raise ValueError('Heading ids must be unique URL segments (auto-N is reserved)')
                    heading_ids.add(identifier)
                if 'tocLabel' in block:
                    require_text(block, 'tocLabel')
        elif kind in ('list', 'checklist'):
            if not block.get('items') or not all(isinstance(item, str) and item.strip() for item in block['items']):
                raise ValueError('Empty list')
            if kind == 'checklist':
                require_text(block, 'title')
        elif kind == 'sources':
            if 'label' in block:
                require_text(block, 'label')
            if not block.get('items'):
                raise ValueError('Empty sources')
            for item in block['items']:
                require_text(item, 'title', 'url')
                if not safe_url(item['url']):
                    raise ValueError('Sources require a safe URL')
        elif kind == 'cta':
            require_text(block, 'id', 'lead', 'text', 'label', 'url')
            for link in [block] + block.get('links', []):
                require_text(link, 'id', 'label', 'url')
                if not re.fullmatch(SEGMENT, link['id']) or link['id'] in cta_ids:
                    raise ValueError('CTA ids must be unique stable URL segments')
                cta_ids.add(link['id'])
                if not safe_url(link['url']):
                    raise ValueError('CTA requires a local path or HTTPS URL')
            if 'image' in block:
                catalog_image(block['image'])
        elif kind == 'image':
            catalog_image(block)
        elif kind == 'callout':
            require_text(block, 'title', 'text')
            if block.get('tone', 'note') not in ('note', 'important'):
                raise ValueError('Unknown callout tone')
        elif kind in ('tabs', 'accordion'):
            require_text(block, 'title')
            if not block.get('items') or (kind == 'tabs' and len(block['items']) < 2):
                raise ValueError('Empty interactive block')
            for item in block['items']:
                require_text(item, 'label')
                if not item.get('blocks') or any(child['type'] not in ('paragraph', 'list', 'sources') for child in item['blocks']):
                    raise ValueError('Panels allow paragraphs, lists and sources only')
        elif kind == 'faq':
            if not block.get('items'):
                raise ValueError('Empty FAQ')
            for item in block['items']:
                require_text(item, 'question', 'answer')
        else:
            raise ValueError('Unknown content block')


def figure(data):
    item = catalog_image(data)
    attributes = image_attributes(item['src'], sizes='(max-width: 800px) 90vw, 740px')
    attrs = ' '.join(f'{key}="{e(value)}"' for key, value in attributes.items())
    return f'<figure class="article-photo"><img {attrs} alt="{e(item["alt"])}" loading="lazy" decoding="async"><figcaption>{rich(data["caption"])}</figcaption></figure>'


class ArticleBlocks:
    def __init__(self, post):
        self.post = post
        self.counter = 0
        self.headings = []
        self.notes = {}

    def render(self, blocks):
        output = []
        for block in blocks:
            self.counter += 1
            key = str(self.counter)
            kind = block['type']
            tracking_id = e(block.get('id', f'{kind}-auto-{key}'))
            if kind == 'paragraph':
                output.append('<p>' + rich(block['text']) + '</p>')
            elif kind == 'heading':
                identifier = 'section-' + block.get('id', 'auto-' + key)
                self.headings.append((identifier, block.get('tocLabel', block['text'])))
                output.append(f'<h2 id="{identifier}" tabindex="-1">{e(block["text"])}</h2>')
            elif kind == 'list':
                output.append('<ul>' + ''.join('<li>' + rich(item) + '</li>' for item in block['items']) + '</ul>')
            elif kind == 'sources':
                links = []
                for index, source in enumerate(block['items']):
                    note = self.notes.setdefault(source['url'], dict(number=len(self.notes) + 1, title=source['title'], refs=[]))
                    ref = f'note-ref-{key}-{index}'
                    note['refs'].append(ref)
                    number = note['number']
                    links.append(f'<a id="{ref}" href="#note-{number}" data-track="blog_note_{number}" role="doc-noteref" aria-label="Источник {number}: {e(source["title"])}" title="{e(source["title"])}">[{number}]</a>')
                output.append('<p class="article-sources">' + e(block.get('label', 'По руководству производителя')) + ' ' + ' '.join(links) + '</p>')
            elif kind == 'image':
                output.append(figure(block))
            elif kind == 'callout':
                output.append(f'<aside class="article-callout {block.get("tone", "note")}" aria-label="{e(block["title"])}"><p class="callout-title">{e(block["title"])}</p><p>{rich(block["text"])}</p></aside>')
            elif kind == 'cta':
                links = []
                for index, link in enumerate([block] + block.get('links', [])):
                    external = ' rel="noopener noreferrer"' if link['url'].startswith('https://') else ''
                    cls = 'button accent' if index == 0 else 'article-cta-link'
                    links.append(f'<a class="{cls}" href="{e(link["url"])}" data-blog-cta="{e(link["id"])}" data-article="{e(self.post["slug"])}"{external}>{e(link["label"])} <span aria-hidden="true">↗</span></a>')
                photo = figure(block['image']) if 'image' in block else ''
                output.append(f'<aside class="article-cta" aria-label="{e(block["lead"])}">{photo}<div class="article-cta-copy"><p class="cta-lead">{e(block["lead"])}</p><p>{rich(block["text"])}</p><div class="article-cta-actions">{"".join(links)}</div></div></aside>')
            elif kind == 'tabs':
                controls, panels = [], []
                for index, item in enumerate(block['items']):
                    panel = f'tabs-{key}-panel-{index}'
                    controls.append(f'<button type="button" id="tabs-{key}-tab-{index}" data-tab-target="{panel}">{e(item["label"])}</button>')
                    panels.append(f'<section id="{panel}" class="article-tab-panel"><h3>{e(item["label"])}</h3>{self.render(item["blocks"])}</section>')
                output.append(f'<section class="article-tabs" data-article-tabs data-blog-block="{tracking_id}" aria-labelledby="tabs-{key}-title"><p id="tabs-{key}-title" class="interactive-title">{e(block["title"])}</p><div class="article-tab-list" aria-labelledby="tabs-{key}-title" hidden>{"".join(controls)}</div>{"".join(panels)}</section>')
            elif kind == 'accordion':
                items = ''.join(f'<details><summary>{e(item["label"])}<span aria-hidden="true">+</span></summary><div class="article-disclosure-content">{self.render(item["blocks"])}</div></details>' for item in block['items'])
                output.append(f'<section class="article-accordion" data-blog-block="{tracking_id}" aria-label="{e(block["title"])}"><p class="interactive-title">{e(block["title"])}</p>{items}</section>')
            elif kind == 'checklist':
                items = ''.join(f'<li><label><input type="checkbox"><span>{rich(item)}</span></label></li>' for item in block['items'])
                output.append(f'<section class="article-checklist" data-article-checklist data-blog-block="{tracking_id}" aria-labelledby="checklist-{key}"><h3 id="checklist-{key}">{e(block["title"])}</h3><p class="checklist-hint">Отмечайте по мере подготовки.</p><ul>{items}</ul><p class="checklist-status" role="status" hidden>Отмечено 0 из {len(block["items"])}</p></section>')
            elif kind == 'faq':
                output.append('<section class="article-faq"><h2>Вопросы и ответы</h2>' + ''.join(f'<h3>{e(item["question"])}</h3><p>{rich(item["answer"])}</p>' for item in block['items']) + '</section>')
        return '\n'.join(output)

    def contents(self):
        if not self.headings:
            return ''
        links = ''.join(f'<li><a href="#{identifier}" data-track="blog_toc_{identifier}">{e(label)}</a></li>' for identifier, label in self.headings)
        return f'<nav class="article-contents" aria-label="Содержание статьи"><p>В этой статье</p><ol>{links}</ol><a class="article-notes-link" href="#article-notes">Источники ↓</a></nav>' if self.notes else f'<nav class="article-contents" aria-label="Содержание статьи"><p>В этой статье</p><ol>{links}</ol></nav>'

    def footnotes(self):
        if not self.notes:
            return ''
        items = []
        for url, note in self.notes.items():
            back = ' '.join(f'<a class="note-back" href="#{ref}" data-track="blog_note_return_{note["number"]}" aria-label="Вернуться к упоминанию {index + 1} источника {note["number"]}">↩{index + 1 if len(note["refs"]) > 1 else ""}</a>' for index, ref in enumerate(note['refs']))
            items.append(f'<li id="note-{note["number"]}" tabindex="-1"><a href="{e(url)}" data-track="blog_source_{note["number"]}" rel="noopener noreferrer">{e(note["title"])}</a> {back}</li>')
        return '<section class="article-notes" role="doc-endnotes" aria-labelledby="article-notes"><h2 id="article-notes" tabindex="-1">Источники и примечания</h2><ol>' + ''.join(items) + '</ol></section>'
