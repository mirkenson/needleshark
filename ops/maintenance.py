"""Bounded attachment retention and privacy-safe local server monitoring."""
import argparse
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import json
import os
from pathlib import Path
import shutil
import smtplib
import ssl
import subprocess
import sys
import time
import urllib.request


def cleanup(conn):
    # Only file bytes/metadata are removed. Orders and permanent fingerprints survive.
    with conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '20s'")
        cur.execute("SET LOCAL lock_timeout = '3s'")
        cur.execute('SELECT pg_try_advisory_xact_lock(1849202630)')
        if not cur.fetchone()[0]:
            raise RuntimeError('cleanup_busy')
        cur.execute("""WITH expired AS (
            SELECT f.submission_id FROM lead_files f
            JOIN lead_submissions s USING(submission_id)
            WHERE s.created_at < now() - interval '30 days'
            AND EXISTS (SELECT 1 FROM lead_deliveries d WHERE d.submission_id=f.submission_id)
            AND NOT EXISTS (SELECT 1 FROM lead_deliveries d
                WHERE d.submission_id=f.submission_id AND (d.status <> 'sent' OR d.sent_at IS NULL))
            ORDER BY s.created_at LIMIT 100 FOR UPDATE OF f SKIP LOCKED)
            DELETE FROM lead_files f USING expired e WHERE f.submission_id=e.submission_id""")
        return cur.rowcount


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True))
    temporary.replace(path)


def active(unit):
    return subprocess.run(['systemctl', 'is-active', '--quiet', unit],
                          timeout=10, check=False).returncode == 0


def collect():
    issues = {}
    disk = shutil.disk_usage('/')
    if disk.used / disk.total >= .80 or disk.free < 1024**3:
        issues['disk'] = f'Диск: занято {disk.used / disk.total:.0%}, свободно {disk.free / 1024**3:.2f} ГиБ.'
    fs = os.statvfs('/')
    if fs.f_files and fs.f_favail / fs.f_files < .15:
        issues['inodes'] = 'Свободно менее 15% inode.'
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    if int(memory['MemAvailable'].split()[0]) < 32 * 1024:
        issues['memory'] = 'Доступно менее 32 МиБ оперативной памяти.'
    for unit in ('nginx', 'needle-leads', 'postgresql@16-main', 'needle-cleanup.timer'):
        if not active(unit):
            issues['service_' + unit] = 'Неактивна служба: ' + unit
    try:
        request = urllib.request.Request('https://needle-shark.ru/', method='HEAD',
                                         headers={'User-Agent': 'NeedleShark-Health/1.0'})
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError('https_status')
    except Exception:
        issues['https'] = 'Не удалось подтвердить HTTPS 200 основного сайта.'
    try:
        request = urllib.request.Request('http://127.0.0.1:8091/api/leads', data=b'{}',
            headers={'Origin': 'https://needle-shark.ru', 'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request, timeout=10).close()
            issues['api'] = 'API не вернул ожидаемый отказ для пустой тестовой заявки.'
        except urllib.error.HTTPError as error:
            if error.code != 400:
                raise
    except Exception:
        issues['api'] = 'Обработчик заявок не отвечает ожидаемым HTTP 400 на пустую проверку.'
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ['CRM_DSN'], connect_timeout=5)
        try:
            with conn, conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '10s'")
                cur.execute("""SELECT count(*), count(*) FILTER (
                    WHERE s.created_at < now()-interval '15 minutes')
                    FROM lead_deliveries d JOIN lead_submissions s USING(submission_id)
                    WHERE d.status <> 'sent'""")
                pending, delayed = cur.fetchone()
                if delayed:
                    issues['queue'] = f'Почтовых заданий в ожидании: {pending}; старше 15 минут: {delayed}.'
        finally:
            conn.close()
    except Exception:
        issues['database'] = 'Не удалось проверить PostgreSQL и очередь доставки.'
    try:
        result = json.loads(Path('/var/lib/needle-cleanup/last-success.json').read_text())
        if time.time() - result['time'] > 36 * 3600:
            raise RuntimeError('stale_cleanup')
        status = subprocess.run(['systemctl', 'show', 'needle-cleanup.service',
                                 '--property=Result', '--value'], capture_output=True,
                                text=True, timeout=10, check=True).stdout.strip()
        if status != 'success':
            raise RuntimeError('cleanup_failed')
    except Exception:
        issues['cleanup'] = 'Очистка вложений завершилась ошибкой или нет успешного запуска за 36 часов.'
    return issues


def notify(subject, body):
    # Reuse existing TLS configuration and mailbox validation, without changing lead recipients.
    sys.path.insert(0, '/opt/needle-shark/current')
    from mail_delivery import smtp_config, mailbox
    config = smtp_config()
    if not config:
        raise RuntimeError('smtp_unconfigured')
    recipient = mailbox(os.environ['MONITOR_RECIPIENT'])
    msg = EmailMessage()
    msg['From'], msg['To'] = config['sender'], recipient
    msg['Subject'] = 'Needle Shark — ' + subject
    msg['Date'], msg['Message-ID'] = formatdate(usegmt=True), make_msgid(domain=config['sender'].split('@')[1])
    msg.set_content(body + '\n\nАвтоматический мониторинг VPS. Данные заявителей не включены.')
    context = ssl.create_default_context()
    cls = smtplib.SMTP_SSL if config['mode'] == 'ssl' else smtplib.SMTP
    kwargs = dict(host=config['host'], port=config['port'], timeout=30)
    if config['mode'] == 'ssl':
        kwargs['context'] = context
    client = cls(**kwargs)
    try:
        if config['mode'] == 'starttls':
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        client.login(config['user'], config['password'])
        if client.send_message(msg, from_addr=config['sender'], to_addrs=[recipient]):
            raise RuntimeError('recipient_refused')
    finally:
        client.close()


def report(issues, state, now, sender=notify):
    # Stable keys prevent repeated alerts as counters fluctuate. Retry failed sends next run.
    keys = sorted(issues)
    previous = state.get('issues', [])
    if keys != previous or (keys and now - state.get('sent_at', 0) >= 6 * 3600):
        subject = 'проблема с сервером' if keys else 'работа сервера восстановлена'
        body = '\n'.join(issues[key] for key in keys) if keys else 'Все контролируемые проверки снова проходят.'
        sender(subject, body)
        state = dict(issues=keys, sent_at=now)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('cleanup', 'monitor', 'test-email', 'check'))
    action = parser.parse_args().action
    if action == 'cleanup':
        import psycopg2
        conn = psycopg2.connect('dbname=needle_shark', connect_timeout=5)
        try:
            count = 0
            for _ in range(10):
                deleted = cleanup(conn)
                count += deleted
                if deleted < 100:
                    break
        finally:
            conn.close()
        atomic_json(Path('/var/lib/needle-cleanup/last-success.json'), dict(time=time.time(), deleted=count))
        print('Expired delivered attachments deleted:', count)
    elif action == 'test-email':
        notify('ТЕСТ уведомлений сервера', 'ТЕСТ: отправка уведомлений настроена. Это проверка, аварии не обнаружены.\n'
               'Проверки каждые 5 минут: диск, память, службы, HTTPS, очередь почты и очистка вложений.\n'
               'Мониторинг работает на самом VPS и не сможет сообщить о его полном отключении.')
        print('Test notification accepted by SMTP')
    else:
        issues = collect()
        if action == 'check':
            print(json.dumps(issues, ensure_ascii=False))
            return
        path = Path('/var/lib/needle-monitor/state.json')
        try:
            state = json.loads(path.read_text())
        except FileNotFoundError:
            state = {}
        atomic_json(path, report(issues, state, time.time()))
        print('Monitor checks completed; issues:', ','.join(sorted(issues)) or 'none')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Exception strings may contain DSNs or SMTP replies. Keep journals privacy-safe.
        print('Maintenance failed; inspect configuration and service health.', file=sys.stderr)
        sys.exit(1)
