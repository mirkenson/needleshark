"""Synthetic PostgreSQL checks in a disposable schema, zero external sends."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import uuid
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn
import delivery_store as store


def main():
    dsn = os.environ['CRM_TEST_DSN']
    schema = 'needle_amo_test_' + uuid.uuid4().hex
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    def query(statement, args=()):
        with admin.cursor() as cur:
            cur.execute(statement, args)
            return cur.fetchall() if cur.description else None
    def lead():
        return dict(id=str(uuid.uuid4()), name='ТЕСТ АМО', contact='qa@example.invalid',
                    question='ТЕСТ: изолированная проверка очереди', consent=True,
                    email='qa@example.invalid', phone='+79990000000', utm_source='qa',
                    source_path='/', business_direction='chehly', business_material='oxford')
    secret, recipients = 'test-only-' * 4, ('qa@example.invalid',)
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            cur.execute(Path(__file__).with_name('schema.sql').read_text())
            migration = Path(__file__).with_name('migrations').joinpath('20261023_amo_delivery.sql').read_text()
            cur.execute(migration)
            cur.execute(migration)
        os.environ['CRM_DSN'] = make_dsn(dsn, options='-csearch_path=' + schema)
        store.initialize(amo_enabled=True)
        old = lead()
        assert store.enqueue(old, 'old', recipients, secret)[0] == 202
        assert store.enqueue(old, 'old', recipients, secret, amo_enabled=True)[0] == 200
        assert query('SELECT count(*) FROM lead_amo_deliveries') == [(0,)]
        new = lead()
        new['ym_client_id'] = '17613200001234567890'
        # Re-running an additive migration preserves old/new records and absence.
        migration = Path(__file__).with_name('migrations').joinpath('20261024_lead_clientid.sql').read_text()
        query(migration)
        query(migration)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: store.enqueue(new, 'new', recipients, secret, amo_enabled=True)[0], range(4)))
        assert sorted(results) == [200, 200, 200, 202]
        assert query('SELECT count(*) FROM lead_amo_deliveries') == [(1,)]
        assert query('SELECT count(*) FROM orders') == [(2,)]
        assert store.enqueue(dict(new, utm_source='changed'), 'new', recipients, secret, amo_enabled=True)[0] == 409
        assert store.enqueue(dict(new, ym_client_id='123'), 'new', recipients, secret, amo_enabled=True)[0] == 409
        assert query('SELECT ym_client_id FROM orders ORDER BY id') == [(None,), (new['ym_client_id'],)]
        assert query('SELECT payload FROM lead_submissions WHERE submission_id=%s', (new['id'],))[0][0]['ym_client_id'] == new['ym_client_id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = [job for job in pool.map(lambda _: store.claim('amo'), range(4)) if job]
        assert len(jobs) == 1
        job = jobs[0]
        assert job['lead']['email'] == new['email'] and job['lead']['phone'] == new['phone']
        assert job['lead']['utm_source'] == 'qa'
        assert job['lead']['ym_client_id'] == new['ym_client_id']
        assert store.save_amo_state(job, create_started=True)
        assert store.finish(job, 'amo_network_error')
        assert store.claim('amo') is None
        query("UPDATE lead_amo_deliveries SET retry_at=now()-interval '1 second'")
        stale = store.claim('amo')
        assert stale['create_started'] and stale['amo_lead_id'] is None
        query("UPDATE lead_amo_deliveries SET lease_until=now()-interval '1 second'")
        assert not store.save_amo_state(stale, create_started=False)
        resumed = store.claim('amo')
        assert not store.save_amo_state(stale, amo_lead_id=456)
        assert not store.finish(stale)
        assert store.save_amo_state(resumed, amo_lead_id=123)
        # Simulate restart after the remote id has been committed.
        query("UPDATE lead_amo_deliveries SET lease_until=now()-interval '1 second'")
        resumed = store.claim('amo')
        assert resumed['amo_lead_id'] == 123 and resumed['create_started']
        assert store.finish(resumed)
        assert query('SELECT status,amo_lead_id FROM lead_amo_deliveries') == [('sent', 123)]
        assert query('SELECT DISTINCT status FROM lead_deliveries') == [('pending',)]
        # An outbox failure must roll the new order and its email jobs back too.
        query('ALTER TABLE lead_amo_deliveries ADD CONSTRAINT qa_reject CHECK (false) NOT VALID')
        try:
            store.enqueue(lead(), 'rollback', recipients, secret, amo_enabled=True)
            raise AssertionError('Outbox insertion did not fail')
        except psycopg2.IntegrityError:
            pass
        for table in ('orders', 'lead_submissions', 'lead_deliveries'):
            assert query('SELECT count(*) FROM ' + table) == [(2,)]
        print('PASS amoCRM PostgreSQL: additive migration, no historical replay, atomic enqueue/rollback, concurrent UUID deduplication, preserved fields, independent mail, persistent create fence, restart recovery, stale-worker fencing and backoff; zero external sends')
    finally:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        admin.close()


if __name__ == '__main__':
    main()
