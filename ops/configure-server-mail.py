"""Build private systemd environment without printing secrets. Run as root on VPS."""
import os
from pathlib import Path
import secrets
import shlex
import sys


def read_env(path):
    result = {}
    for raw in Path(path).read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        key, sep, value = raw.partition('=')
        if not sep or not key.strip().replace('_', '').isalnum():
            raise ValueError('Invalid environment file')
        value = value.strip()
        result[key.strip()] = shlex.split(value)[0] if value[:1] in ('\"', "'") else value
    return result


def quoted(value):
    if any(c in value for c in ('\n', '\r', '\x00')):
        raise ValueError('Multiline environment value rejected')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def write_env(target, new):
    temp = Path(target + '.next')
    fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(key + '=' + quoted(value) + '\n' for key, value in sorted(new.items())))
    os.chmod(temp, 0o600)
    os.replace(temp, target)


def configure_loop(target, incoming):
    from loop_delivery import webhook_url
    old, supplied = read_env(target), read_env(incoming)
    if set(supplied) != {'LOOP_LEADS_WEBHOOK_URL'} or not webhook_url(supplied['LOOP_LEADS_WEBHOOK_URL']):
        raise ValueError('Only the approved LOOP webhook setting is allowed')
    if not old.get('CRM_DSN') or not old.get('MAIL_RECIPIENTS'):
        raise ValueError('Existing mail backend configuration missing')
    write_env(target, dict(old, **supplied))


def main():
    if sys.argv[1] == '--loop':
        configure_loop(*sys.argv[2:])
        print('Private LOOP configuration updated; existing settings preserved')
        return
    target, incoming, allowed_recipient = map(str, sys.argv[1:])
    old = read_env(target)
    supplied = read_env(incoming)
    allowed = {'SMTP_HOST', 'SMTP_PORT', 'SMTP_SECURITY', 'SMTP_USER', 'SMTP_PASSWORD', 'MAIL_FROM', 'MAIL_RECIPIENTS'}
    if set(supplied) - allowed or supplied.get('MAIL_RECIPIENTS') != allowed_recipient:
        raise SystemExit('Only explicitly approved recipient/settings are allowed')
    new = {key: value for key, value in old.items() if not key.startswith('GOOGLE_') and key != 'LEADS_DB'}
    new.update(supplied)
    new.setdefault('IP_HASH_SECRET', secrets.token_urlsafe(48))
    if not new.get('CRM_DSN'):
        raise SystemExit('Existing PostgreSQL configuration missing')
    write_env(target, new)
    print('Private environment updated; Google keys removed; one approved mail recipient')


if __name__ == '__main__':
    main()
