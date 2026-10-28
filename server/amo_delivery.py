"""Private amoCRM API delivery. No browser credentials, files or public secrets.

Create requests are fenced in PostgreSQL before the network call. An ambiguous
response is reconciled by the permanent submission UUID, never blindly replayed.
"""
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from lead_context import UTM_FIELDS, notification_payload, BUSINESS_LABELS, DIRECTION_LABELS


class DeliveryError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def enabled():
    return os.environ.get('AMO_ENABLED') == '1'


def configuration(env=None):
    env = os.environ if env is None else env
    if env.get('AMO_ENABLED') != '1':
        return None
    base = env.get('AMO_BASE_URL', '')
    if not re.fullmatch(r'https://[a-z0-9][a-z0-9-]*\.amocrm\.ru', base):
        raise DeliveryError('amo_config_host')
    token = env.get('AMO_ACCESS_TOKEN', '')
    if not re.fullmatch(r'[A-Za-z0-9._-]{32,16384}', token):
        raise DeliveryError('amo_config_token')
    result = {'base': base, 'token': token}
    for key in ('PIPELINE_ID', 'STATUS_ID', 'SUBMISSION_FIELD_ID', 'DETAILS_FIELD_ID', 'ORDER_FIELD_ID'):
        value = env.get('AMO_' + key, '')
        if not re.fullmatch(r'[1-9][0-9]{0,18}', value):
            raise DeliveryError('amo_config_ids')
        result[key.lower()] = int(value)
    if env.get('AMO_RESPONSIBLE_ID'):
        value = env['AMO_RESPONSIBLE_ID']
        if not re.fullmatch(r'[1-9][0-9]{0,18}', value):
            raise DeliveryError('amo_config_ids')
        result['responsible_id'] = int(value)
    result['structured'] = env.get('AMO_STRUCTURED_FIELDS') == '1'
    if result['structured']:
        value = env.get('AMO_SOURCE_FIELD_ID', '')
        if not re.fullmatch(r'[1-9][0-9]{0,18}', value):
            raise DeliveryError('amo_config_ids')
        result['source_field_id'] = int(value)
    return result


class Client:
    def __init__(self, config):
        self.config = config
        self.last_request = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(self, method, path, payload=None):
        if not path.startswith('/api/v4/') or any(c in path for c in ('\r', '\n', '#')):
            raise DeliveryError('amo_invalid_path')
        time.sleep(max(0, .25 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = urllib.request.Request(self.config['base'] + path, method=method,
            data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(),
            headers={'Authorization': 'Bearer ' + self.config['token'],
                     'Content-Type': 'application/json', 'Accept': 'application/json',
                     'User-Agent': 'NeedleShark-Leads/1.0'})
        try:
            with self.opener.open(request, timeout=20) as response:
                if response.status == 204 and method == 'GET':
                    return {}
                if response.status not in (200, 201):
                    raise DeliveryError('amo_invalid_response')
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise DeliveryError('amo_response_too_large')
                data = json.loads(raw)
                if not isinstance(data, (dict, list)):
                    raise ValueError()
                return data
        except urllib.error.HTTPError as error:
            # Do not read or log provider bodies, URLs, contact details or tokens.
            error.close()
            raise DeliveryError('amo_http_' + str(error.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise DeliveryError('amo_network_error') from None
        except (ValueError, UnicodeError):
            raise DeliveryError('amo_invalid_response') from None

    def list(self, entity, params):
        # Bounded traversal; never follow provider-supplied URLs with our token.
        collection = entity.rsplit('/', 1)[-1]
        for page in range(1, 11):
            query = urllib.parse.urlencode(dict(params, page=page, limit=250))
            data = self.request('GET', '/api/v4/' + entity + '?' + query)
            if not isinstance(data, dict) or (data and collection not in data.get('_embedded', {})):
                raise DeliveryError('amo_invalid_response')
            rows = data.get('_embedded', {}).get(collection, [])
            if not isinstance(rows, list):
                raise DeliveryError('amo_invalid_response')
            yield from rows
            if not data.get('_links', {}).get('next'):
                return
        raise DeliveryError('amo_search_limit')


def preflight(config):
    """Read-only account, pipeline and field validation before first activation."""
    client = Client(config)
    account = client.request('GET', '/api/v4/account')
    if 'https://' + account.get('subdomain', '') + '.amocrm.ru' != config['base']:
        raise DeliveryError('amo_account_mismatch')
    pipeline = client.request('GET', '/api/v4/leads/pipelines/' + str(config['pipeline_id']))
    if not any(s['id'] == config['status_id'] for s in pipeline.get('_embedded', {}).get('statuses', [])):
        raise DeliveryError('amo_status_missing')
    fields = list(client.list('leads/custom_fields', {}))
    types = {f['id']: f['type'] for f in fields}
    for setting, expected in [('submission_field_id', 'text'), ('details_field_id', 'textarea'), ('order_field_id', 'text')]:
        if types.get(config[setting]) != expected:
            raise DeliveryError('amo_field_mismatch')
    if config.get('structured'):
        if types.get(config['source_field_id']) != 'text':
            raise DeliveryError('amo_field_mismatch')
        actual = {f.get('code'): f['type'] for f in fields}
        if any(actual.get(code) != kind for code, kind in STRUCTURED_TYPES.items()):
            raise DeliveryError('amo_field_mismatch')
    codes = {f.get('code') for f in fields}
    if not {key.upper() for key in UTM_FIELDS} <= codes:
        raise DeliveryError('amo_utm_fields_missing')
    tracking = {f.get('code') for f in fields if f.get('type') == 'tracking_data'}
    if not {'_YM_UID', '_YM_COUNTER'} <= tracking:
        raise DeliveryError('amo_metrika_fields_missing')


def field(field_id, value):
    return {'field_id': field_id, 'values': [{'value': value}]}


def contacts(lead):
    email, phone = lead.get('email'), lead.get('phone')
    if '@' in lead['contact']:
        email = email or lead['contact']
    else:
        phone = phone or lead['contact']
    return {key: value for key, value in [('EMAIL', email), ('PHONE', phone)] if value}


def normalize(code, value):
    return str(value).strip().casefold() if code == 'EMAIL' else re.sub(r'\D', '', str(value))


def existing_contact(client, lead):
    matches = set()
    for code, value in contacts(lead).items():
        for row in client.list('contacts', {'query': value}):
            for entry in row.get('custom_fields_values') or []:
                if entry.get('field_code') == code and any(
                        normalize(code, item.get('value', '')) == normalize(code, value)
                        for item in entry.get('values', [])):
                    matches.add(row['id'])
    if len(matches) > 1:
        raise DeliveryError('amo_contact_conflict')
    return next(iter(matches), None)


def find_submission(client, submission_id):
    fid = client.config['submission_field_id']
    matches = set()
    # Custom-field filters are unavailable on some account plans. Standard search
    # covers filled entity fields; verify the exact UUID ourselves before reuse.
    for row in client.list('leads', {'query': submission_id}):
        if any(entry.get('field_id') == fid and any(item.get('value') == submission_id
                for item in entry.get('values', [])) for entry in row.get('custom_fields_values') or []):
            matches.add(row['id'])
    if len(matches) > 1:
        raise DeliveryError('amo_submission_conflict')
    return next(iter(matches), None)


STRUCTURED_TYPES = {'NS_PAGE': 'url', 'NS_DIRECTION': 'text', 'NS_PRODUCT': 'text', 'NS_YM_CLIENT_ID': 'text'}


def structured_fields(lead, config):
    source, medium = lead.get('utm_source'), lead.get('utm_medium')
    traffic = ('Яндекс Директ (UTM)' if source == 'yandex' and medium == 'cpc' else
               (' / '.join(x for x in (source, medium) if x) + ' (UTM)' if source else 'Источник перехода неизвестен'))
    values = {'NS_PAGE': 'https://needle-shark.ru' + lead['source_path'] if lead.get('source_path') else None,
              'NS_DIRECTION': BUSINESS_LABELS.get(lead.get('business_intent')),
              'NS_PRODUCT': lead.get('product_name') or DIRECTION_LABELS.get(lead.get('business_direction')),
              'NS_YM_CLIENT_ID': lead.get('ym_client_id')}
    return [field(config['source_field_id'], traffic + ' → сайт → форма → amoCRM')] + [
        {'field_code': code, 'values': [{'value': value}]} for code, value in values.items() if value]


def note_text(lead):
    attachment = '\n\nВложение сохранено на сервере и отправляется по почте.' if lead.get('attachment') else ''
    return 'Заявка сайта №' + str(lead['order_id']) + '\n\n' + notification_payload(lead)['question'] + attachment + '\n\nID заявки сайта: ' + lead['id']


def ensure_note(job, remote_id, config, save_state, client):
    if not config.get('structured') or job.get('amo_note_id'):
        return remote_id
    expected = note_text(job['lead'])
    notes = list(client.list('leads/' + str(remote_id) + '/notes', {'filter[note_type]': 'common'}))
    matches = [n['id'] for n in notes if n.get('note_type') == 'common' and n.get('params', {}).get('text') == expected]
    if matches:
        if not save_state(job, amo_note_id=matches[0]):
            raise DeliveryError('amo_lease_lost')
        return remote_id
    if job.get('note_started'):
        raise DeliveryError('amo_note_unconfirmed')
    if not save_state(job, note_started=True):
        raise DeliveryError('amo_lease_lost')
    try:
        data = client.request('POST', '/api/v4/leads/' + str(remote_id) + '/notes',
                              [{'note_type': 'common', 'params': {'text': expected}}])
    except DeliveryError as error:
        if error.code in {'amo_http_400', 'amo_http_401', 'amo_http_403', 'amo_http_404', 'amo_http_422', 'amo_http_429'}:
            save_state(job, note_started=False)
        raise
    rows = data.get('_embedded', {}).get('notes', []) if isinstance(data, dict) else []
    if len(rows) != 1 or type(rows[0].get('id')) is not int or rows[0]['id'] <= 0:
        raise DeliveryError('amo_invalid_note_response')
    if not save_state(job, amo_note_id=rows[0]['id']):
        raise DeliveryError('amo_lease_lost')
    return remote_id


def payload(lead, config, contact_id=None):
    text = ('Заявка сайта №' + str(lead['order_id']) + '\nДата UTC: ' + lead['created_at'] +
            '\nИмя: ' + lead['name'] + '\nКонтакт: ' + lead['contact'] + '\n\n' +
            notification_payload(lead)['question'])
    if lead.get('attachment'):
        text += '\n\nВложение сохранено на сервере и отправляется в почтовом уведомлении. В amoCRM файл не загружен.'
    fields = [field(config['submission_field_id'], lead['id']),
              field(config['order_field_id'], str(lead['order_id'])),
              *([] if config.get('structured') else [field(config['details_field_id'], text)])]
    if config.get('structured'):
        fields.extend(structured_fields(lead, config))
    fields.extend({'field_code': key.upper(), 'values': [{'value': lead[key]}]}
                  for key in UTM_FIELDS if lead.get(key))
    if lead.get('ym_client_id'):
        fields.extend({'field_code': code, 'values': [{'value': value}]}
                      for code, value in [('_YM_UID', lead['ym_client_id']), ('_YM_COUNTER', '112428810')])
    contact = {'id': contact_id} if contact_id else {'name': lead['name'],
        'custom_fields_values': [{'field_code': code, 'values': [{'value': value, 'enum_code': 'WORK'}]}
                                for code, value in contacts(lead).items()]}
    result = {'name': 'Сайт — заявка №' + str(lead['order_id']),
        'pipeline_id': config['pipeline_id'], 'status_id': config['status_id'],
        'request_id': lead['id'], 'custom_fields_values': fields,
        '_embedded': {'contacts': [contact], 'tags': [{'name': 'Сайт Needle Shark'}]}}
    if config.get('responsible_id'):
        result['responsible_user_id'] = config['responsible_id']
        if not contact_id:
            contact['responsible_user_id'] = config['responsible_id']
    return result


def send(job, config, save_state, client=None):
    client = client or Client(config)
    lead = job['lead']
    if job.get('amo_lead_id'):
        # A durable remote id is sufficient to finish a job after a local crash.
        return ensure_note(job, job['amo_lead_id'], config, save_state, client)
    found = find_submission(client, lead['id'])
    if found:
        if not save_state(job, amo_lead_id=found):
            raise DeliveryError('amo_lease_lost')
        return ensure_note(job, found, config, save_state, client)
    if job.get('create_started'):
        # request_id is echoed by amoCRM, NOT an idempotency key. Do not retry a
        # possibly accepted POST. Keep reconciling and surface the pending job.
        raise DeliveryError('amo_create_unconfirmed')
    data = payload(lead, config, existing_contact(client, lead))
    if not save_state(job, create_started=True):
        raise DeliveryError('amo_lease_lost')
    try:
        result = client.request('POST', '/api/v4/leads/complex', [data])
    except DeliveryError as error:
        # These explicit rejections have not created the requested entity.
        if error.code in {'amo_http_400', 'amo_http_401', 'amo_http_403', 'amo_http_404', 'amo_http_422', 'amo_http_429'}:
            save_state(job, create_started=False)
        raise
    if not (isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict) and
            type(result[0].get('id')) is int and result[0]['id'] > 0 and
            lead['id'] in result[0].get('request_id', [])):
        raise DeliveryError('amo_invalid_create_response')
    remote_id = result[0]['id']
    if not save_state(job, amo_lead_id=remote_id):
        raise DeliveryError('amo_lease_lost')
    return ensure_note(job, remote_id, config, save_state, client)


def error_code(error):
    return error.code if isinstance(error, DeliveryError) else 'amo_delivery_error'
