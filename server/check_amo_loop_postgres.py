"""Isolated schema, fake CRM/Loop, real durable queue. No external sends."""
import os
from pathlib import Path
import time
import uuid
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn
import amo_loop


def main():
    dsn=os.environ['CRM_TEST_DSN']; schema='needle_loop_test_'+uuid.uuid4().hex
    admin=psycopg2.connect(dsn); admin.autocommit=True
    def query(q,args=()):
        with admin.cursor() as c:
            c.execute(q,args)
            return c.fetchall() if c.description else None
    try:
        query(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        query(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        query('CREATE TABLE lead_amo_deliveries(id BIGINT)')
        migration=Path(__file__).with_name('migrations').joinpath('20261028_amo_fields_loop.sql').read_text()
        query(migration); query(migration)
        os.environ['CRM_DSN']=make_dsn(dsn,options='-csearch_path='+schema)
        now=int(time.time()); config={'start':now-1000,'url':'https://neesha.loop.ru/hooks/'+'a'*26,'amo':{'base':'https://example.amocrm.ru'}}
        row={'id':42,'name':'QA','created_at':now-100}
        with patch('amo_loop.discover',return_value=[row]),patch('amo_loop.post',return_value=('sent',None)) as post:
            amo_loop.run_once(config,MagicMock())
            assert query('SELECT status,attempts FROM amo_loop_notifications')==[('sent',1)]
            query('UPDATE amo_loop_cursor SET scanned_until=%s',(now-100,))
            amo_loop.run_once(config,MagicMock())
            assert post.call_count==1
        # Simulate a crash after POST fence and before persisting its reply.
        query("INSERT INTO amo_loop_notifications(lead_id,title,created_at,status) VALUES(43,'QA',%s,'sending')",(now-100,))
        query('UPDATE amo_loop_cursor SET scanned_until=%s',(now-100,))
        with patch('amo_loop.discover',return_value=[]),patch('amo_loop.post') as post:
            amo_loop.run_once(config,MagicMock()); post.assert_not_called()
            assert query('SELECT status FROM amo_loop_notifications WHERE lead_id=43')==[('uncertain',)]
        # A scan failure must retain its cursor; retry recovers the same window.
        query('UPDATE amo_loop_cursor SET scanned_until=%s',(now-100,))
        with patch('amo_loop.discover',side_effect=RuntimeError('QA')):
            try: amo_loop.run_once(config,MagicMock())
            except RuntimeError: pass
        assert query('SELECT scanned_until FROM amo_loop_cursor')==[(now-100,)]
        # An explicit rejection is queued for a later retry, not marked sent.
        row={'id':44,'name':'QA','created_at':now-100}
        with patch('amo_loop.discover',return_value=[row]),patch('amo_loop.post',return_value=('pending','loop_http_429')):
            amo_loop.run_once(config,MagicMock())
            assert query('SELECT status,sent_at FROM amo_loop_notifications WHERE lead_id=44')==[('pending',None)]
        print('PASS CRM LOOP PostgreSQL: duplicate suppression, durable fence, interrupted POST held, scan cursor recovery, rejected send retry, no external sends')
    finally:
        query(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)));admin.close()

if __name__=='__main__': main()
