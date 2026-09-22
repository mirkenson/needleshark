"""Transactional PostgreSQL intake, private files and independently retried deliveries."""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
import time
import uuid
from crm import archive_cursor


@contextmanager
def connection():
    import psycopg2
    dsn = os.environ.get('CRM_DSN')
    if not dsn:
        raise RuntimeError('CRM_DSN required')
    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '15s'")
            yield conn
    finally:
        conn.close()


def initialize(loop_enabled=False):
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT submission_id FROM lead_submissions LIMIT 0')
        cur.execute('SELECT content FROM lead_files LIMIT 0')
        cur.execute('SELECT lease_token FROM lead_deliveries LIMIT 0')
        if loop_enabled:
            cur.execute('SELECT lease_token FROM lead_loop_deliveries LIMIT 0')


def enqueue(data, ip, recipients, secret, loop_enabled=False):
    if not recipients or len(secret) < 32:
        raise RuntimeError('Intake configuration missing')
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    # HMAC prevents offline guessing of low-entropy IP addresses without the key.
    import hmac
    ip_hash = hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()
    lead = dict(data, created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    attachment = lead.pop('attachment', None)
    if attachment:
        lead['attachment'] = {k: attachment[k] for k in ('name', 'type')}
    conflict = (409, {'ok': False, 'error': 'Повторите отправку с новым номером заявки.'})
    with connection() as conn, conn.cursor() as cur:
        # Serialize short intake transactions: deterministic deduplication and rate limits.
        cur.execute('SELECT pg_advisory_xact_lock(1849202618)')
        cur.execute('SELECT fingerprint FROM lead_submissions WHERE submission_id=%s', (data['id'],))
        old = cur.fetchone()
        if old:
            return (200, {'ok': True, 'id': data['id']}) if old[0] == fingerprint else conflict
        cur.execute('SELECT 1 FROM orders WHERE submission_id=%s', (data['id'],))
        if cur.fetchone():
            # Historical Google entries have no permanent file fingerprint. Never replay them.
            return conflict
        cur.execute("SELECT count(*) FROM lead_submissions WHERE ip_hash=%s AND created_at > now()-interval '1 hour'", (ip_hash,))
        recent = cur.fetchone()[0]
        cur.execute("SELECT count(DISTINCT submission_id) FROM lead_deliveries WHERE status <> 'sent'")
        pending = cur.fetchone()[0]
        if recent >= 10 or pending >= 500:
            return 429, {'ok': False, 'error': 'Слишком много заявок. Попробуйте позже или напишите на info@neesha.ru.'}
        archive_cursor(cur, lead)
        cur.execute('INSERT INTO lead_submissions(submission_id,fingerprint,payload,ip_hash) VALUES(%s,%s,%s::jsonb,%s)',
                    (data['id'], fingerprint, json.dumps(lead, ensure_ascii=False), ip_hash))
        if attachment:
            cur.execute('INSERT INTO lead_files(submission_id,name,mime_type,content) VALUES(%s,%s,%s,%s)',
                        (data['id'], attachment['name'], attachment['type'], base64.b64decode(attachment['data'], validate=True)))
        for recipient in dict.fromkeys(recipients):
            cur.execute("INSERT INTO lead_deliveries(submission_id,channel,recipient) VALUES(%s,'email',%s)", (data['id'], recipient))
        if loop_enabled:
            cur.execute('INSERT INTO lead_loop_deliveries(submission_id) VALUES(%s)', (data['id'],))
    return 202, {'ok': True, 'id': data['id']}


def delivery_table(channel):
    # SQL identifiers only come from this fixed allowlist, never from a request/config.
    return {'email': 'lead_deliveries', 'loop': 'lead_loop_deliveries'}[channel]


def claim(channel='email'):
    table = delivery_table(channel)
    recipient_sql = 'd.recipient' if channel == 'email' else "'loop-leads'"
    token = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"""WITH next_job AS (
            SELECT id FROM {table} WHERE
            ((status='pending' AND retry_at<=now()) OR (status='sending' AND lease_until<now()))
            ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
            UPDATE {table} d SET status='sending',attempts=attempts+1,
            lease_until=now()+interval '5 minutes',lease_token=%s
            FROM next_job n WHERE d.id=n.id
            RETURNING d.id,d.submission_id,{recipient_sql},d.attempts""", (token,))
        row = cur.fetchone()
        if not row:
            return None
        job_id, submission_id, recipient, attempts = row
        # Resolve the human-facing number from the registry, including older queued
        # payloads. Keep the original UUID/fingerprint and API retry contract intact.
        cur.execute('''SELECT s.payload,o.id FROM lead_submissions s
            JOIN orders o USING(submission_id) WHERE s.submission_id=%s''', (submission_id,))
        lead, order_id = cur.fetchone()
        lead['order_id'] = order_id
        if channel == 'email':
            cur.execute('SELECT name,mime_type,content FROM lead_files WHERE submission_id=%s', (submission_id,))
            attachment = cur.fetchone()
            if attachment:
                lead['attachment'] = {'name': attachment[0], 'type': attachment[1], 'content': bytes(attachment[2])}
        return {'id': job_id, 'token': token, 'lead': lead, 'recipient': recipient, 'attempts': attempts, 'channel': channel}


def finish(job, error=None):
    table = delivery_table(job.get('channel', 'email'))
    with connection() as conn, conn.cursor() as cur:
        if error is None:
            cur.execute(f"""UPDATE {table} SET status='sent',sent_at=now(),last_error=NULL,
                lease_until=NULL,lease_token=NULL WHERE id=%s AND lease_token=%s AND status='sending'""", (job['id'], job['token']))
        else:
            delay = min(3600, 60 * 2 ** min(job['attempts'] - 1, 6))
            cur.execute(f"""UPDATE {table} SET status='pending',last_error=%s,
                retry_at=now()+(%s * interval '1 second'),lease_until=NULL,lease_token=NULL
                WHERE id=%s AND lease_token=%s AND status='sending'""", (error, delay, job['id'], job['token']))
        return cur.rowcount == 1
