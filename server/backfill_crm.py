"""Run once with production CRM_DSN and LEADS_DB; safe to repeat by submission UUID."""
import json
import os
import sqlite3
from crm import archive
if not os.environ.get('CRM_DSN'):
    raise SystemExit('CRM_DSN required')
with sqlite3.connect(os.environ.get('LEADS_DB','/var/lib/needle-shark/leads.sqlite3')) as db:
    rows=db.execute('SELECT payload FROM leads ORDER BY created').fetchall()
for (payload,) in rows:
    archive(json.loads(payload))
print('Archived queue records:',len(rows))
