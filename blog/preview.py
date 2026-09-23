"""Render draft articles into an isolated, noindex local review; never publish it."""
import copy
import json
import re
import shutil
from pathlib import Path

from render import ROOT, render


def main():
    output = ROOT / 'outputs/blog-preview'
    shutil.copytree(ROOT / 'dist', output, dirs_exist_ok=True)
    posts = json.loads((ROOT / 'blog/posts.json').read_text())
    review = copy.deepcopy(posts)
    drafts = {post['slug'] for post in review if post['status'] == 'draft'}
    for post in review:
        post['status'] = 'published'
    render(review, output / 'blog')
    for page in output.rglob('*.html'):
        html = re.sub(r'<meta name="robots"[^>]*>', '<meta name="robots" content="noindex,nofollow">', page.read_text())
        html = re.sub(r'<script src="/metrika\.js[^\"]*"[^>]*></script>', '', html)
        html = re.sub(r'<noscript>.*?</noscript>', '', html, flags=re.S)
        if page.parent.name in drafts and page.parent.parent.name == 'blog':
            html = html.replace('<span>Опубликовано <time', '<span>Черновик от <time')
            html = html.replace('NEEDLE SHARK / ПРАКТИКА', 'NEEDLE SHARK / ЧЕРНОВИК ДЛЯ СОГЛАСОВАНИЯ')
            # A draft date is a preparation date, not an actual publication date.
            def without_publication_date(match):
                data = json.loads(match[1])
                if data.get('@type') == 'BlogPosting':
                    data.pop('datePublished', None)
                    data.pop('dateModified', None)
                return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'
            html = re.sub(r'<script type="application/ld\+json">(.*?)</script>', without_publication_date, html, flags=re.S)
        if page.relative_to(output).as_posix() == 'blog/index.html':
            html = html.replace('NEEDLE SHARK / БЛОГ', 'NEEDLE SHARK / ЛОКАЛЬНЫЙ ПРЕДПРОСМОТР')
        page.write_text(html)
    (output / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    # Do not expose a production sitemap as a draft review's index.
    (output / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>\n')
    print(f'Rendered {len(drafts)} draft article(s): {output}/blog/')
    print('No production analytics SDK. Serve with server/preview.py --directory outputs/blog-preview.')


if __name__ == '__main__':
    main()
