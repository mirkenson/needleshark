"""Transactional lead intake and SMTP worker; expose only /api/leads through Nginx."""
import base64
import json
import os
import re
import threading
import time
import uuid
import delivery_store
import mail_delivery
from lead_context import validate_context, notification_payload
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_FILE = 2 * 1024 * 1024
MAX_BODY = 3 * 1024 * 1024
ORIGINS = {'https://needle-shark.ru', 'https://www.needle-shark.ru',
           'https://needleshark.ru', 'https://www.needleshark.ru'}


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
    if len(notification_payload(result)['question']) > 5000:
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
    return delivery_store.enqueue(data, ip, mail_delivery.recipients(), os.environ.get('IP_HASH_SECRET', ''))


def deliver_once():
    config = mail_delivery.smtp_config()
    if config is None:
        return
    for _ in range(5):
        job = delivery_store.claim()
        if job is None:
            break
        try:
            mail_delivery.send(job['lead'], job['recipient'], config)
        except Exception as error:
            delivery_store.finish(job, mail_delivery.error_code(error))
            print('Email delivery pending:', job['id'], flush=True)
        else:
            delivery_store.finish(job)


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
    if len(os.environ.get('IP_HASH_SECRET', '')) < 32:
        raise SystemExit('IP_HASH_SECRET must contain at least 32 characters')
    mail_delivery.recipients()
    if mail_delivery.smtp_config() is None:
        print('SMTP not configured: leads will be saved, email delivery paused', flush=True)
    delivery_store.initialize()
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', 8091), Handler).serve_forever()
