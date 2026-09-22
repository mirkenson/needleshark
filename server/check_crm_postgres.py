"""Verify the real CRM SQL in a disposable PostgreSQL schema, never public tables.

Run with CRM_TEST_DSN (a test/admin connection) and psycopg2 installed.
The schema name is generated locally; only that schema is removed afterwards.
"""
import os
import uuid
from pathlib import Path
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn
import crm


def main():
    dsn = os.environ['CRM_TEST_DSN']
    schema = 'needle_test_' + uuid.uuid4().hex
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            cur.execute(Path(__file__).with_name('schema.sql').read_text())
            migration = Path(__file__).with_name('migrations').joinpath('20260918_business_attachments.sql').read_text()
            cur.execute(migration)
            cur.execute(migration)
        os.environ['CRM_DSN'] = make_dsn(dsn, options='-csearch_path=' + schema)
        ids = []
        for intent in ['ready', 'custom', 'materials', None]:
            lead = dict(id=str(uuid.uuid4()), name='ТЕСТ БД', contact='test@example.invalid',
                        question='ТЕСТ: описание без служебных префиксов', consent=True,
                        created_at='2026-09-18T00:00:00Z')
            if intent:
                lead.update(business_intent=intent, business_company="ТЕСТ ' компания", source_path='/business/',
                            inquiry_type='direct' if intent == 'materials' else 'wholesale',
                            attachment={'name': 'ТЕСТ.pdf'})
            crm.archive(lead)
            crm.archive(lead)
            try:
                crm.archive(dict(lead, business_company='Другие данные'))
                raise AssertionError('Changed request accepted')
            except ValueError:
                pass
            if intent:
                link = 'https://drive.google.com/file/d/test-file-123456789/view'
                crm.save_attachment_link(lead['id'], link)
                crm.save_attachment_link(lead['id'], link)
            with admin.cursor() as cur:
                cur.execute('SELECT business_intent,business_company,description,source_path,attachment_name,attachment_url FROM orders WHERE submission_id=%s', (lead['id'],))
                saved = cur.fetchone()
                assert saved == (intent, lead.get('business_company'), lead['question'], lead.get('source_path'),
                                 'ТЕСТ.pdf' if intent else None, link if intent else None), saved
            ids.append(lead['id'])
        with admin.cursor() as cur:
            cur.execute('SELECT count(*) FROM orders')
            assert cur.fetchone()[0] == 4
            cur.execute('SELECT count(*) FROM customers')
            assert cur.fetchone()[0] == 1
        print('PASS PostgreSQL: 3 B2B directions, legacy form, exact fields, file links, retry deduplication, additive migration twice')
        # Four distinct submissions above used one customer, consuming sequence
        # values 1..4. Retries of an already archived UUID consumed none.
        for contact, count in [('second@example.invalid', 3), ('third@example.invalid', 2),
                               ('fourth@example.invalid', 1)]:
            for _ in range(count):
                crm.archive(dict(id=str(uuid.uuid4()), name='ТЕСТ нумерация', contact=contact,
                                 question='ТЕСТ повторное обращение', consent=True,
                                 created_at='2026-09-22T00:00:00Z'))
        with admin.cursor() as cur:
            cur.execute('SELECT id FROM customers ORDER BY id')
            assert cur.fetchall() == [(1,), (5,), (8,), (10,)]
            cur.execute('SELECT count(*) FROM orders')
            assert cur.fetchone()[0] == 10
        print('PASS customer sequence gaps reproduced: ids 1,5,8,10 with 10 inquiries, no deletions or failed transactions')
    finally:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        admin.close()


if __name__ == '__main__':
    main()
