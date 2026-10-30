"""Isolated PostgreSQL integration tests, fake CRM rows, no external sends."""
import copy
import os
from pathlib import Path
import uuid
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn
import delivery_store as store
import customer_registry as registry
import customer_sync as sync


def main():
    dsn=os.environ['CRM_TEST_DSN']; schema='needle_sync_test_'+uuid.uuid4().hex
    admin=psycopg2.connect(dsn);admin.autocommit=True
    def query(q,args=()):
        with admin.cursor() as cur:
            cur.execute(q,args);return cur.fetchall() if cur.description else None
    def crm_contact(rid,name,email,phone=None):
        fs=[{'field_code':'EMAIL','values':[{'value':email}]}]
        if phone:fs.append({'field_code':'PHONE','values':[{'value':phone}]})
        return {'id':rid,'name':name,'created_at':1000,'updated_at':2000,
          'custom_fields_values':fs,'_embedded':{'companies':[{'id':55}]}}
    def event(eid,t,before,after):
        return dict(id=eid,entity_id=99,created_at=t,value_before=[{'lead_status':{'pipeline_id':1,'id':before}}],
                    value_after=[{'lead_status':{'pipeline_id':1,'id':after}}])
    def apply(snap,until=3000):
        with store.connection() as conn,conn.cursor() as cur:return sync.apply(cur,1,snap,until,2500)
    try:
        query(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        query(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        root=Path(__file__).parent
        query((root/'schema.sql').read_text())
        for p in sorted((root/'migrations').glob('*.sql')):query(p.read_text())
        query((root/'migrations/20261030_customer_sync.sql').read_text())
        os.environ['CRM_DSN']=make_dsn(dsn,options='-csearch_path='+schema)
        os.environ['CUSTOMER_SYNC_ENABLED']='1'
        query('INSERT INTO customer_sync_state(id,amo_account_id,activated_at) VALUES(1,1,2500)')
        lead=dict(id=str(uuid.uuid4()),name='Synthetic Person',contact='person@example.invalid',email='person@example.invalid',
            phone='+7 (999) 000-00-00',question='Isolated integration test',consent=True,utm_source='first',source_path='/business/')
        assert store.enqueue(lead,'ip',['qa@example.invalid'],'x'*32,amo_enabled=True)[0]==202
        cid=query('SELECT id FROM customers')[0][0]
        before=query('SELECT payload FROM lead_submissions')[0][0]
        snapshot={'companies':[dict(id=55,name='Synthetic Company',created_at=900,updated_at=2000)],
          'contacts':[crm_contact(77,'Synthetic Person','PERSON@example.invalid','89990000000')],
          'leads':[dict(id=99,name='Synthetic Deal',pipeline_id=1,status_id=20,created_at=2000,updated_at=2200,
            source_id=21223,custom_fields_values=[],_embedded={'companies':[{'id':55}],'contacts':[{'id':77,'is_main':True}]})],
          'events':[event('e1',2100,10,15),event('e2',2200,15,20)]}
        query('UPDATE lead_amo_deliveries SET amo_lead_id=99')
        apply(snapshot);apply(snapshot)
        assert query('SELECT count(*) FROM customers')==[(1,)]
        assert query('SELECT count(*) FROM companies')==[(1,)]
        assert query('SELECT count(*) FROM deal_stage_log')==[(2,)]
        assert query('SELECT count(*) FROM customer_company_history')==[(1,)]
        assert query('SELECT first_utm_source FROM customers')==[('first',)]
        assert query('SELECT payload FROM lead_submissions')[0][0]==before
        assert query('SELECT count(*) FROM lead_amo_deliveries')==[(1,)]
        assert query('SELECT count(*) FROM lead_deliveries')==[(1,)]
        # Reverse transition, delivered twice and out of order.
        reverse=copy.deepcopy(snapshot);reverse['leads'][0].update(status_id=10,updated_at=2800)
        reverse['events']=[event('e3',2800,20,10),event('e2',2200,15,20)]
        apply(reverse);apply(reverse)
        assert query('SELECT previous_stage_id,new_stage_id FROM deal_stage_log ORDER BY occurred_at DESC LIMIT 1')==[(20,10)]
        assert query('SELECT new_stage_id,ready_for_trigger FROM deal_latest_stage')==[(10,True)]
        assert query("SELECT historical FROM deal_stage_log WHERE source_event_id='e3'")==[(False,)]
        # Phone-only website request reuses CRM/email identity and still creates its CRM job.
        second=dict(lead,id=str(uuid.uuid4()),contact='89990000000',email=None,phone='89990000000',utm_source='later')
        assert store.enqueue(second,'ip2',['qa@example.invalid'],'x'*32,amo_enabled=True)[0]==202
        assert store.enqueue(second,'ip2',['qa@example.invalid'],'x'*32,amo_enabled=True)[0]==200
        assert query('SELECT count(*) FROM customers')==[(1,)]
        assert query('SELECT count(*) FROM lead_amo_deliveries')==[(2,)]
        assert query('SELECT first_utm_source FROM customers')==[('first',)]
        # CRM-only contact: no fake website order and no SMTP/CRM/LOOP jobs.
        fresh=copy.deepcopy(reverse);fresh['contacts'].append(crm_contact(78,'Second Person','second@example.invalid'))
        apply(fresh)
        assert query('SELECT count(*) FROM customers')==[(2,)]
        assert query('SELECT count(*) FROM orders')==[(2,)]
        # Email of A plus phone of B blocks import instead of silently merging.
        bad=copy.deepcopy(fresh);bad['contacts'].append(crm_contact(79,'Conflict','second@example.invalid','79990000000'))
        apply(bad)
        assert query('SELECT count(*) FROM customers')==[(2,)]
        assert query("SELECT reason FROM customer_sync_conflicts WHERE object_key='amo_contact:79'")==[('identifier_conflict',)]
        # Late duplicate is idempotent; malformed event rolls back the whole cursor update.
        invalid=copy.deepcopy(reverse);invalid['events']=[dict(event('bad',2900,10,30),value_before=[])]
        cursor=query('SELECT events_until FROM customer_sync_state')
        try:apply(invalid,9999);raise AssertionError('Expected validation failure')
        except ValueError:pass
        assert query('SELECT events_until FROM customer_sync_state')==cursor
        assert query("SELECT count(*) FROM deal_stage_log WHERE source_event_id='bad'")==[(0,)]
        # Same-second conflicting transitions cannot drive an automatic email.
        tied=copy.deepcopy(reverse);tied['events']=[event('e4',2800,10,12)]
        apply(tied)
        assert query('SELECT ready_for_trigger FROM deal_latest_stage')==[(False,)]
        # Guard against accidental CRM mutations even if code later calls the client incorrectly.
        try:sync.ReadClient.__new__(sync.ReadClient).request('POST','/api/v4/contacts',{});raise AssertionError('write allowed')
        except ValueError:pass
        # Missing deals retain their events for a later scan instead of dropping history.
        orphan=copy.deepcopy(reverse);orphan['events']=[dict(event('later-link',2900,10,15),entity_id=10001)]
        apply(orphan);apply(orphan)
        assert query('SELECT count(*) FROM crm_unresolved_events')==[(1,)]
        # Concurrent website intake and CRM import agree on one identity.
        from concurrent.futures import ThreadPoolExecutor
        concurrent=copy.deepcopy(reverse);concurrent['contacts'].append(crm_contact(100,'Concurrent Person','concurrent@example.invalid'))
        concurrent_lead=dict(lead,id=str(uuid.uuid4()),name='Concurrent Person',contact='concurrent@example.invalid',email='concurrent@example.invalid',phone=None)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(apply,concurrent)
            b=pool.submit(store.enqueue,concurrent_lead,'ip3',['qa@example.invalid'],'x'*32,False,True)
            a.result();assert b.result()[0]==202
        assert query("SELECT count(*) FROM customers WHERE contact_key='concurrent@example.invalid'")==[(1,)]
        # CRM aliases retain the union of their current email addresses.
        alias=crm_contact(101,'Concurrent Person','concurrent@example.invalid')
        alias['custom_fields_values'][0]['values'].append({'value':'alias@example.invalid'})
        aliases=copy.deepcopy(concurrent);aliases['contacts'].insert(0,alias)
        apply(aliases)
        assert query("SELECT active FROM customer_identifiers WHERE value='alias@example.invalid'")==[(True,)]
        apply(concurrent)
        assert query("SELECT active FROM customer_identifiers WHERE value='alias@example.invalid'")==[(False,)]
        assert query('SELECT archived FROM customer_amo_links WHERE amo_contact_id=101')==[(True,)]
        removed=copy.deepcopy(concurrent);removed['leads']=[];removed['events']=[]
        apply(removed)
        assert query('SELECT archived,ready_for_trigger FROM deal_latest_stage')==[(True,False)]
        # Export fence survives an unknown POST outcome; readback prevents a replay.
        import unisender_sync as uni
        from unittest.mock import patch
        class FakeUnisender:
            def __init__(self):self.contacts={};self.imports=0;self.lose_reply=False
            def contact(self,email):return copy.deepcopy(self.contacts.get(email))
            def call(self,method,args):
                assert method=='importContacts';self.imports+=1
                data={};i=0
                while f'field_names[{i}]' in args:
                    data[args[f'field_names[{i}]']]=args[f'data[0][{i}]'];i+=1
                if data['email'] not in self.contacts:assert data['contact_status']=='disabled'
                self.contacts[data['email']]={'email':{'status':'new'},'lists':[{'id':3}],
                    'fields':{k:v for k,v in data.items() if k in uni.FIELDS or k=='Name'}}
                if self.lose_reply:raise uni.ApiError('network_or_response')
                return {'total':1,'inserted':1,'updated':0,'invalid':0}
        fake=FakeUnisender();os.environ.update(UNISENDER_SYNC_ENABLED='1',UNISENDER_LIST_ID='3')
        with patch.object(uni,'Client',return_value=fake):
            uni.run_once();uni.run_once()
            assert fake.imports==1
            assert query('SELECT status FROM unisender_contact_sync')==[('accepted',)]
            query("UPDATE customers SET name='Updated Synthetic' WHERE contact_key='concurrent@example.invalid'")
            fake.lose_reply=True;uni.run_once()
            assert fake.imports==2
            assert query('SELECT status FROM unisender_contact_sync')==[('uncertain',)]
            query("UPDATE unisender_contact_sync SET retry_at=now()-interval '1 second'")
            uni.run_once()
            assert fake.imports==2
            assert query('SELECT status FROM unisender_contact_sync')==[('accepted',)]
        print('PASS customer sync PostgreSQL: repeatable migration/import, identity reuse, company links, immutable form snapshots, first attribution, no inbound outbound jobs, reverse stages, late/duplicate events, conflict isolation, cursor rollback, same-second ambiguity, read-only CRM client')
    finally:
        query(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)));admin.close()

if __name__=='__main__':main()
