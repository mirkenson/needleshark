"""Private directory sync only. No send/subscribe/trigger methods are permitted."""
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import amo_delivery
import delivery_store

FIELDS={
 'NS_CUSTOMER_ID':'ID клиента Needle Shark','NS_COMPANY_ID':'ID компании Needle Shark',
 'NS_COMPANY_NAME':'Компания','NS_PHONE':'Телефон (справочно)',
 'NS_FIRST_CHANNEL':'Канал первого обращения','NS_FIRST_SOURCE':'UTM source первого обращения',
 'NS_FIRST_MEDIUM':'UTM medium первого обращения','NS_FIRST_CAMPAIGN':'UTM campaign первого обращения',
 'NS_FIRST_CONTENT':'UTM content первого обращения','NS_FIRST_TERM':'UTM term первого обращения',
 'NS_FIRST_AT':'Дата первого известного обращения','NS_FIRST_PAGE':'Страница первого обращения',
 'NS_PERMISSION':'Разрешение на рассылку'}

class ApiError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)

class Client:
    def __init__(self,key=None):
        self.key=key or Path(os.environ.get('UNISENDER_KEY_FILE','/etc/needle-shark/unisender.key')).read_text().strip()
        if not re.fullmatch('[A-Za-z0-9_-]{20,200}',self.key):raise ApiError('key_format')
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),amo_delivery.NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    def call(self,method,params=None):
        if method not in ('getContact','getLists','getFields','importContacts','createList','createField'):
            raise ApiError('method_forbidden')
        body=urllib.parse.urlencode(dict(params or {},api_key=self.key,format='json')).encode()
        req=urllib.request.Request('https://api.unisender.com/ru/api/'+method,data=body,
            headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'NeedleShark-Directory/1.0'})
        try:
            with self.opener.open(req,timeout=20) as r:
                raw=r.read(2*1024*1024+1)
                if len(raw)>2*1024*1024:raise ApiError('response_too_large')
                obj=json.loads(raw)
        except urllib.error.HTTPError as e:
            e.close();raise ApiError('http_'+str(e.code)) from None
        except (OSError,urllib.error.URLError,ValueError):raise ApiError('network_or_response') from None
        if obj.get('error'):
            code=str(obj.get('code','provider_error'))
            raise ApiError(code if re.fullmatch('[a-zA-Z0-9_]{1,60}',code) else 'provider_error')
        if 'result' not in obj:raise ApiError('result_missing')
        if obj.get('warnings'):raise ApiError('provider_warning')
        return obj['result']
    def contact(self,email):
        try:return self.call('getContact',{'email':email,'include_fields':1,'include_lists':1,'include_details':1})
        except ApiError as e:
            if e.code=='object_not_found':return None
            raise

def payload(row,list_id,remote):
    # New contacts are disabled, regardless of future permission flags. Enabling
    # actual messaging is a distinct future rollout. Existing statuses untouched.
    data={k:str(v) for k,v in row.items() if k in FIELDS and v is not None}
    data.update(email=row['email'],Name=row['name'])
    if remote is None:
        data.update(contact_status='disabled',email_list_ids=str(list_id))
    else:
        status=(remote.get('email') or {}).get('status')
        lists=remote.get('lists') or []
        if status not in ('unsubscribed','blocked') and not any(str(x.get('id'))==str(list_id) for x in lists):
            data['email_list_ids']=str(list_id)
    return data

def import_one(client,data):
    args={'overwrite_lists':0,'overwrite_tags':0}
    for i,(key,value) in enumerate(data.items()):
        args['field_names['+str(i)+']']=key;args['data[0]['+str(i)+']']=value
    result=client.call('importContacts',args)
    if result.get('total')!=1 or result.get('inserted',0)+result.get('updated',0)!=1 or result.get('invalid',0) or result.get('log'):
        raise ApiError('import_not_confirmed')

def matches(remote,data,list_id):
    if not isinstance(remote,dict):return False
    actual=remote.get('fields') or {}
    if any(str(actual.get(k,''))!=str(v) for k,v in data.items() if k in FIELDS or k=='Name'):return False
    return 'email_list_ids' not in data or any(str(x.get('id'))==str(list_id) for x in remote.get('lists') or [])

def projections(cur):
    cur.execute('''SELECT DISTINCT ON(c.id) c.id,c.name,i.value,co.id,co.name,
      (SELECT value FROM customer_identifiers WHERE customer_id=c.id AND kind='phone' AND active ORDER BY value LIMIT 1),
      c.first_touch_channel,c.first_utm_source,c.first_utm_medium,c.first_utm_campaign,
      c.first_utm_content,c.first_utm_term,c.first_touch_at::text,c.first_source_path,
      COALESCE(p.status,'unknown')
      FROM customers c JOIN customer_identifiers i ON i.customer_id=c.id AND i.kind='email' AND i.active
      LEFT JOIN companies co ON co.id=c.company_id LEFT JOIN marketing_permissions p ON p.customer_id=c.id AND p.email=i.value
      WHERE NOT c.is_test AND NOT c.sync_conflict
      AND (EXISTS(SELECT 1 FROM orders o WHERE o.customer_id=c.id) OR EXISTS(SELECT 1 FROM customer_amo_links a WHERE a.customer_id=c.id AND NOT a.archived))
      AND (SELECT count(DISTINCT customer_id) FROM customer_identifiers WHERE kind='email' AND value=i.value)=1
      ORDER BY c.id,(i.value=c.contact_key) DESC,i.value''')
    names=('NS_CUSTOMER_ID','name','email','NS_COMPANY_ID','NS_COMPANY_NAME','NS_PHONE',
           'NS_FIRST_CHANNEL','NS_FIRST_SOURCE','NS_FIRST_MEDIUM','NS_FIRST_CAMPAIGN',
           'NS_FIRST_CONTENT','NS_FIRST_TERM','NS_FIRST_AT','NS_FIRST_PAGE','NS_PERMISSION')
    return [dict(zip(names,r)) for r in cur.fetchall()]

def run_once():
    if os.environ.get('UNISENDER_SYNC_ENABLED')!='1':return
    list_id=os.environ.get('UNISENDER_LIST_ID','')
    if not re.fullmatch('[1-9][0-9]*',list_id):raise ApiError('list_config')
    with delivery_store.connection() as guard,guard.cursor() as lock:
        lock.execute('SELECT pg_try_advisory_lock(1849202631)')
        if not lock.fetchone()[0]:return
        with delivery_store.connection() as conn,conn.cursor() as cur:
            cur.execute('SELECT baseline_complete FROM customer_sync_state WHERE id=1')
            if cur.fetchone()!=(True,):return
            rows=projections(cur)
        client=Client()
        for row in rows:
            email=row['email'];cid=row['NS_CUSTOMER_ID']
            digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            with delivery_store.connection() as conn,conn.cursor() as cur:
                cur.execute('SELECT payload_hash,status,retry_at>now() FROM unisender_contact_sync WHERE email=%s',(email,))
                old=cur.fetchone()
                if old and old[0]==digest and old[2]:continue
            fenced=bool(old and old[1]=='uncertain')
            try:
                remote=client.contact(email)
                status=(remote or {}).get('email',{}).get('status')
                list_withdrawn=any(str(x.get('id'))==str(list_id) and x.get('status') in ('unsubscribed','blocked') for x in (remote or {}).get('lists') or [])
                if status in ('unsubscribed','blocked') or list_withdrawn:
                    with delivery_store.connection() as conn,conn.cursor() as cur:
                        cur.execute("UPDATE marketing_permissions SET status='withdrawn',updated_at=now() WHERE customer_id=%s AND email=%s AND status<>'withdrawn'",(cid,email))
                    row['NS_PERMISSION']='withdrawn'
                    digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                data=payload(row,list_id,remote)
                if matches(remote,data,list_id):result='accepted';error=None
                elif old and old[1]=='uncertain':result='uncertain';error='reconcile_required'
                else:
                    # Persist send fence. Restart after POST never blindly repeats it.
                    with delivery_store.connection() as conn,conn.cursor() as cur:
                        cur.execute('''INSERT INTO unisender_contact_sync(email,customer_id,payload_hash,status,attempts)
                            VALUES(%s,%s,%s,'uncertain',1) ON CONFLICT(email) DO UPDATE SET
                            payload_hash=EXCLUDED.payload_hash,status='uncertain',attempts=unisender_contact_sync.attempts+1''',(email,cid,digest))
                    fenced=True
                    import_one(client,data)
                    if not matches(client.contact(email),data,list_id):raise ApiError('readback_mismatch')
                    result='accepted';error=None
            except ApiError as exc:
                result='uncertain' if fenced else 'pending';error=exc.code
            with delivery_store.connection() as conn,conn.cursor() as cur:
                cur.execute('''INSERT INTO unisender_contact_sync(email,customer_id,payload_hash,status,last_error,retry_at,synced_at)
                  VALUES(%s,%s,%s,%s,%s,now()+interval '10 minutes',CASE WHEN %s='accepted' THEN now() END)
                  ON CONFLICT(email) DO UPDATE SET payload_hash=EXCLUDED.payload_hash,status=EXCLUDED.status,
                  last_error=EXCLUDED.last_error,retry_at=EXCLUDED.retry_at,synced_at=EXCLUDED.synced_at''',
                  (email,cid,digest,result,error,result))
