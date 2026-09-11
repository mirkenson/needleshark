"""Build the blog from approved structured text, using only Python's stdlib."""
import json
import sys
import re
from datetime import date
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html, ORIGIN, json_ld, breadcrumbs
BASE = Template((ROOT / 'blog/base.html').read_text())


def e(value):
    return escape(str(value), quote=True)


def safe_url(value):
    parts = urlsplit(value)
    return (not re.search(r'[\s\\]', value) and
            ((value.startswith('/') and not value.startswith('//')) or
             (parts.scheme == 'https' and bool(parts.hostname) and not parts.username and not parts.password)))


def validate(posts):
    slugs = set()
    for post in posts:
        slug = post['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in slugs:
            raise ValueError('Article slugs must be unique lowercase URL segments')
        slugs.add(slug)
        if post['status'] not in ('draft', 'published'):
            raise ValueError('Use draft or published status')
        if 'featured' in post and not isinstance(post['featured'], bool):
            raise ValueError('featured must be boolean')
        date.fromisoformat(post['date'])
        if post.get('updated') and date.fromisoformat(post['updated']) < date.fromisoformat(post['date']):
            raise ValueError('Update cannot precede publication')
        for key in ('seoTitle', 'seoDescription', 'author'):
            if key in post and (not isinstance(post[key], str) or not post[key].strip()):
                raise ValueError(f'Invalid {key}')
        for key in ('title', 'description'):
            if not isinstance(post[key], str) or not post[key].strip():
                raise ValueError(f'Missing {key}')
        if not post['blocks']:
            raise ValueError('Article body is empty')
        cta_ids = set()
        for block in post['blocks']:
            if block['type'] in ('paragraph', 'heading'):
                if not isinstance(block['text'], str) or not block['text'].strip():
                    raise ValueError('Empty text block')
            elif block['type'] == 'list':
                if not block['items'] or not all(isinstance(item, str) and item.strip() for item in block['items']):
                    raise ValueError('Empty list')
            elif block['type'] == 'sources':
                if not block['items'] or not all(isinstance(item.get('title'), str) and item['title'].strip() and isinstance(item.get('url'), str) and safe_url(item['url']) for item in block['items']):
                    raise ValueError('Sources require a title and safe URL')
            elif block['type'] == 'cta':
                for key in ('id', 'lead', 'text', 'label', 'url'):
                    if not isinstance(block[key], str) or not block[key].strip():
                        raise ValueError(f'Missing CTA {key}')
                if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', block['id']) or block['id'] in cta_ids:
                    raise ValueError('CTA ids must be unique stable URL segments')
                cta_ids.add(block['id'])
                if not safe_url(block['url']):
                    raise ValueError('CTA requires a local path or HTTPS URL')
            elif block['type'] == 'faq':
                if not block['items'] or not all(isinstance(item.get(key), str) and item[key].strip() for item in block['items'] for key in ('question', 'answer')):
                    raise ValueError('FAQ requires questions and answers')
            else:
                raise ValueError('Unknown content block')


def shell(content, title, description, current='false', slug=None, structured=None):
    metadata = ''  # Common canonical/social/icon metadata comes from prepare_html.
    if structured:
        metadata += json_ld(structured)
    trail = [('Главная', '/'), ('Блог', '/blog/')]
    if slug:
        trail.append((structured['headline'], '/blog/' + slug + '/'))
    metadata += json_ld(breadcrumbs(trail))
    return BASE.substitute(content=content, title=e(title), description=e(description), blog_current=current, metadata=metadata)


def date_label(value):
    return date.fromisoformat(value).strftime('%d.%m.%Y')


def render(posts, output):
    validate(posts)  # Validate everything before modifying generated files.
    published = sorted((p for p in posts if p['status'] == 'published'), key=lambda p: (p['date'], p['slug']), reverse=True)
    intro = '<section class="wrap blog-intro"><p class="eyebrow">NEEDLE SHARK / БЛОГ</p><h1>Блог<span class="title-dot">.</span></h1><p>О материалах, изделиях и работе производства.</p></section>'
    cards = ''.join(f'<article class="blog-card"><time datetime="{e(p["date"])}">{date_label(p["date"])}</time><div><h2><a href="/blog/{p["slug"]}/">{e(p["title"])} <span aria-hidden="true">↗</span></a></h2><p>{e(p["description"])}</p></div></article>' for p in published)
    collection = f'<section class="wrap blog-list" aria-label="Статьи">{cards}</section>' if cards else '<section class="wrap blog-empty" aria-labelledby="empty-title"><h2 id="empty-title">Здесь появятся<br>первые статьи.</h2><div><p>Публикаций пока нет. А познакомиться с нашими изделиями можно уже сейчас.</p><a href="/catalog/">Перейти в каталог <span aria-hidden="true">↗</span></a></div></section>'
    blog_schema = {'@context': 'https://schema.org', '@type': 'CollectionPage', '@id': ORIGIN + '/blog/#webpage',
                   'name': 'Блог Needle Shark', 'mainEntity': {'@type': 'ItemList', 'itemListElement': [
                       {'@type': 'ListItem', 'position': i + 1, 'name': post['title'],
                        'url': ORIGIN + '/blog/' + post['slug'] + '/'} for i, post in enumerate(published)]}}
    pages = {'index.html': shell(intro + collection, 'Блог о чехлах, материалах и хранении техники | Needle Shark', 'Статьи Needle Shark о защитных чехлах, технических тканях и уходе за техникой. Подготовка мотоцикла и квадроцикла к зимнему хранению.', 'page', structured=blog_schema)}
    for post in published:
        blocks = []
        for block in post['blocks']:
            if block['type'] == 'list':
                blocks.append('<ul>' + ''.join(f'<li>{e(item)}</li>' for item in block['items']) + '</ul>')
            elif block['type'] == 'sources':
                blocks.append('<p class="article-sources">Источники: ' + '; '.join(f'<a href="{e(item["url"])}" rel="noopener noreferrer">{e(item["title"])}</a>' for item in block['items']) + '.</p>')
            elif block['type'] == 'cta':
                external = ' rel="noopener noreferrer"' if block['url'].startswith('https://') else ''
                blocks.append(f'<aside class="article-cta" aria-label="{e(block["lead"])}"><p class="cta-lead">{e(block["lead"])}</p><p>{e(block["text"])}</p><a class="button accent" href="{e(block["url"])}" data-blog-cta="{e(block["id"])}" data-article="{e(post["slug"])}"{external}>{e(block["label"])} <span aria-hidden="true">↗</span></a></aside>')
            elif block['type'] == 'faq':
                blocks.append('<section class="article-faq"><h2>Вопросы и ответы</h2>' + ''.join(f'<h3>{e(item["question"])}</h3><p>{e(item["answer"])}</p>' for item in block['items']) + '</section>')
            else:
                tag = 'h2' if block['type'] == 'heading' else 'p'
                blocks.append(f'<{tag}>{e(block["text"])}</{tag}>')
        byline = f'<p class="article-author">Автор: {e(post["author"])}</p>' if post.get('author') else ''
        updated = f'<p class="article-updated">Обновлено: <time datetime="{e(post["updated"])}">{date_label(post["updated"])}</time></p>' if post.get('updated') else ''
        body = f'<article class="wrap blog-article"><a class="blog-back" href="/blog/">← Все статьи</a><h1>{e(post["title"])}</h1><time datetime="{e(post["date"])}">{date_label(post["date"])}</time>{byline}{updated}<p class="article-lead">{e(post["description"])}</p>{"".join(blocks)}<a class="blog-back" href="/blog/">← Вернуться в блог</a></article>'
        structured = {'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': post['title'], 'description': post['description'], 'datePublished': post['date'], 'inLanguage': 'ru-RU', 'mainEntityOfPage': ORIGIN + '/blog/' + post['slug'] + '/', 'publisher': {'@type': 'Organization', 'name': 'Needle Shark', 'url': ORIGIN + '/'}}
        structured['@id'] = ORIGIN + '/blog/' + post['slug'] + '/#article'
        structured['url'] = ORIGIN + '/blog/' + post['slug'] + '/'
        structured['publisher']['@id'] = ORIGIN + '/#organization'
        structured['publisher']['logo'] = ORIGIN + '/logo.svg'
        structured['citation'] = [item['url'] for block in post['blocks'] if block['type'] == 'sources' for item in block['items']]
        if post.get('author'):
            structured['author'] = {'@type': 'Person', 'name': post['author']}
        if post.get('updated'):
            structured['dateModified'] = post['updated']
        pages[f'{post["slug"]}/index.html'] = shell(body, post.get('seoTitle', post['title'] + ' — Needle Shark'), post.get('seoDescription', post['description']), slug=post['slug'], structured=structured)
    output.mkdir(parents=True, exist_ok=True)
    # Remove only obsolete HTML carrying this generator's ownership marker.
    marker = '<!-- Generated by blog/render.py -->'
    for old in output.glob('*/index.html'):
        if old.relative_to(output).as_posix() not in pages and old.read_text().startswith(marker):
            old.unlink()
    for name, html in pages.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prepare_html(marker + '\n' + html, 'blog/' + name))


def render_featured(posts, homepage):
    validate(posts)
    selected = sorted((p for p in posts if p['status'] == 'published' and p.get('featured', False)), key=lambda p: (p['date'], p['slug']), reverse=True)[:3]
    content = '<div class="popular-grid">' + ''.join(f'<article><h3><a href="/blog/{p["slug"]}/">{e(p["title"])}</a></h3><p>{e(p["description"])}</p></article>' for p in selected) + '</div>' if selected else '<p>Здесь появится подборка материалов из нашего блога.</p>'
    block = '<!-- BLOG_FEATURED_START -->\n<section class="wrap popular-articles" aria-labelledby="popular-heading"><div><h2 id="popular-heading">Популярные статьи</h2><a href="/blog/">Весь блог ↗</a></div>' + content + '</section>\n<!-- BLOG_FEATURED_END -->'
    source = homepage.read_text()
    pattern = r'<!-- BLOG_FEATURED_START -->.*?<!-- BLOG_FEATURED_END -->'
    if len(re.findall(pattern, source, flags=re.S)) != 1:
        raise ValueError('Expected one featured block in homepage')
    homepage.write_text(re.sub(pattern, lambda _: block, source, flags=re.S))


if __name__ == '__main__':
    posts = json.loads((ROOT / 'blog/posts.json').read_text())
    render(posts, ROOT / 'dist/blog')
    render_featured(posts, ROOT / 'dist/index.html')
