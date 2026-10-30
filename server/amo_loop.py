"""New amoCRM deals -> approved LOOP channel; independent from website intake.

Read-only polling avoids a public unauthenticated webhook. PostgreSQL deduplicates
both the normal and unsorted feeds by deal ID. Unknown POST outcomes are held,
never blindly repeated. No customer contact, comment or attachment is published.
"""
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
import amo_delivery
import delivery_store
import loop_delivery


def configuration(env=None):
    env = os.environ if env is None else env
    url = loop_delivery.webhook_url(env.get('AMO_LOOP_WEBHOOK_URL', ''))
    if not url:
        return None
    start = env.get('AMO_LOOP_STARTED_AT', '')
    if not re.fullmatch(r'[1-9][0-9]{9}', start):
        raise ValueError('Invalid amoCRM LOOP start')
    config = amo_delivery.configuration(env)
    if config is None or env.get('LOOP_LEADS_WEBHOOK_URL'):
        raise ValueError('amoCRM required; legacy LOOP intake must remain disabled')
    return {'url': url, 'start': int(start), 'amo': config}


def message(lead_id, title, base):
    if type(lead_id) is not int or lead_id <= 0 or not re.fullmatch(r'https://[a-z0-9-]+\.amocrm\.ru', base):
        raise ValueError('Invalid deal link')
    # Only the owner's fixed mention is active. Visitor-controlled deal names
    # cannot inject mentions, Markdown links, images, or extra message lines.
    title = ' '.join(str(title).split())
    title = title.replace('@', '@\u200b')
    title = re.sub(r'([\\`*_{}\[\]()<>!~|])', r'\\\1', title)
    title = re.sub(r'https?://', lambda m: m.group(0).replace(':', ':\u200b'), title)
    return {'text': '@daniil\n🚨🚨🚨 НОВАЯ ЗАЯВКА 🚨🚨🚨\n' + base + '/leads/detail/' + str(lead_id) + '\n' + title,
            'skip_slack_parsing': True}


def discover(client, since, until):
    params = {'filter[created_at][from]': since, 'filter[created_at][to]': until,
              'order[created_at]': 'asc', 'with': 'source_id'}
    result = {}
    for row in client.list('leads', params):
        if type(row.get('id')) is not int or type(row.get('created_at')) is not int:
            raise ValueError('Invalid CRM feed')
        if since <= row['created_at'] <= until:
            result[row['id']] = row
    # Chat requests may not be present in the ordinary list until accepted.
    for unsorted in client.list('leads/unsorted', {'order[created_at]': 'desc'}):
        if type(unsorted.get('created_at')) is int and unsorted['created_at'] < since:
            break
        for item in unsorted.get('_embedded', {}).get('leads', []):
            lid = item.get('id')
            if type(lid) is not int or lid <= 0:
                raise ValueError('Invalid unsorted deal')
            if lid not in result:
                row = client.request('GET', '/api/v4/leads/' + str(lid) + '?with=source_id')
                if type(row.get('created_at')) is not int:
                    raise ValueError('Invalid CRM timestamp')
                if since <= row['created_at'] <= until:
                    row['_intake_category'] = unsorted.get('category')
                    result[lid] = row
            elif unsorted.get('category'):
                result[lid]['_intake_category'] = unsorted['category']
    return list(result.values())


def enrich(client, row, config):
    if not config.get('structured'):
        return
    fields = row.get('custom_fields_values') or []
    bycode = {f.get('field_code'): f.get('values', []) for f in fields}
    byid = {f.get('field_id'): f.get('values', []) for f in fields}
    changes = []
    if not byid.get(config['source_field_id']):
        channel = ('Email' if row.get('source_id') == 21223 else
                   {'chats': 'Онлайн-чат', 'mail': 'Email'}.get(row.get('_intake_category')))
        if channel:
            changes.append(amo_delivery.field(config['source_field_id'],
                channel + ' → amoCRM; источник до обращения не установлен'))
    if not bycode.get('NS_YM_CLIENT_ID') and bycode.get('_YM_UID'):
        value = bycode['_YM_UID'][0].get('value')
        if isinstance(value, str) and re.fullmatch(r'[0-9]{1,32}',value):
            changes.append({'field_code':'NS_YM_CLIENT_ID','values':[{'value':value}]})
    if changes:
        client.request('PATCH','/api/v4/leads/' + str(row['id']),{'custom_fields_values':changes})


def post(url, body):
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(),
        headers={'Content-Type':'application/json','User-Agent':'NeedleShark-CRM/1.0'}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), loop_delivery.NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200 or response.read(1024).strip() != b'ok':
                return 'uncertain', 'loop_unconfirmed'
        return 'sent', None
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        # Retry only explicit non-acceptance. 5xx might follow a persisted post.
        return ('pending' if code in (400,401,403,404,413,422,429) else 'uncertain'), 'loop_http_' + str(code)
    except (urllib.error.URLError, TimeoutError, OSError):
        return 'uncertain', 'loop_network_unconfirmed'


def run_once(config=None, client=None):
    config = configuration() if config is None else config
    if config is None:
        return
    client = client or amo_delivery.Client(config['amo'])
    # Session lock spans network requests; only one process scans/sends at a time.
    with delivery_store.connection() as lock_conn, lock_conn.cursor() as lock:
        lock.execute('SELECT pg_try_advisory_lock(1849202628)')
        if not lock.fetchone()[0]:
            return
        with delivery_store.connection() as conn, conn.cursor() as cur:
            cur.execute('INSERT INTO amo_loop_cursor(id,scanned_until) VALUES(1,%s) ON CONFLICT DO NOTHING', (config['start'],))
            cur.execute('SELECT scanned_until FROM amo_loop_cursor WHERE id=1')
            cursor = cur.fetchone()[0]
        until = int(time.time()) - 5
        if until < cursor + 55:
            return
        since = max(config['start'], cursor - 300)
        rows = discover(client, since, until)
        for row in rows:
            enrich(client, row, config['amo'])
        with delivery_store.connection() as conn, conn.cursor() as cur:
            for row in rows:
                cur.execute('''INSERT INTO amo_loop_notifications(lead_id,title,created_at) VALUES(%s,%s,%s)
                    ON CONFLICT(lead_id) DO NOTHING''', (row['id'], row.get('name') or 'Без названия', row['created_at']))
            cur.execute('UPDATE amo_loop_cursor SET scanned_until=%s WHERE id=1', (until,))
            # Previous process exited after fencing a send. Do not duplicate it.
            cur.execute("UPDATE amo_loop_notifications SET status='uncertain',last_error='loop_process_interrupted' WHERE status='sending'")
        for _ in range(20):
            with delivery_store.connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT lead_id,title FROM amo_loop_notifications WHERE status='pending' AND retry_at<=now() ORDER BY created_at,lead_id LIMIT 1 FOR UPDATE")
                row = cur.fetchone()
                if not row:
                    break
                body = message(row[0], row[1], config['amo']['base'])
                cur.execute("UPDATE amo_loop_notifications SET status='sending',attempts=attempts+1 WHERE lead_id=%s", (row[0],))
            status, error = post(config['url'], body)
            with delivery_store.connection() as conn, conn.cursor() as cur:
                cur.execute("""UPDATE amo_loop_notifications SET status=%s,last_error=%s,
                    sent_at=CASE WHEN %s='sent' THEN now() ELSE NULL END,
                    retry_at=now()+interval '5 minutes' WHERE lead_id=%s""", (status,error,status,row[0]))
            print('amoCRM LOOP:', row[0], status, flush=True)
