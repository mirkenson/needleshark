"""Text-only LOOP notifications. Secrets and provider responses never enter logs."""
from datetime import datetime
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from lead_context import BUSINESS_LABELS, INQUIRY_LABELS


def webhook_url(value=None):
    value = os.environ.get('LOOP_LEADS_WEBHOOK_URL', '') if value is None else value
    if not value:
        return None
    # One owner-approved workspace; no credentials/query/redirect to another destination.
    if not re.fullmatch(r'https://neesha\.loop\.ru/hooks/[a-z0-9]{26}', value):
        raise ValueError('Invalid LOOP webhook configuration')
    return value


def message(lead):
    received = datetime.fromisoformat(lead['created_at'].replace('Z', '+00:00'))
    when = received.astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S МСК')
    path = lead.get('source_path')
    if path and not re.fullmatch(r'/(?:[a-z0-9-]+/)*', path):
        path = None
    form = {'/': 'Главная — «Что нужно изготовить?»',
            '/business/': 'Для бизнеса — заявка',
            '/catalog/': 'Каталог — форма обращения'}.get(path)
    if not form and path and path.startswith('/catalog/'):
        form = 'Карточка товара — форма обращения'
    lines = [f'Время: {when}', f'Контакт: {lead["contact"]}', f'Имя: {lead["name"]}']
    if lead.get('business_company'):
        lines.append('Компания / сфера: ' + lead['business_company'])
    lines.append('Товар: ' + (lead.get('product_name') or 'Не выбран — см. текст обращения'))
    if lead.get('business_intent'):
        lines.append('Направление: ' + BUSINESS_LABELS[lead['business_intent']])
    lines.append('Тип обращения: ' + INQUIRY_LABELS.get(lead.get('inquiry_type'), 'Общий вопрос / консультация'))
    for key, label in [('product_size', 'Размер, см'), ('quantity', 'Количество, шт.'),
                       ('product_slug', 'Код товара')]:
        if lead.get(key) is not None and lead.get(key) != '':
            lines.append(f'{label}: {lead[key]}')
    lines += ['Форма: ' + (form or 'Не передана'),
              'Страница: ' + ('https://needle-shark.ru' + path if path else 'Не передана'),
              '', 'Текст обращения:', lead['question']]
    if lead.get('attachment'):
        lines += ['', 'К заявке приложен файл. Он отправляется только по почте.']
    # Indent every line as literal code: visitor text cannot become mentions, images,
    # misleading Markdown links or close a fenced block. Preserve exact contact text.
    literal = '\n'.join('    ' + line for line in '\n'.join(lines).splitlines())
    return {'text': '**Новая заявка Needle Shark**\nНомер: ' + lead['id'] + '\n\n' + literal,
            'skip_slack_parsing': True}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(lead, url):
    url = webhook_url(url)
    if not url:
        raise ValueError('LOOP webhook missing')
    request = urllib.request.Request(url, data=json.dumps(message(lead), ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'NeedleShark-Leads/1.0'}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=15) as response:
            # A login page or an ambiguous 2xx is not a delivery acknowledgement.
            if response.status != 200 or response.read(1024).strip() != b'ok':
                raise RuntimeError('loop_unconfirmed')
    except urllib.error.HTTPError as error:
        error.close()
        raise


def error_code(error):
    if isinstance(error, urllib.error.HTTPError):
        return 'loop_http_' + str(error.code)
    if isinstance(error, (urllib.error.URLError, TimeoutError, OSError)):
        return 'loop_network_error'
    return 'loop_delivery_error'
