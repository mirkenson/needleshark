"""Persistent PostgreSQL customer/order registry, separate from delivery queue."""
from contextlib import closing
import os
import re
import json

def archive(lead):
    dsn = os.environ.get('CRM_DSN')
    if not dsn:
        return  # Explicitly enabled on production; allows isolated queue tests.
    import psycopg2
    contact = lead['contact'].strip()
    key = contact.casefold() if '@' in contact else re.sub(r'\D', '', contact)
    with closing(psycopg2.connect(dsn, connect_timeout=5)) as conn, conn:
        with conn.cursor() as cur:
            # A retry must not change the customer/order snapshot or create a duplicate.
            cur.execute('SELECT customer_name,contact,description FROM orders WHERE submission_id=%s', (lead['id'],))
            old = cur.fetchone()
            if old:
                if old != (lead['name'],contact,lead['question']):
                    raise ValueError('Submission ID already belongs to another request')
                return
            cur.execute('''INSERT INTO customers(name,contact,contact_key,first_inquiry_at,last_inquiry_at)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(contact_key) DO UPDATE
                SET last_inquiry_at=GREATEST(customers.last_inquiry_at,EXCLUDED.last_inquiry_at)
                RETURNING id''', (lead['name'],contact,key,lead['created_at'],lead['created_at']))
            customer_id = cur.fetchone()[0]
            cur.execute('''INSERT INTO orders(submission_id,customer_id,created_at,customer_name,contact,description,
                attachment_name,consent,consent_documents) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT(submission_id) DO NOTHING''', (lead['id'],customer_id,lead['created_at'],lead['name'],contact,
                lead['question'],(lead.get('attachment') or {}).get('name'),lead.get('consent',False),
                json.dumps(lead.get('consent_documents',[]))))
