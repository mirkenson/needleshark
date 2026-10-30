"""Shared static publishing helpers; stdlib only."""
import hashlib
import json
import re
from html import escape, unescape
from pathlib import Path
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ORIGIN = 'https://needle-shark.ru'
HOSTS = {'needle-shark.ru', 'www.needle-shark.ru', 'needleshark.ru', 'www.needleshark.ru'}
ROOT = Path(__file__).resolve().parent
# Existing public ownership markers, restored from the approved pre-B2B homepage.
SEARCH_VERIFICATION = {
    'google-site-verification': 'z903IhTA3omVwH9fuJwzmF7enNlPvS2F6CxpqPID5U8',
    'yandex-verification': '02dc02f9a91882a9',
}


def json_ld(data, element_id=None):
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    identifier = f' id="{escape(element_id)}"' if element_id else ''
    return f'<script type="application/ld+json"{identifier}>{payload}</script>'


@lru_cache(maxsize=1)
def image_manifest():
    return json.loads((ROOT / 'ops/image-manifest.json').read_text())


def image_attributes(source, sizes='100vw', thumbnail=False):
    """Use checked-in derivatives with measured dimensions, never guessed ones."""
    entry = image_manifest().get('/' + source.lstrip('/'))
    if not entry:
        raise ValueError('Missing optimized image; run ops/optimize-images.py: ' + source)
    variants = entry['variants']
    if thumbnail:
        variants = variants[:1]
    default = next((item for item in variants if item['width'] >= 800), variants[-1])
    return {'src': default['src'], 'width': entry['width'], 'height': entry['height'],
            'srcset': ', '.join(f'{item["src"]} {item["width"]}w' for item in variants), 'sizes': sizes}


def breadcrumbs(items):
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList',
            '@id': ORIGIN + items[-1][1] + '#breadcrumb',
            'itemListElement': [{'@type': 'ListItem', 'position': index + 1, 'name': name,
                                 'item': ORIGIN + path} for index, (name, path) in enumerate(items)]}


def schema_nodes(value):
    """Walk JSON-LD objects, including nested lists and graph nodes."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


def image_object(url, alt, width, height, identifier):
    return {'@type': 'ImageObject', '@id': identifier, 'url': url, 'contentUrl': url,
            'caption': alt, 'width': width, 'height': height, 'encodingFormat': 'image/webp'}


def common_metadata(html, path):
    """One idempotent source for icons, social tags and site identity on every page."""
    html = re.sub(r'<!-- SITE_METADATA_START -->.*?<!-- SITE_METADATA_END -->', '', html, flags=re.S)
    title_match = re.search(r'<title>(.*?)</title>', html, re.S)
    if not title_match:
        return html
    title = unescape(title_match[1])
    description_match = re.search(r'<meta name="description" content="([^"]*)"', html)
    description = unescape(description_match[1]) if description_match else title
    url = ORIGIN + public_path(path)
    # These tags are owned by this function, including older generator output.
    html = re.sub(r'<meta\b[^>]*(?:property="og:[^"]+"|name="(?:twitter:[^"]+|robots|theme-color)")[^>]*>', '', html)
    html = re.sub(r'<link\b[^>]*rel="(?:icon|shortcut icon|apple-touch-icon|manifest)"[^>]*>', '', html)
    article = any(public_path(path).startswith(section) and public_path(path) != section for section in ('/blog/', '/cases/'))
    image_url, image_alt = ORIGIN + '/brand-preview.png', 'Needle Shark'
    image_width, image_height, image_type = 1200, 630, 'image/png'
    nodes = [node for raw in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S) for node in schema_nodes(json.loads(raw))]
    primary = next((n for n in nodes if n.get('@type') == 'ImageObject' and n.get('@id') == url + '#primaryimage'), None)
    # Legacy product pages keep their own product image; current pages supply an explicit image.
    for payload in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        data = json.loads(payload)
        if data.get('@type') == 'Product' and data.get('image'):
            image_url, image_alt = data['image'][0], data['name']
            variant = next(v for entry in image_manifest().values() for v in entry['variants'] if ORIGIN + v['src'] == image_url)
            image_width, image_height, image_type = variant['width'], variant['height'], 'image/webp'
            break
    if primary:
        image_url, image_alt = primary['url'], primary['caption']
        image_width, image_height, image_type = primary['width'], primary['height'], primary['encodingFormat']
    tags = [
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta name="theme-color" content="#BE3E3E">',
        '<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">',
        '<link rel="icon" href="/favicon-96.png" type="image/png" sizes="96x96">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml" sizes="any">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">',
        '<link rel="manifest" href="/site.webmanifest">',
    ]
    if public_path(path) == '/':
        # Own these tags on the homepage, including old tags outside our block.
        html = re.sub(r'<meta\b[^>]*name=[\"\'](?:google-site-verification|yandex-verification)[\"\'][^>]*>', '', html, flags=re.I)
        tags.extend(f'<meta name="{name}" content="{value}">' for name, value in SEARCH_VERIFICATION.items())
    social = {'og:title': title, 'og:description': description, 'og:url': url,
              'og:type': 'article' if article else 'website', 'og:locale': 'ru_RU',
              'og:site_name': 'Needle Shark', 'og:image': image_url,
              'og:image:alt': image_alt, 'og:image:width': str(image_width), 'og:image:height': str(image_height),
              'og:image:type': image_type,
              'twitter:card': 'summary_large_image', 'twitter:title': title, 'twitter:description': description,
              'twitter:image': image_url, 'twitter:image:alt': image_alt}
    for key, value in social.items():
        attr = 'property' if key.startswith('og:') else 'name'
        tags.append(f'<meta {attr}="{key}" content="{escape(value, quote=True)}">')
    organization = {'@type': 'Organization', '@id': ORIGIN + '/#organization',
                    'name': 'Needle Shark', 'url': ORIGIN + '/', 'logo': ORIGIN + '/logo.svg',
                    'email': 'sales@neesha.ru', 'telephone': '+79312448245', 'sameAs': ['https://vk.ru/needleshark'],
                    'address': {'@type': 'PostalAddress', 'addressLocality': 'Санкт-Петербург', 'addressCountry': 'RU'}}
    website = {'@type': 'WebSite', '@id': ORIGIN + '/#website', 'url': ORIGIN + '/',
               'name': 'Needle Shark', 'inLanguage': 'ru-RU', 'publisher': {'@id': organization['@id']}}
    webpage = {'@type': 'WebPage', '@id': url + '#webpage', 'url': url, 'name': title,
               'description': description, 'inLanguage': 'ru-RU', 'isPartOf': {'@id': website['@id']},
               'publisher': {'@id': organization['@id']}}
    if primary:
        webpage['primaryImageOfPage'] = {'@id': primary['@id']}
    trail = next((n for n in nodes if n.get('@type') == 'BreadcrumbList'), None)
    if trail and trail.get('@id'):
        webpage['breadcrumb'] = {'@id': trail['@id']}
    main = next((n for n in nodes if n.get('@type') in ('Service', 'BlogPosting', 'Article') and n.get('url') == url), None)
    if main:
        webpage['mainEntity'] = {'@id': main['@id']}
    tags.append(json_ld({'@context': 'https://schema.org', '@graph': [organization, website, webpage]}, 'site-schema'))
    block = '<!-- SITE_METADATA_START -->' + '\n'.join(tags) + '<!-- SITE_METADATA_END -->'
    return '\n'.join(line.rstrip() for line in html.replace('</head>', block + '</head>').split('\n'))

def public_path(path):
    path = '/' + str(path).lstrip('/')
    return path.removesuffix('index.html') if path.endswith('/index.html') else path.removesuffix('.html')


def external_url(url, content):
    """Tag external links, including variant URLs that are selected in JavaScript."""
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.hostname in HOSTS:
        return url
    query = parse_qsl(parsed.query, keep_blank_values=True)
    ozon = parsed.hostname == 'ozon.ru' or (parsed.hostname or '').endswith('.ozon.ru')
    if ozon:
        normalized, campaign_seen = [], False
        for key, value in query:
            if key.lower() == 'utm_campaign':
                if not campaign_seen:
                    normalized.append(('utm_campaign', 'vendor_org_211216'))
                    campaign_seen = True
            else:
                normalized.append((key, value))
        query = normalized
    keys = {key for key, value in query}
    campaign = 'vendor_org_211216' if ozon else 'website'
    for key, value in [('utm_source', urlsplit(ORIGIN).hostname), ('utm_medium', 'referral'),
                       ('utm_campaign', campaign), ('utm_content', content)]:
        if key not in keys:
            query.append((key, value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))

def prepare_html(html, path):
    # One shared pixel, versioned and idempotent across all renderers.
    html = re.sub(r'<script\b[^>]*\bsrc="/vk-pixel\.js(?:\?[^"<>]*)?"[^>]*>\s*</script>', '', html)
    pixel_version = hashlib.sha256((ROOT / 'dist/vk-pixel.js').read_bytes()).hexdigest()[:12]
    html = html.replace('</head>', f'<script src="/vk-pixel.js?v={pixel_version}" defer></script></head>')
    canonical = ORIGIN + public_path(path)
    canonical_tag = f'<link rel="canonical" href="{canonical}">'
    def remove_canonical(match):
        rel = re.search(r"""\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", match[0], re.I)
        return '' if rel and 'canonical' in next(v for v in rel.groups() if v is not None).lower().split() else match[0]
    html = re.sub(r'<link\b[^>]*>', remove_canonical, html, flags=re.I)
    html = html.replace('</head>', canonical_tag + '</head>')
    def anchor(match):
        tag = match.group()
        href = re.search(r'\bhref="([^"]*)"', tag)
        if not href:
            return tag
        url = unescape(href.group(1))
        parsed = urlsplit(url)
        if (not parsed.scheme and not parsed.netloc) or parsed.hostname in HOSTS:
            # Avoid duplicate internal .html/index.html URLs without changing route identity.
            clean_path = public_path(parsed.path) if parsed.path.startswith('/') else parsed.path
            updated = urlunsplit((parsed.scheme, parsed.netloc, clean_path, parsed.query, parsed.fragment))
            return tag[:href.start(1)] + escape(updated, quote=True) + tag[href.end(1):]
        if parsed.scheme not in ('http', 'https'):
            return tag
        track = re.search(r'\bdata-track="([^"]+)"', tag)
        content = track.group(1) if track else public_path(path).strip('/').replace('/', '_') + '_' + hashlib.sha256((parsed.hostname + parsed.path).encode()).hexdigest()[:8]
        updated = external_url(url, content)
        return tag[:href.start(1)] + escape(updated, quote=True) + tag[href.end(1):]
    return common_metadata(re.sub(r'<a\b[^>]*>', anchor, html), path)
