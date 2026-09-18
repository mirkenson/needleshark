"""Real retention checks in an isolated disposable schema; no mail or real lead changes."""
import os
from pathlib import Path
import uuid
import psycopg2
from psycopg2 import sql
from maintenance import cleanup


def main():
    conn = psycopg2.connect(os.environ.get('CRM_TEST_DSN', 'dbname=needle_shark'))
    schema = 'needle_retention_test_' + uuid.uuid4().hex
    def query(statement, args=()):
        with conn, conn.cursor() as cur:
            cur.execute(statement, args)
            return cur.fetchall() if cur.description else None
    try:
        query(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        query(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        query(Path(__file__).parent.parent.joinpath('server/schema.sql').read_text())
        customer = query("""INSERT INTO customers(name,contact,contact_key,first_inquiry_at,last_inquiry_at)
            VALUES('TEST','test@example.invalid','test',now(),now()) RETURNING id""")[0][0]
        ids = []
        for days, statuses in ((31, ['sent']), (29, ['sent']), (31, ['pending']),
                               (31, ['sending']), (31, ['sent', 'pending']), (31, []),
                               (31, ['sent', 'sent'])):
            key = str(uuid.uuid4())
            ids.append(key)
            query("""INSERT INTO orders(submission_id,customer_id,created_at,customer_name,contact,description,consent)
                VALUES(%s,%s,now(),'TEST','test@example.invalid','TEST',true)""", (key, customer))
            query("""INSERT INTO lead_submissions(submission_id,fingerprint,payload,ip_hash,created_at)
                VALUES(%s,'permanent','{}','test',now()-(%s * interval '1 day'))""", (key, days))
            query("INSERT INTO lead_files VALUES(%s,'test.pdf','application/pdf',%s)", (key, b'%PDF-test'))
            for index, status in enumerate(statuses):
                query("""INSERT INTO lead_deliveries(submission_id,channel,recipient,status,sent_at)
                    VALUES(%s,'email',%s,%s,CASE WHEN %s='sent' THEN now() ELSE NULL END)""",
                      (key, f'test{index}@example.invalid', status, status))
        assert cleanup(conn) == 2
        remaining = {str(row[0]) for row in query('SELECT submission_id FROM lead_files')}
        assert remaining == set(ids[1:6])
        assert query('SELECT count(*) FROM orders') == [(7,)]
        assert query("SELECT count(*) FROM lead_submissions WHERE fingerprint='permanent'") == [(7,)]
        assert cleanup(conn) == 0
        assert bytes(query('SELECT content FROM lead_files LIMIT 1')[0][0]) == b'%PDF-test'
        print('PASS: expired sent removed; fresh, pending, sending, partial and no-job preserved; orders/fingerprints intact; idempotent')
    finally:
        conn.rollback()
        query(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        conn.close()


if __name__ == '__main__':
    main()
