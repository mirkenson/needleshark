"""Short-lived, UUID/IP-bound browser work; no visitor data or challenge state stored."""
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid

DIFFICULTY = 14
LIFETIME = 600
ERROR = 'Не удалось пройти проверку отправки. Обновите страницу и попробуйте снова или напишите на sales@neesha.ru.'


class Rejected(ValueError):
    pass


def required():
    value = os.environ.get('LEAD_PROTECTION_REQUIRED', '0')
    if value not in ('0', '1'):
        raise RuntimeError('Invalid lead protection configuration')
    return value == '1'


def signature(message, ip):
    secret = os.environ.get('IP_HASH_SECRET', '')
    if len(secret) < 32:
        raise RuntimeError('Intake configuration missing')
    return hmac.new(secret.encode(), ('lead-work-v1\n' + ip + '\n' + message).encode(), hashlib.sha256).hexdigest()


def issue(submission_id, ip):
    submission_id = str(uuid.UUID(str(submission_id)))
    message = f'{int(time.time())}.{submission_id}.{secrets.token_hex(16)}'
    return {'ok': True, 'challenge': message + '.' + signature(message, ip),
            'difficulty': DIFFICULTY, 'expires_in': LIFETIME}


def verify(proof, submission_id, ip):
    if not isinstance(proof, dict):
        raise Rejected(ERROR)
    token, nonce = proof.get('challenge'), proof.get('nonce')
    if (not isinstance(token, str) or len(token) > 200 or type(nonce) is not int
            or not 0 <= nonce < 2**24):
        raise Rejected(ERROR)
    match = re.fullmatch(r'(\d{10})\.([0-9a-f-]{36})\.([0-9a-f]{32})\.([0-9a-f]{64})', token)
    if not match:
        raise Rejected(ERROR)
    issued, bound_id, _, mac = match.groups()
    if bound_id != submission_id or not 0 <= time.time() - int(issued) <= LIFETIME:
        raise Rejected(ERROR)
    if not hmac.compare_digest(mac, signature(token.rsplit('.', 1)[0], ip)):
        raise Rejected(ERROR)
    digest = hashlib.sha256(f'{token}:{nonce}'.encode()).digest()
    if int.from_bytes(digest[:2], 'big') >> (16 - DIFFICULTY):
        raise Rejected(ERROR)
