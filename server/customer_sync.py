"""Read-only amoCRM -> local registry. No outbound CRM calls or email triggers."""
import json
import os
import re
import time
from datetime import datetime, timezone
import amo_delivery
import customer_registry as registry
import delivery_store

class ReadClient(amo_delivery.Client):
    def request(self,method,path,payload=None):
        if method!='GET' or payload is not None: raise ValueError('sync_read_only')
        return super().request(method,path)

    def all(self,entity,params=None):
        import urllib.parse
        for page in range(1,1001):
            query=urllib.parse.urlencode(dict(params or {},page=page,limit=250))
            data=self.request('GET','/api/v4/'+entity+'?'+query)
            rows=data.get('_embedded',{}).get(entity.rsplit('/',1)[-1],[])
            if not isinstance(rows,list):raise ValueError('sync_invalid_collection')
            if data and not rows and data.get('_links',{}).get('next'):raise ValueError('sync_empty_page')
            yield from rows
            if not data.get('_links',{}).get('next'):return
        raise ValueError('sync_page_limit')

def fields(row):
    return {f.get('field_code') or f.get('field_name'): [v.get('value') for v in f.get('values',[])]
            for f in row.get('custom_fields_values') or []}

def one(row,code):
    v=fields(row).get(code) or []
    return str(v[0]) if v and v[0] is not None else None

def contact_values(row):
    result=set()
    for kind in ('email','phone'):
        for value in fields(row).get(kind.upper(),[]):
            normalized=registry.normalize(kind,value)
            if normalized:result.add((kind,normalized))
    return sorted(result)

def clearly_test(row):
    # Strong label at beginning, not substring in a normal customer question/name.
    return bool(re.match(r'^(?:ТЕСТ\b|TEST\b|QA\b)',row.get('name',''),re.I))

def contact(cur,account,row,company_map):
    rid=row['id'];key='amo_contact:'+str(rid)
    cur.execute('SELECT customer_id,source_updated_at FROM customer_amo_links WHERE amo_account_id=%s AND amo_contact_id=%s',(account,rid))
    link=cur.fetchone();vals=contact_values(row)
    found=registry.candidates(cur,vals)
    if link and found-{link[0]}:
        registry.conflict(cur,key,'mapped_identifier_conflict',found|{link[0]});return link[0]
    if not link and len(found)>1:
        registry.conflict(cur,key,'identifier_conflict',found);return None
    if link:
        cid=link[0]
        if row['updated_at']<link[1]:return cid
    elif found:
        cid=next(iter(found))
        cur.execute('SELECT name FROM customers WHERE id=%s',(cid,));existing_name=cur.fetchone()[0]
        cur.execute('SELECT 1 FROM customer_amo_links WHERE customer_id=%s AND NOT archived LIMIT 1',(cid,))
        if cur.fetchone() and existing_name.strip().casefold()!=row.get('name','').strip().casefold():
            registry.conflict(cur,key,'shared_identifier_review',found);return None
    else:
        value=next((v for k,v in vals if k=='email'),next((v for k,v in vals if k=='phone'),'amo:'+str(account)+':'+str(rid)))
        created=datetime.fromtimestamp(row['created_at'],timezone.utc)
        cur.execute('''INSERT INTO customers(name,contact,contact_key,first_inquiry_at,last_inquiry_at)
          VALUES(%s,%s,%s,%s,%s) ON CONFLICT(contact_key) DO NOTHING RETURNING id''',
          (row.get('name') or 'Контакт amoCRM',value,value,created,created))
        result=cur.fetchone()
        if not result:
            registry.conflict(cur,key,'legacy_key_conflict');return None
        cid=result[0]
    cur.execute('''INSERT INTO customer_amo_links(amo_account_id,amo_contact_id,customer_id,source_updated_at)
        VALUES(%s,%s,%s,%s) ON CONFLICT(amo_account_id,amo_contact_id) DO UPDATE SET
        source_updated_at=EXCLUDED.source_updated_at,archived=false''',(account,rid,cid,row['updated_at']))
    if row.get('name'):
        cur.execute('UPDATE customers SET name=%s WHERE id=%s',(row['name'],cid))
    registry.save_identifiers(cur,cid,vals,'amocrm')
    companies=row.get('_embedded',{}).get('companies',[])
    if len(companies)>1:registry.conflict(cur,key,'multiple_companies',(cid,))
    elif len(companies)==1 and companies[0]['id'] in company_map:
        company=company_map[companies[0]['id']]
        cur.execute('SELECT company_id FROM customers WHERE id=%s',(cid,));old=cur.fetchone()[0]
        if old!=company:
            cur.execute('''INSERT INTO customer_company_history(customer_id,previous_company_id,company_id,source)
                VALUES(%s,%s,%s,'amocrm')''',(cid,old,company))
            cur.execute('UPDATE customers SET company_id=%s WHERE id=%s',(company,cid))
    # Empty company/contact collections are not used to erase manager data automatically.
    return cid

def stage_value(event,key):
    value=event.get(key) or []
    v=value[0].get('lead_status') if len(value)==1 else None
    if not isinstance(v,dict) or type(v.get('id')) is not int or type(v.get('pipeline_id')) is not int:
        raise ValueError('sync_invalid_stage_event')
    return v['pipeline_id'],v['id']

def stage_event(cur,event,deal_id,cid,historical):
    before=stage_value(event,'value_before');after=stage_value(event,'value_after')
    cur.execute('''INSERT INTO deal_stage_log(deal_id,customer_id,source_event_id,previous_pipeline_id,
        previous_stage_id,new_pipeline_id,new_stage_id,occurred_at,event_kind,historical)
        VALUES(%s,%s,%s,%s,%s,%s,%s,to_timestamp(%s),'transition',%s)
        ON CONFLICT(deal_id,source_event_id) DO NOTHING''',
        (deal_id,cid,event['id'],*before,*after,event['created_at'],historical))

def apply(cur,account,snapshot,until,activated):
    cur.execute('SELECT pg_advisory_xact_lock(1849202618)')
    registry.backfill_forms(cur)
    for pipeline in snapshot.get('pipelines',[]):
        for stage in pipeline.get('_embedded',{}).get('statuses',[]):
            cur.execute('''INSERT INTO crm_stages(amo_account_id,pipeline_id,stage_id,pipeline_name,stage_name)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(amo_account_id,pipeline_id,stage_id) DO UPDATE SET
                pipeline_name=EXCLUDED.pipeline_name,stage_name=EXCLUDED.stage_name''',
                (account,pipeline['id'],stage['id'],pipeline['name'],stage['name']))
    cur.execute('SELECT entity_type,amo_id FROM customer_sync_exclusions')
    excluded={'lead':set(),'contact':set(),'company':set()}
    for kind,rid in cur.fetchall():excluded[kind].add(rid)
    contacts=snapshot['contacts'];leads=snapshot['leads'];companies=snapshot['companies']
    for kind,rows in (('lead',leads),('contact',contacts),('company',companies)):
        excluded[kind].update(r['id'] for r in rows if clearly_test(r))
    # Exclude a contact linked ONLY to reviewed test leads; shared real contacts survive.
    relations={}
    for r in leads:
        for c in r.get('_embedded',{}).get('contacts',[]):relations.setdefault(c['id'],set()).add(r['id'])
    excluded['contact'].update(cid for cid,lids in relations.items() if lids and lids<=excluded['lead'])
    company_map={}
    for row in companies:
        if row['id'] in excluded['company']:continue
        cur.execute('''INSERT INTO companies(amo_account_id,amo_company_id,name,inn,kpp,details,source_updated_at)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT(amo_account_id,amo_company_id) DO UPDATE SET
            name=EXCLUDED.name,details=EXCLUDED.details,inn=COALESCE(EXCLUDED.inn,companies.inn),
            kpp=COALESCE(EXCLUDED.kpp,companies.kpp),source_updated_at=EXCLUDED.source_updated_at,archived=false
            WHERE companies.source_updated_at<=EXCLUDED.source_updated_at RETURNING id''',
            (account,row['id'],row.get('name') or 'Компания amoCRM',one(row,'ИНН'),one(row,'КПП'),json.dumps(fields(row),ensure_ascii=False),row['updated_at']))
        result=cur.fetchone()
        if not result:
            cur.execute('SELECT id FROM companies WHERE amo_account_id=%s AND amo_company_id=%s',(account,row['id']));result=cur.fetchone()
        company_map[row['id']]=result[0]
    contact_map={}
    for row in contacts:
        if row['id'] in excluded['contact']:continue
        cid=contact(cur,account,row,company_map)
        if cid:contact_map[row['id']]=cid
    # Keep the union of current identifiers across all CRM aliases of a person.
    # Older snapshots must not deactivate identifiers from a newer contact version.
    stale_cids=set()
    for row in contacts:
        if row['id'] not in contact_map:continue
        cur.execute('SELECT source_updated_at FROM customer_amo_links WHERE amo_account_id=%s AND amo_contact_id=%s',(account,row['id']))
        if cur.fetchone()[0]>row['updated_at']:stale_cids.add(contact_map[row['id']])
    cur.execute("UPDATE customer_identifiers SET active=false WHERE source='amocrm' AND NOT (customer_id=ANY(%s))",(list(stale_cids),))
    for row in contacts:
        cid=contact_map.get(row['id'])
        if cid:
            for kind,value in contact_values(row):
                cur.execute('UPDATE customer_identifiers SET active=true WHERE customer_id=%s AND kind=%s AND value=%s',(cid,kind,value))
    deal_map={};main_map={};snapshots={}
    for row in leads:
        rid=row['id']
        if rid in excluded['lead']:continue
        cs=row.get('_embedded',{}).get('companies',[])
        company=company_map.get(cs[0]['id']) if len(cs)==1 else None
        cur.execute('SELECT o.id FROM orders o JOIN lead_amo_deliveries a USING(submission_id) WHERE a.amo_lead_id=%s',(rid,))
        order=cur.fetchone()
        cur.execute('''INSERT INTO crm_deals(amo_account_id,amo_lead_id,name,pipeline_id,stage_id,company_id,order_id,source_created_at,source_updated_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(amo_account_id,amo_lead_id) DO UPDATE SET
            name=EXCLUDED.name,pipeline_id=EXCLUDED.pipeline_id,stage_id=EXCLUDED.stage_id,
            company_id=COALESCE(EXCLUDED.company_id,crm_deals.company_id),order_id=COALESCE(EXCLUDED.order_id,crm_deals.order_id),
            source_updated_at=EXCLUDED.source_updated_at,archived=false
            WHERE crm_deals.source_updated_at<=EXCLUDED.source_updated_at RETURNING id''',
            (account,rid,row.get('name') or 'Сделка amoCRM',row['pipeline_id'],row['status_id'],company,order[0] if order else None,row['created_at'],row['updated_at']))
        result=cur.fetchone()
        if not result:
            cur.execute('SELECT id FROM crm_deals WHERE amo_account_id=%s AND amo_lead_id=%s',(account,rid))
            did=cur.fetchone()[0];deal_map[rid]=did
            cur.execute('SELECT customer_id FROM crm_deal_contacts WHERE deal_id=%s AND is_main ORDER BY customer_id LIMIT 1',(did,))
            old_main=cur.fetchone();main_map[did]=old_main[0] if old_main else None
            continue
        did=result[0];deal_map[rid]=did;snapshots[did]=row
        linked=row.get('_embedded',{}).get('contacts',[])
        cur.execute('DELETE FROM crm_deal_contacts WHERE deal_id=%s',(did,))
        main=None
        for c in linked:
            cid=contact_map.get(c['id'])
            if not cid:continue
            is_main=bool(c.get('is_main')) or len(linked)==1
            cur.execute('''INSERT INTO crm_deal_contacts(deal_id,customer_id,is_main) VALUES(%s,%s,%s)
                ON CONFLICT(deal_id,customer_id) DO UPDATE SET is_main=crm_deal_contacts.is_main OR EXCLUDED.is_main''',(did,cid,is_main))
            if is_main:main=cid
            # Website attribution is already preserved from its original order.
            if not order:
                data={k:one(row,k.upper()) for k in registry.UTM}
                data['ym_client_id']=one(row,'_YM_UID')
                raw_path=one(row,'NS_PAGE')
                if raw_path:
                    from urllib.parse import urlsplit
                    parts=urlsplit(raw_path)
                    if parts.hostname in ('needle-shark.ru','needleshark.ru'):data['source_path']=parts.path
                channel='email' if row.get('source_id')==21223 else 'crm'
                registry.touch(cur,cid,row['created_at'],channel,'amocrm_deal',str(account)+':'+str(rid)+':'+str(cid),'crm_record_created',data)
        main_map[did]=main
    for event in sorted(snapshot['events'],key=lambda r:(r['created_at'],r['id'])):
        did=deal_map.get(event['entity_id'])
        if not did:
            if event['entity_id'] not in excluded['lead']:
                cur.execute('''INSERT INTO crm_unresolved_events(source_event_id,event_data,reason) VALUES(%s,%s::jsonb,'deal_unavailable') ON CONFLICT DO NOTHING''',(event['id'],json.dumps(event)))
            continue
        stage_event(cur,event,did,main_map[did],event['created_at']<activated)
        cur.execute('DELETE FROM crm_unresolved_events WHERE source_event_id=%s',(event['id'],))
    for did,row in snapshots.items():
        cur.execute('SELECT new_pipeline_id,new_stage_id FROM deal_stage_log WHERE deal_id=%s ORDER BY occurred_at DESC,source_event_id DESC LIMIT 1',(did,))
        previous=cur.fetchone()
        current=(row['pipeline_id'],row['status_id'])
        if previous!=current:
            kind='baseline' if previous is None else 'reconciliation'
            cur.execute('''INSERT INTO deal_stage_log(deal_id,customer_id,source_event_id,previous_pipeline_id,previous_stage_id,
              new_pipeline_id,new_stage_id,occurred_at,event_kind,historical)
              VALUES(%s,%s,%s,%s,%s,%s,%s,to_timestamp(%s),%s,true) ON CONFLICT DO NOTHING''',
              (did,main_map[did],kind+':'+str(row['updated_at'])+':'+str(row['status_id']),
               *(previous or (None,None)),*current,row['updated_at'],kind))
    for table,column,ids in (
        ('companies','amo_company_id',list(company_map)),
        ('customer_amo_links','amo_contact_id',list(contact_map)),
        ('crm_deals','amo_lead_id',list(deal_map)),
    ):
        cur.execute(f'UPDATE {table} SET archived=true WHERE amo_account_id=%s AND NOT ({column}=ANY(%s))',(account,ids))
    cur.execute('''UPDATE customer_sync_state SET events_until=%s,last_success_at=now(),last_error=NULL,
        baseline_complete=true WHERE id=1''',(until,))
    return {'companies':len(company_map),'contacts':len(contact_map),'deals':len(deal_map),'events_read':len(snapshot['events'])}

def run_once():
    if not registry.enabled():return
    with delivery_store.connection() as guard,guard.cursor() as lock:
        lock.execute('SELECT pg_try_advisory_lock(1849202630)')
        if not lock.fetchone()[0]:return
        with delivery_store.connection() as conn,conn.cursor() as cur:
            cur.execute('SELECT amo_account_id,events_until,activated_at,EXTRACT(EPOCH FROM last_success_at) FROM customer_sync_state WHERE id=1')
            state=cur.fetchone()
        if state and state[3] and time.time()-float(state[3])<60:return
        try:
            client=ReadClient(amo_delivery.configuration())
            account=client.request('GET','/api/v4/account')['id']
            if state and state[0]!=account:raise ValueError('sync_account_mismatch')
            activated=state[2] if state else int(time.time())
            if not state:
                with delivery_store.connection() as conn,conn.cursor() as cur:
                    cur.execute('INSERT INTO customer_sync_state(id,amo_account_id,activated_at) VALUES(1,%s,%s) ON CONFLICT DO NOTHING',(account,activated))
            since=max(0,state[1]-300) if state else 0
            until=int(time.time())-5
            if state and until<state[1]:return
            snapshot={entity:list(client.all(entity,{'with':'contacts,source_id'} if entity=='leads' else {}))
                      for entity in ('companies','contacts','leads')}
            snapshot['pipelines']=list(client.all('leads/pipelines'))
            snapshot['events']=list(client.all('events',{'filter[type]':'lead_status_changed','filter[created_at][from]':since,'filter[created_at][to]':until}))
            with delivery_store.connection() as conn,conn.cursor() as cur:
                cur.execute('SELECT event_data FROM crm_unresolved_events')
                snapshot['events'].extend(r[0] for r in cur.fetchall())
                cur.execute('''INSERT INTO customer_sync_state(id,amo_account_id,activated_at) VALUES(1,%s,%s) ON CONFLICT DO NOTHING''',(account,activated))
                apply(cur,account,snapshot,until,activated)
        except Exception as error:
            code=error.code if isinstance(error,amo_delivery.DeliveryError) else 'sync_failed'
            with delivery_store.connection() as conn,conn.cursor() as cur:
                cur.execute('UPDATE customer_sync_state SET last_error=%s WHERE id=1',(code,))
            print('Customer sync:',code,flush=True)
            raise RuntimeError('Customer sync retry') from None
