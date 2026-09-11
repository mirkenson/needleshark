"""Private durable lead queue; expose only /api/leads through Nginx."""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from crm import archive
from lead_context import validate_context, google_payload
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

DB = os.environ.get('LEADS_DB', '/var/lib/needle-shark/leads.sqlite3')
HOOK = os.environ.get('GOOGLE_LEADS_URL', '')
SECRET = os.environ.get('GOOGLE_LEADS_SECRET', '')
MAX_FILE = 2 * 1024 * 1024
MAX_BODY = 3 * 1024 * 1024
ORIGINS = {'https://needle-shark.ru', 'https://www.needle-shark.ru',
           'https://needleshark.ru', 'https://www.needleshark.ru'}


@contextmanager
def connect():
    connection = sqlite3.connect(DB, timeout=10)
    connection.execute('PRAGMA busy_timeout=10000')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    os.makedirs(os.path.dirname(DB), mode=0o700, exist_ok=True)
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, fingerprint TEXT NOT NULL,
            created REAL NOT NULL, ip_hash TEXT NOT NULL, delivered REAL,
            attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0)''')
        db.execute('CREATE INDEX IF NOT EXISTS leads_retry ON leads(delivered, retry_at)')
    os.chmod(DB, 0o600)


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Некорректные данные заявки.')
    if data.get('consent') is not True:
        raise ValueError('Необходимо согласие с документами и обработкой данных.')
    if data.get('website'):
        raise ValueError('Не удалось отправить заявку.')
    result = {'id': str(uuid.UUID(str(data.get('id', '')))), 'consent': True,
              'consent_documents': ['https://needle-shark.ru/user-agreement', 'https://needle-shark.ru/privacy-policy']}
    for key, limit in [('name', 120), ('contact', 254), ('question', 5000)]:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Проверьте имя, контакт и описание задачи.')
        if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
            raise ValueError('Некорректные символы в заявке.')
        result[key] = value.strip()
    contact = result['contact']
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', contact):
        if not re.fullmatch(r'[+\d()\s.-]+', contact) or not 7 <= len(re.sub(r'\D', '', contact)) <= 15:
            raise ValueError('Укажите корректный телефон или email.')
    result.update(validate_context(data))
    if len(google_payload(result)['question']) > 5000:
        raise ValueError('Сократите описание задачи с учётом сведений о товаре.')
    attachment = data.get('attachment')
    if attachment is not None:
        if not isinstance(attachment, dict):
            raise ValueError('Некорректный файл.')
        try:
            raw = base64.b64decode(attachment.get('data', ''), validate=True)
        except (ValueError, TypeError):
            raise ValueError('Некорректный файл.') from None
        mime = attachment.get('type')
        signatures = {'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff', 'application/pdf': b'%PDF-'}
        if mime not in signatures or not raw.startswith(signatures[mime]) or len(raw) > MAX_FILE:
            raise ValueError('Прикрепите JPG, PNG или PDF размером до 2 МБ.')
        name = attachment.get('name', '')
        if not isinstance(name, str) or not name or len(name) > 160 or any(ord(c) < 32 for c in name):
            raise ValueError('Некорректное имя файла.')
        result['attachment'] = {'name': name.replace('/', '_').replace('\\', '_'), 'type': mime, 'data': base64.b64encode(raw).decode()}
    return result


def enqueue(data, ip):
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    ip_hash = hashlib.sha256((SECRET + ip).encode()).hexdigest()
    now = time.time()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT fingerprint FROM leads WHERE id=?', (data['id'],)).fetchone()
        if old:
            return (200, {'ok': True, 'id': data['id']}) if old[0] == fingerprint else (409, {'ok': False, 'error': 'Повторите отправку с новым номером заявки.'})
        recent = db.execute('SELECT count(*) FROM leads WHERE ip_hash=? AND created>?', (ip_hash, now - 3600)).fetchone()[0]
        pending = db.execute('SELECT count(*) FROM leads WHERE delivered IS NULL').fetchone()[0]
        if recent >= 10 or pending >= 500:
            return 429, {'ok': False, 'error': 'Слишком много заявок. Попробуйте позже или напишите на info@neesha.ru.'}
        data['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))
        archive(data)
        db.execute('INSERT INTO leads(id,payload,fingerprint,created,ip_hash) VALUES(?,?,?,?,?)',
                   (data['id'], json.dumps(data, ensure_ascii=False), fingerprint, now, ip_hash))
    return 202, {'ok': True, 'id': data['id']}


def deliver_once():
    if not HOOK or not SECRET:
        return
    with connect() as db:
        rows = db.execute('SELECT id,payload,attempts FROM leads WHERE delivered IS NULL AND retry_at<=? ORDER BY created LIMIT 5', (time.time(),)).fetchall()
    for lead_id, payload, attempts in rows:
        try:
            body = json.dumps({'token': SECRET, 'lead': google_payload(json.loads(payload))}).encode()
            request = Request(HOOK, data=body, headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(request, timeout=40) as response:
                result = json.loads(response.read(4096))
            if result.get('ok') is not True or result.get('id') != lead_id:
                raise ValueError('Delivery not acknowledged')
            with connect() as db:
                db.execute('UPDATE leads SET delivered=? WHERE id=?', (time.time(), lead_id))
        except Exception:
            # Log identifiers only, never contacts, messages, files, tokens or webhook URLs.
            print('Lead delivery pending:', lead_id, flush=True)
            with connect() as db:
                db.execute('UPDATE leads SET attempts=attempts+1,retry_at=? WHERE id=?', (time.time() + min(3600, 60 * 2 ** min(attempts, 6)), lead_id))
    with connect() as db:
        db.execute('DELETE FROM leads WHERE delivered IS NOT NULL AND delivered<?', (time.time() - 7 * 86400,))


def worker():
    while True:
        try:
            deliver_once()
        except Exception:
            print('Lead queue worker will retry', flush=True)
        time.sleep(15)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/leads':
            return self.reply(404, {'ok': False})
        if not HOOK or not SECRET:
            return self.reply(503, {'ok': False, 'error': 'Напишите нам на info@neesha.ru — форма временно недоступна.'})
        if self.headers.get('Origin') not in ORIGINS:
            return self.reply(403, {'ok': False, 'error': 'Откройте форму на needle-shark.ru.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'ok': False, 'error': 'Некорректный формат заявки.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.reply(413, {'ok': False, 'error': 'Файл слишком большой.'})
            self.connection.settimeout(15)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError('Неполная заявка.')
            data = validate(json.loads(raw))
            status, response = enqueue(data, self.headers.get('X-Real-IP', self.client_address[0]))
            self.reply(status, response)
        except (ValueError, TypeError):
            self.reply(400, {'ok': False, 'error': 'Проверьте поля. Допустимы JPG, PNG и PDF до 2 МБ.'})
        except Exception:
            self.reply(503, {'ok': False, 'error': 'Не удалось сохранить заявку. Попробуйте позже или напишите на info@neesha.ru.'})


if __name__ == '__main__':
    if HOOK and not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', HOOK):
        raise SystemExit('Invalid Google webhook configuration')
    if SECRET and len(SECRET) < 32:
        raise SystemExit('Shared secret must contain at least 32 characters')
    initialize()
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', 8091), Handler).serve_forever()
