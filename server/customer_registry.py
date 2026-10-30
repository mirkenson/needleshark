"""Local identity and attribution. No HTTP, no changes to outbound CRM payloads."""
import os
import re
from datetime import datetime, timezone

UTM = ('utm_source','utm_medium','utm_campaign','utm_content','utm_term')

def enabled():
    return os.environ.get('CUSTOMER_SYNC_ENABLED') == '1'

def normalize(kind, value):
    value = str(value or '').strip()
    if kind == 'email':
        value = value.casefold()
        return value if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value) else None
    digits = re.sub(r'\D','',value)
    if len(digits)==11 and digits.startswith('8'):
        digits='7'+digits[1:]
    return digits if 10 <= len(digits) <= 15 else None

def identifiers(lead):
    found = set()
    for kind in ('email','phone'):
        value=lead.get(kind)
        if not value and ('@' in lead.get('contact','')) == (kind=='email'):
            value=lead.get('contact')
        key=normalize(kind,value)
        if key: found.add((kind,key))
    return sorted(found)

def conflict(cur, key, reason, ids=()):
    cur.execute('''INSERT INTO customer_sync_conflicts(object_key,reason,candidate_ids)
        VALUES(%s,%s,%s) ON CONFLICT(object_key) DO UPDATE SET reason=EXCLUDED.reason,
        candidate_ids=EXCLUDED.candidate_ids,last_seen_at=now(),resolved_at=NULL''',(key,reason,list(ids)))
    if ids:
        cur.execute('UPDATE customers SET sync_conflict=true WHERE id=ANY(%s)',(list(ids),))

def candidates(cur, values):
    found=set()
    for kind,value in values:
        cur.execute('SELECT customer_id FROM customer_identifiers WHERE active AND kind=%s AND value=%s',(kind,value))
        found.update(r[0] for r in cur.fetchall())
        cur.execute('SELECT id FROM customers WHERE contact_key=%s AND NOT EXISTS (SELECT 1 FROM customer_identifiers i WHERE i.customer_id=customers.id)',(value,))
        found.update(r[0] for r in cur.fetchall())
    return found

def save_identifiers(cur,cid,values,source):
    for kind,value in values:
        cur.execute('''INSERT INTO customer_identifiers(customer_id,kind,value,source)
            VALUES(%s,%s,%s,%s) ON CONFLICT(customer_id,kind,value) DO UPDATE SET active=true,source=CASE WHEN customer_identifiers.source='website' THEN 'website' ELSE EXCLUDED.source END''',(cid,kind,value,source))
        if kind=='email':
            cur.execute('INSERT INTO marketing_permissions(customer_id,email) VALUES(%s,%s) ON CONFLICT DO NOTHING',(cid,value))

def form_customer(cur,lead):
    # Intake already owns this lock; taking it again is safe. Import uses same lock.
    cur.execute('SELECT pg_advisory_xact_lock(1849202618)')
    values=identifiers(lead); found=candidates(cur,values)
    if len(found)==1:
        cid=next(iter(found))
        cur.execute('''UPDATE customers SET first_inquiry_at=LEAST(first_inquiry_at,%s),
            last_inquiry_at=GREATEST(last_inquiry_at,%s) WHERE id=%s''',(lead['created_at'],lead['created_at'],cid))
    else:
        # Ambiguous identity must never reject a genuine form or stop CRM delivery.
        # Preserve legacy primary-contact behavior, block marketing and flag review.
        contact=lead['contact'].strip()
        key=contact.casefold() if '@' in contact else re.sub(r'\D','',contact)
        cur.execute('''INSERT INTO customers(name,contact,contact_key,first_inquiry_at,last_inquiry_at)
            VALUES(%s,%s,%s,%s,%s) ON CONFLICT(contact_key) DO UPDATE SET
            last_inquiry_at=GREATEST(customers.last_inquiry_at,EXCLUDED.last_inquiry_at) RETURNING id''',
            (lead['name'],contact,key,lead['created_at'],lead['created_at']))
        cid=cur.fetchone()[0]
        if len(found)>1: conflict(cur,'form:'+lead['id'],'identifier_conflict',found|{cid})
    if re.match(r'^(?:QA\b|ТЕСТ\b|TEST\b)',lead.get('name',''),re.I):
        cur.execute('''UPDATE customers SET is_test=true WHERE id=%s
            AND NOT EXISTS(SELECT 1 FROM orders WHERE customer_id=%s)
            AND NOT EXISTS(SELECT 1 FROM customer_amo_links WHERE customer_id=%s)''',(cid,cid,cid))
    save_identifiers(cur,cid,values,'website')
    touch(cur,cid,lead['created_at'],'website','website',lead['id'],'first_known_inquiry',lead)
    return cid

def touch(cur,cid,when,channel,source,source_id,quality,data=None):
    data=data or {}
    if isinstance(when,(int,float)): when=datetime.fromtimestamp(when,timezone.utc)
    cur.execute('''INSERT INTO customer_touchpoints(customer_id,occurred_at,channel,source,source_id,
        quality,utm_source,utm_medium,utm_campaign,utm_content,utm_term,source_path,ym_client_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source,source_id) DO NOTHING''',
        (cid,when,channel,source,str(source_id),quality,*(data.get(k) for k in UTM),data.get('source_path'),data.get('ym_client_id')))
    cur.execute('''UPDATE customers c SET
        first_touch_at=t.occurred_at,first_touch_channel=t.channel,first_touch_source=t.source,
        first_touch_source_id=t.source_id,first_touch_quality=t.quality,
        first_utm_source=t.utm_source,first_utm_medium=t.utm_medium,first_utm_campaign=t.utm_campaign,
        first_utm_content=t.utm_content,first_utm_term=t.utm_term,
        first_source_path=t.source_path,first_ym_client_id=t.ym_client_id
        FROM (SELECT * FROM customer_touchpoints WHERE customer_id=%s ORDER BY occurred_at,id LIMIT 1) t
        WHERE c.id=%s''',(cid,cid))

def backfill_forms(cur):
    cur.execute('''SELECT o.id,o.customer_id,o.submission_id,o.created_at,o.email,o.phone,o.contact,
        o.utm_source,o.utm_medium,o.utm_campaign,o.utm_content,o.utm_term,o.source_path,o.ym_client_id
        FROM orders o JOIN customers c ON c.id=o.customer_id WHERE NOT c.is_test
        AND NOT EXISTS(SELECT 1 FROM customer_touchpoints t WHERE t.source='website' AND t.source_id=o.submission_id::text)
        ORDER BY o.created_at,o.id''')
    for row in cur.fetchall():
        data=dict(zip(('id','cid','uuid','created','email','phone','contact',*UTM,'source_path','ym_client_id'),row))
        vals=identifiers(data)
        found=candidates(cur,vals)
        if found-{data['cid']}:conflict(cur,'legacy:'+str(data['cid']),'legacy_identity_overlap',found|{data['cid']})
        save_identifiers(cur,data['cid'],vals,'website')
        touch(cur,data['cid'],data['created'],'website','website',data['uuid'],'first_known_inquiry',data)
