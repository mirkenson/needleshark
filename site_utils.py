"""Shared static publishing helpers; stdlib only."""
import hashlib
import re
from html import escape, unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ORIGIN = 'https://needleshark.ru'
HOSTS = {'needleshark.ru', 'www.needleshark.ru'}

def public_path(path):
    path = '/' + str(path).lstrip('/')
    return path.removesuffix('index.html') if path.endswith('/index.html') else path.removesuffix('.html')

def prepare_html(html, path):
    canonical = ORIGIN + public_path(path)
    if not re.search(r'<link\b[^>]*rel="canonical"', html):
        html = html.replace('</head>', f'<link rel="canonical" href="{canonical}"></head>')
    def anchor(match):
        tag = match.group()
        href = re.search(r'\bhref="([^"]*)"', tag)
        if not href:
            return tag
        url = unescape(href.group(1))
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or parsed.hostname in HOSTS:
            return tag
        query = parse_qsl(parsed.query, keep_blank_values=True)
        keys = {key for key, value in query}
        track = re.search(r'\bdata-track="([^"]+)"', tag)
        content = track.group(1) if track else public_path(path).strip('/').replace('/', '_') + '_' + hashlib.sha256((parsed.hostname + parsed.path).encode()).hexdigest()[:8]
        for key, value in [('utm_source','needleshark.ru'),('utm_medium','referral'),('utm_campaign','website'),('utm_content',content)]:
            if key not in keys:
                query.append((key, value))
        updated = urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),parsed.fragment))
        return tag[:href.start(1)] + escape(updated, quote=True) + tag[href.end(1):]
    return re.sub(r'<a\b[^>]*>', anchor, html)
