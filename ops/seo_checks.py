"""Independent checks of the public URL contract and rendered metadata."""
import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://needle-shark.ru'
ALIASES = {'www.needle-shark.ru', 'needleshark.ru', 'www.needleshark.ru', 'neesha.ru'}


def text(value):
    return ' '.join(unescape(re.sub('<[^>]+>', ' ', value)).split())


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


class Metadata(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.head = False
        self.tags, self.schemas, self.ids, self.images = [], [], set(), set()
        self.script = None
        self.feed(source)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == 'head':
            self.head = True
        self.tags.append((tag, attrs, self.head))
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'img':
            self.images.add(attrs.get('src'))
            self.images.update(s.strip().split()[0] for s in attrs.get('srcset', '').split(',') if s.strip())
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.script = [self.head, '']

    def handle_data(self, value):
        if self.script is not None:
            self.script[1] += value

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.schemas.append((self.script[0], json.loads(self.script[1])))
            self.script = None
        if tag == 'head':
            self.head = False

    def meta(self, field):
        return [(inside, a.get('content')) for tag, a, inside in self.tags
                if tag == 'meta' and (a.get('name') == field or a.get('property') == field)]


def registry():
    records = json.loads((ROOT / 'ops/page-registry.json').read_text())['pages']
    assert len({p['file'] for p in records}) == len(records), 'Duplicate registry file'
    assert len({p['canonical'] for p in records}) == len(records), 'Duplicate registry canonical'
    for p in records:
        parsed = urlsplit(p['canonical'])
        assert parsed.scheme == 'https' and parsed.netloc == 'needle-shark.ru' and not parsed.query and not parsed.fragment, p
        assert p['url'] == p['canonical'] and p['purpose'] and p['action'], p
    return records


def check_inventory(dist, records=None):
    records = registry() if records is None else records
    expected = {p['file'] for p in records}
    actual = {p.relative_to(dist).as_posix() for p in dist.rglob('*.html')}
    assert actual == expected, f'Public route inventory: missing={sorted(expected-actual)}, unknown={sorted(actual-expected)}'


def check_page(record, page, all_pages, dist):
    url = record['canonical']
    canonical = [(inside, a.get('href')) for tag, a, inside in page.tags
                 if tag == 'link' and 'canonical' in a.get('rel', '').lower().split()]
    assert canonical == [(True, url)], f'{url}: exactly one self-canonical in head'
    titles = re.findall(r'<title>(.*?)</title>', page.source, re.S)
    assert [unescape(t) for t in titles] == [record['title']], f'{url}: title contract'
    assert [(inside) for tag, _, inside in page.tags if tag == 'title'] == [True], f'{url}: title outside head'
    h1 = re.findall(r'<h1\b[^>]*>(.*?)</h1>', page.source, re.S)
    assert [text(h) for h in h1] == [record['h1']], f'{url}: H1 contract'
    for key, expected in [('description', record['description']), ('og:url', url), ('og:title', record['title']),
                          ('og:description', record['description']), ('twitter:title', record['title']),
                          ('twitter:description', record['description']), ('og:image', record['image']),
                          ('twitter:image', record['image'])]:
        assert page.meta(key) == [(True, expected)], f'{url}: {key}'
    assert page.meta('robots') == [(True, 'index,follow,max-image-preview:large')], f'{url}: robots'
    assert record['indexable'], f'{url}: unexpected noindex policy'
    assert all(inside for inside, _ in page.schemas), f'{url}: JSON-LD outside head'
    graph = [n for _, value in page.schemas for n in nodes(value)]
    types = {n.get('@type') for n in graph if isinstance(n.get('@type'), str)}
    assert set(record['schema_types']) <= types, f'{url}: missing schema {set(record["schema_types"])-types}'
    assert not types & {'Offer', 'AggregateRating', 'Review', 'Product'}, f'{url}: inappropriate commerce schema'
    web = [n for n in graph if n.get('@type') == 'WebPage']
    assert len(web) == 1 and web[0]['@id'] == url + '#webpage' and web[0]['url'] == url, f'{url}: WebPage identity'
    assert web[0]['name'] == record['title'] and web[0]['description'] == record['description']
    entity_ids = {n['@id'] for n in graph if '@id' in n and len(n) > 1}
    for n in graph:
        for key in ('@id', 'url', 'contentUrl', 'mainEntityOfPage', 'citation', 'image', 'logo', 'item'):
            values = n.get(key, [])
            for value in values if isinstance(values, list) else [values]:
                if not isinstance(value, str):
                    continue
                parsed = urlsplit(value)
                assert parsed.hostname not in ALIASES, f'{url}: alias in schema {value}'
                if parsed.hostname != 'needle-shark.ru' and not value.startswith('/'):
                    continue
                assert value.startswith(ORIGIN + '/') and not parsed.query, f'{url}: noncanonical schema URL {value}'
                base = ORIGIN + parsed.path
                if base in all_pages:
                    if parsed.fragment:
                        assert value in entity_ids or parsed.fragment in all_pages[base].ids, f'{url}: unknown schema fragment {value}'
                else:
                    assert (dist / parsed.path.lstrip('/')).is_file(), f'{url}: missing schema destination {value}'
    primary = [n for n in graph if n.get('@type') == 'ImageObject' and n.get('@id') == url + '#primaryimage']
    if 'ImageObject' in record['schema_types']:
        assert len(primary) == 1, f'{url}: primary image'
        photo = primary[0]
        assert photo['url'] == photo['contentUrl'] == record['image'], f'{url}: inconsistent image'
        assert urlsplit(photo['url']).path in page.images, f'{url}: schema image not visible on page'
        for prop in ('width', 'height'):
            assert isinstance(photo[prop], int) and photo[prop] > 0
            assert page.meta('og:image:' + prop) == [(True, str(photo[prop]))]
        assert page.meta('og:image:alt') == page.meta('twitter:image:alt') == [(True, photo['caption'])]
        assert web[0]['primaryImageOfPage'] == {'@id': photo['@id']}
    services = [n for n in graph if n.get('@type') == 'Service']
    if 'Service' in record['schema_types']:
        assert len(services) == 1, f'{url}: Service count'
        service = services[0]
        assert service['url'] == url and service['@id'] == url + '#service'
        assert service['description'] == record['description'] and service['name'] in text(page.source)
        assert service['provider'] == {'@id': ORIGIN + '/#organization'}
        assert web[0]['mainEntity'] == {'@id': service['@id']}
    for trail in (n for n in graph if n.get('@type') == 'BreadcrumbList'):
        items = trail['itemListElement']
        assert [i['position'] for i in items] == list(range(1,len(items)+1)) and len(items) >= 2
        assert items[-1]['item'] == url and trail['@id'] == url + '#breadcrumb'
        assert web[0]['breadcrumb'] == {'@id': trail['@id']}
    if 'CollectionPage' in record['schema_types']:
        collections = [n for n in graph if n.get('@type') == 'CollectionPage']
        assert len(collections) == 1 and collections[0]['@id'] == url + '#webpage' and collections[0]['url'] == url
        listing = collections[0]['mainEntity']
        if url.endswith('/catalog/'):
            visible = [(ORIGIN + '/catalog/#' + slug, text(name)) for slug, name in re.findall(r'<article class="ns-product" id="([^"]+)".*?<h2>(.*?)</h2>', page.source, re.S)]
        elif url.endswith('/cases/'):
            visible = [(ORIGIN + href, text(name)) for href, name in re.findall(r'<article class="ns-case-card".*?<h2><a href="([^"]+)"[^>]*>(.*?)</a>', page.source, re.S)]
        else:
            visible = [(ORIGIN + href, text(name).removesuffix(' ↗')) for href, name in re.findall(r'<article class="blog-card".*?<h2><a href="([^"]+)"[^>]*>(.*?)</a>', page.source, re.S)]
        items = listing['itemListElement']
        assert [(i['url'],i['name']) for i in items] == visible and visible, f'{url}: ItemList differs from visible cards'
        assert listing['numberOfItems'] == len(visible) and [i['position'] for i in items] == list(range(1,len(items)+1))
    for article in (n for n in graph if n.get('@type') == 'BlogPosting'):
        assert article['url'] == article['mainEntityOfPage'] == url
        assert article['headline'] == record['h1'] and article['image'] == primary[0]
        dates = re.findall(r'<time datetime="([^"]+)"', page.source)
        assert article['datePublished'] in dates and article.get('dateModified', article['datePublished']) in dates
        if article.get('author'):
            assert article['author']['name'] in text(page.source.split('</head>')[1]), f'{url}: invisible author'


def check_metadata(dist):
    records = registry()
    check_inventory(dist, records)
    pages = {r['canonical']: Metadata((dist / r['file']).read_text()) for r in records}
    for record in records:
        check_page(record, pages[record['canonical']], pages, dist)
    assert len({r['title'] for r in records}) == len(records), 'Duplicate titles'
    assert len({r['description'] for r in records}) == len(records), 'Duplicate descriptions'
    return records
