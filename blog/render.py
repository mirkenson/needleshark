"""Build the blog from approved structured text, using only Python's stdlib."""
import json
import sys
import re
from datetime import date
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from site_utils import prepare_html, ORIGIN, json_ld, breadcrumbs, image_manifest, image_object
from blog.blocks import ArticleBlocks, e, validate_blocks, walk, catalog_image, editorial_images, figure

BASE = Template((ROOT / 'blog/base.html').read_text())


def validate(posts):
    slugs = set()
    for post in posts:
        slug = post['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in slugs:
            raise ValueError('Article slugs must be unique lowercase URL segments')
        slugs.add(slug)
        if post.get('kind', 'article') not in ('article', 'case'):
            raise ValueError('Unknown article kind')
        if post.get('kind') == 'case':
            from blog.blocks import require_text, safe_url
            require_text(post['case'], 'label', 'category', 'summary', 'cta', 'ctaUrl', 'note')
            if not safe_url(post['case']['ctaUrl']) or post['blocks'][0]['type'] != 'image':
                raise ValueError('A case requires a leading image and a safe CTA')
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
        validate_blocks(post['blocks'])
        article_image(post)  # An explicit social image must already be visible in the article.


def article_image(post):
    selection = post.get('seoImage')
    if selection is None:
        return None
    block = next((b for b in walk(post['blocks']) if b['type'] == 'image' and
                  all(b.get(key) == selection.get(key) for key in ('product', 'image', 'asset'))), None) if isinstance(selection, dict) else None
    if block is None:
        raise ValueError('seoImage must select an image already used in this article')
    source = catalog_image(block)
    photo = (editorial_images()[block['asset']] if 'asset' in block else image_manifest()['/' + source['src'].lstrip('/')])['variants'][-1]
    return image_object(ORIGIN + photo['src'], source['alt'], photo['width'], photo['height'],
                        ORIGIN + '/blog/' + post['slug'] + '/#primaryimage')


def shell(content, title, description, current='false', slug=None, structured=None, case=False):
    metadata = ''  # Common canonical/social/icon metadata comes from prepare_html.
    if structured:
        metadata += json_ld(structured)
    trail = [('Главная', '/'), ('Кейсы', '/cases/') if case else ('Блог', '/blog/')]
    if slug:
        trail.append((structured['headline'], '/blog/' + slug + '/'))
    metadata += json_ld(breadcrumbs(trail))
    return BASE.substitute(content=content, title=e(title), description=e(description), blog_current=current, metadata=metadata)


def date_label(value):
    return date.fromisoformat(value).strftime('%d.%m.%Y')


def date_markup(post):
    if post['status'] == 'draft':
        return '<span>Черновик</span>'
    return f'<time datetime="{e(post["date"])}">{date_label(post["date"])}</time>'


def render(posts, output, include_drafts=False):
    validate(posts)  # Validate everything before modifying generated files.
    published = sorted((p for p in posts if p['status'] == 'published' or (include_drafts and p.get('kind') == 'case')), key=lambda p: (p['date'], p['slug']), reverse=True)
    intro = '<section class="wrap blog-intro"><p class="eyebrow">NEEDLE SHARK / БЛОГ</p><h1>Блог<span class="title-dot">.</span></h1><p>О материалах, изделиях и работе производства.</p></section>'
    cards = ''.join(f'<article class="blog-card">{date_markup(p)}<div><h2><a href="/blog/{p["slug"]}/">{e(p["title"])} <span aria-hidden="true">↗</span></a></h2><p>{e(p["description"])}</p></div></article>' for p in published)
    collection = f'<section class="wrap blog-list" aria-label="Статьи">{cards}</section>' if cards else '<section class="wrap blog-empty" aria-labelledby="empty-title"><h2 id="empty-title">Здесь появятся<br>первые статьи.</h2><div><p>Публикаций пока нет. А познакомиться с нашими изделиями можно уже сейчас.</p><a href="/catalog/">Перейти в каталог <span aria-hidden="true">↗</span></a></div></section>'
    blog_schema = {'@context': 'https://schema.org', '@type': 'CollectionPage', '@id': ORIGIN + '/blog/#webpage',
                   'url': ORIGIN + '/blog/', 'mainEntity': {'@type': 'ItemList', '@id': ORIGIN + '/blog/#items', 'numberOfItems': len(published), 'itemListElement': [
                       {'@type': 'ListItem', 'position': i + 1, 'name': post['title'],
                        'url': ORIGIN + '/blog/' + post['slug'] + '/'} for i, post in enumerate(published)]}}
    pages = {'index.html': shell(intro + collection, 'Блог о чехлах, материалах и хранении техники | Needle Shark', 'Статьи Needle Shark о защитных чехлах, технических тканях и уходе за техникой. Подготовка мотоцикла и квадроцикла к зимнему хранению.', 'page', structured=blog_schema)}
    for post in published:
        article = ArticleBlocks(post)
        is_case = post.get('kind') == 'case'
        content = article.render(post['blocks'][1:] if is_case else post['blocks'])
        byline = f'<p class="article-author">Автор: {e(post["author"])}</p>' if post.get('author') else ''
        updated = f'<p class="article-updated">Обновлено: <time datetime="{e(post["updated"])}">{date_label(post["updated"])}</time></p>' if post.get('updated') else ''
        meta = f'<div class="article-meta"><span>Опубликовано <time datetime="{e(post["date"])}">{date_label(post["date"])}</time></span>{byline}{updated}</div>'
        body = f'<article class="wrap blog-article" data-article="{e(post["slug"])}"><a class="blog-back" href="/blog/">← Все статьи</a><div class="article-header"><p class="eyebrow">NEEDLE SHARK / ПРАКТИКА</p><h1>{e(post["title"])}</h1>{meta}<p class="article-lead">{e(post["description"])}</p></div><div class="article-layout">{article.contents()}<div class="article-body">{content}{article.footnotes()}<a class="blog-back" href="/blog/">← Вернуться в блог</a></div></div></article>'
        if post['status'] == 'draft':
            meta = f'<div class="article-meta">Прототип для согласования · {date_label(post["date"])}</div>'
        if is_case:
            case = post['case']
            hero_cta = f'<div class="case-hero-actions"><a class="ns-button" href="{e(case["ctaUrl"])}" data-blog-cta="case-hero" data-article="{e(post["slug"])}">{e(case["cta"])} <span aria-hidden="true">↗</span></a><p>{e(case["note"])}</p></div>'
            body = f'<article class="wrap blog-article case-article" data-article="{e(post["slug"])}"><a class="blog-back" href="/cases/">← Все кейсы</a><div class="case-hero"><div class="article-header"><p class="eyebrow">NEEDLE SHARK / КЕЙС</p><h1>{e(post["title"])}</h1><p class="article-lead">{e(post["description"])}</p>{hero_cta}{meta}</div>{figure(post["blocks"][0], eager=True)}</div><div class="article-layout">{article.contents().replace("В этой статье", "В этом кейсе")}<div class="article-body">{content}{article.footnotes()}<a class="blog-back" href="/cases/">← Все кейсы Needle Shark</a></div></div></article>'
        structured = {'@context': 'https://schema.org', '@type': 'BlogPosting' , 'headline': post['title'], 'description': post['description'], 'datePublished': post['date'], 'inLanguage': 'ru-RU', 'mainEntityOfPage': ORIGIN + '/blog/' + post['slug'] + '/', 'publisher': {'@type': 'Organization', 'name': 'Needle Shark', 'url': ORIGIN + '/'}}
        structured['@id'] = ORIGIN + '/blog/' + post['slug'] + '/#article'
        structured['url'] = ORIGIN + '/blog/' + post['slug'] + '/'
        structured['publisher']['@id'] = ORIGIN + '/#organization'
        structured['publisher']['logo'] = ORIGIN + '/logo.svg'
        structured['citation'] = list(dict.fromkeys(item['url'] for block in walk(post['blocks']) if block['type'] == 'sources' for item in block['items']))
        photo = article_image(post)
        if photo:
            structured['image'] = photo
        if post.get('author'):
            structured['author'] = {'@type': 'Person', 'name': post['author']}
        if post.get('updated'):
            structured['dateModified'] = post['updated']
        if post['status'] == 'draft':
            structured.pop('datePublished', None)
            structured.pop('dateModified', None)
        pages[f'{post["slug"]}/index.html'] = shell(body, post.get('seoTitle', post['title'] + ' — Needle Shark'), post.get('seoDescription', post['description']), slug=post['slug'], structured=structured, case=is_case)
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
    selected = sorted((p for p in posts if p['status'] == 'published'), key=lambda p: (p['date'], p['slug']), reverse=True)[:3]
    content = '<div class="popular-grid">' + ''.join(f'<article><h3><a href="/blog/{p["slug"]}/">{e(p["title"])}</a></h3><p>{e(p["description"])}</p></article>' for p in selected) + '</div>' if selected else '<p>Здесь появится подборка материалов из нашего блога.</p>'
    block = '<!-- BLOG_FEATURED_START -->\n<section class="wrap popular-articles" aria-labelledby="popular-heading"><div><h2 id="popular-heading">Полезные материалы</h2><a href="/blog/">Весь блог ↗</a></div>' + content + '</section>\n<!-- BLOG_FEATURED_END -->'
    source = homepage.read_text()
    pattern = r'<!-- BLOG_FEATURED_START -->.*?<!-- BLOG_FEATURED_END -->'
    if len(re.findall(pattern, source, flags=re.S)) != 1:
        raise ValueError('Expected one featured block in homepage')
    homepage.write_text(re.sub(pattern, lambda _: block, source, flags=re.S))


if __name__ == '__main__':
    from b2b.config import ENABLED
    if ENABLED:
        from b2b.render import publish
        publish()
    else:
        posts = json.loads((ROOT / 'blog/posts.json').read_text())
        render(posts, ROOT / 'dist/blog')
        render_featured(posts, ROOT / 'dist/index.html')
