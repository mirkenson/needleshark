"""Integration checks in a disposable schema; never sends mail or touches public orders."""
import base64
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
    schema = 'needle_delivery_test_' + uuid.uuid4().hex
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    secret = 'test-only-' * 4
    recipient = 'test@example.invalid'
    def lead(**changes):
        return dict(dict(id=str(uuid.uuid4()), name='ТЕСТ', contact='test@example.invalid',
                    question='ТЕСТ очередь', consent=True, consent_documents=['https://needle-shark.ru/privacy-policy'],
                    business_intent='custom', business_company="ТЕСТ ' компания", source_path='/business/',
                    attachment={'name': 'ТЕСТ.pdf', 'type': 'application/pdf',
                                'data': base64.b64encode(b'%PDF-test').decode()}), **changes)
    def query(statement, args=()):
        with admin.cursor() as cur:
            cur.execute(statement, args)
            return cur.fetchall() if cur.description else None
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            cur.execute(Path(__file__).with_name('schema.sql').read_text())
            migration = Path(__file__).with_name('migrations').joinpath('20260918_server_delivery.sql').read_text()
            cur.execute(migration)
            cur.execute(migration)
            loop_migration = Path(__file__).with_name('migrations').joinpath('20260922_loop_delivery.sql').read_text()
            cur.execute(loop_migration)
            cur.execute(loop_migration)
        os.environ['CRM_DSN'] = make_dsn(dsn, options='-csearch_path=' + schema)
        store.initialize(loop_enabled=True)
        first = lead()
        assert store.enqueue(first, 'ip1', (recipient,), secret, loop_enabled=True)[0] == 202
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: store.enqueue(first, 'ip1', (recipient,), secret, loop_enabled=True)[0], range(4)))
        assert results == [200] * 4
        assert query('SELECT count(*) FROM orders') == [(1,)]
        assert query('SELECT count(*) FROM lead_deliveries') == [(1,)]
        assert query('SELECT count(*) FROM lead_loop_deliveries') == [(1,)]
        assert query('SELECT business_company,description FROM orders') == [(first['business_company'], first['question'])]
        assert bytes(query('SELECT content FROM lead_files')[0][0]) == b'%PDF-test'
        assert 'data' not in query('SELECT payload FROM lead_submissions')[0][0]['attachment']
        for change in ({'question': 'Changed'}, {'business_company': 'Changed'},
                       {'attachment': dict(first['attachment'], data=base64.b64encode(b'%PDF-changed').decode())}):
            assert store.enqueue(dict(first, **change), 'ip1', (recipient,), secret)[0] == 409
        broken = lead()
        try:
            store.enqueue(broken, 'ip2', (None,), secret)
            raise AssertionError('Expected recipient constraint failure')
        except psycopg2.IntegrityError:
            pass
        for table in ('orders', 'lead_submissions', 'lead_files', 'lead_deliveries'):
            assert query('SELECT count(*) FROM ' + table) == [(1,)], table
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _: store.claim(), range(4)))
        jobs = [job for job in claims if job]
        assert len(jobs) == 1
        job = jobs[0]
        assert job['lead']['attachment']['content'] == b'%PDF-test'
        assert store.finish(job, 'network_error')
        assert store.claim() is None  # Backoff is persistent, no immediate loop.
        assert query('SELECT attempts,last_error,status FROM lead_deliveries') == [(1, 'network_error', 'pending')]
        query("UPDATE lead_deliveries SET retry_at=now()-interval '1 second'")
        abandoned = store.claim()
        assert abandoned['attempts'] == 2
        query("UPDATE lead_deliveries SET lease_until=now()-interval '1 second'")
        recovered = store.claim()
        assert recovered['attempts'] == 3
        assert not store.finish(abandoned)  # A stale worker cannot finalize a reclaimed job.
        assert store.finish(recovered)
        assert store.claim() is None
        # A LOOP failure must not affect the already-sent email with the same numeric id.
        with ThreadPoolExecutor(max_workers=4) as pool:
            loop_claims = list(pool.map(lambda _: store.claim('loop'), range(4)))
        loop_jobs = [job for job in loop_claims if job]
        assert len(loop_jobs) == 1
        loop_job = loop_jobs[0]
        assert 'content' not in loop_job['lead']['attachment']
        assert store.finish(loop_job, 'loop_http_503')
        assert query('SELECT status FROM lead_deliveries') == [('sent',)]
        assert store.claim('loop') is None
        query("UPDATE lead_loop_deliveries SET retry_at=now()-interval '1 second'")
        stale_loop = store.claim('loop')
        query("UPDATE lead_loop_deliveries SET lease_until=now()-interval '1 second'")
        recovered_loop = store.claim('loop')
        assert recovered_loop['attempts'] == 3
        assert not store.finish(stale_loop)
        assert store.finish(recovered_loop)
        assert store.claim('loop') is None
        assert store.enqueue(first, 'ip1', (recipient,), secret, loop_enabled=True)[0] == 200
        assert query('SELECT count(*) FROM lead_loop_deliveries') == [(1,)]
        # Failure of LOOP enqueue rolls the entire new lead transaction back.
        query('ALTER TABLE lead_loop_deliveries ADD CONSTRAINT test_reject CHECK (false) NOT VALID')
        try:
            store.enqueue(lead(), 'ip2', (recipient,), secret, loop_enabled=True)
            raise AssertionError('Expected LOOP outbox insertion failure')
        except psycopg2.IntegrityError:
            pass
        query('ALTER TABLE lead_loop_deliveries DROP CONSTRAINT test_reject')
        for table in ('orders', 'lead_submissions', 'lead_files', 'lead_deliveries', 'lead_loop_deliveries'):
            assert query('SELECT count(*) FROM ' + table) == [(1,)], table
        assert store.enqueue(first, 'ip1', (recipient,), secret)[0] == 200
        assert query('SELECT count(*) FROM lead_files') == [(1,)]  # Files survive sent status.
        second = lead(attachment=None)
        second.pop('attachment')
        assert store.enqueue(second, 'ip2', (recipient, 'second@example.invalid'), secret)[0] == 202
        job1, job2 = store.claim(), store.claim()
        assert job1['recipient'] != job2['recipient']
        assert store.finish(job1, 'smtp_550') and store.finish(job2)
        assert query("SELECT status FROM lead_deliveries WHERE submission_id=%s ORDER BY id", (second['id'],)) == [('pending',), ('sent',)]
        for _ in range(10):
            assert store.enqueue(lead(), 'rate-ip', (recipient,), secret)[0] == 202
        assert store.enqueue(lead(), 'rate-ip', (recipient,), secret)[0] == 429
        assert query('SELECT count(*) FROM lead_loop_deliveries') == [(1,)]  # Disabled integration adds no jobs.
        print('PASS LOOP PostgreSQL: atomic enqueue/rollback, concurrent deduplication, independent mail state, text-only claim, durable retries, lease recovery, stale fencing, disabled mode; zero network sends')
        print('PASS PostgreSQL: atomic rollback (order/file/jobs), concurrent deduplication, file changes rejected, leases/restart recovery, stale fencing, backoff, per-recipient status, rate limit, private file persistence; zero SMTP sends')
    finally:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        admin.close()


if __name__ == '__main__':
    main()
