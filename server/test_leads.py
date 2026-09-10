import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import copy
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('leads', Path(__file__).with_name('leads.py'))
leads = importlib.util.module_from_spec(spec)
spec.loader.exec_module(leads)


class LeadQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        leads.DB = self.tmp.name + '/queue.sqlite3'
        leads.SECRET = 'test-only-' * 4
        leads.HOOK = 'https://script.google.com/macros/s/test/exec'
        leads.initialize()
        self.data = {'id': '12345678-1234-4234-8234-123456789abc', 'name': 'Тест', 'contact': 'test@example.com', 'question': 'Тестовая заявка', 'consent': True}

    def tearDown(self):
        self.tmp.cleanup()

    def test_duplicate_has_one_row_and_rejects_changed_content(self):
        self.assertEqual(leads.enqueue(copy.deepcopy(self.data), 'test-ip')[0], 202)
        self.assertEqual(leads.enqueue(copy.deepcopy(self.data), 'test-ip')[0], 200)
        changed = dict(self.data, question='Другая задача')
        self.assertEqual(leads.enqueue(changed, 'test-ip')[0], 409)
        with leads.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM leads').fetchone()[0], 1)

    def test_validation_rejects_spam_bad_contact_and_bad_attachment(self):
        for changes in [{'website': 'spam'}, {'contact': 'not a contact'}, {'attachment': {'name': 'bad.png', 'type': 'image/png', 'data': 'aGVsbG8='}}]:
            with self.assertRaises(ValueError):
                leads.validate(dict(self.data, **changes))
        self.assertEqual(leads.validate(dict(self.data, contact='+7 (999) 123-45-67'))['name'], 'Тест')

    def test_consent_requires_explicit_boolean_true(self):
        for value in [False, None, 'true', 1]:
            with self.assertRaises(ValueError):
                leads.validate(dict(self.data, consent=value))
        missing = dict(self.data)
        del missing['consent']
        with self.assertRaises(ValueError):
            leads.validate(missing)
        self.assertIs(leads.validate(self.data)['consent'], True)

    def test_database_failure_does_not_acknowledge_or_enqueue(self):
        with patch.object(leads, 'archive', side_effect=RuntimeError('database unavailable')):
            with self.assertRaises(RuntimeError):
                leads.enqueue(copy.deepcopy(self.data), 'test-ip')
        with leads.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM leads').fetchone()[0], 0)

    def test_failed_delivery_is_persisted_and_retried(self):
        leads.enqueue(copy.deepcopy(self.data), 'test-ip')
        with patch.object(leads, 'urlopen', side_effect=TimeoutError):
            leads.deliver_once()
        with leads.connect() as db:
            delivered, attempts, retry = db.execute('SELECT delivered,attempts,retry_at FROM leads').fetchone()
        self.assertIsNone(delivered)
        self.assertEqual(attempts, 1)
        self.assertGreater(retry, time.time())

    def test_acknowledgement_must_match_lead(self):
        leads.enqueue(copy.deepcopy(self.data), 'test-ip')
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return json.dumps({'ok': True, 'id': 'wrong'}).encode()
        with patch.object(leads, 'urlopen', return_value=Reply()):
            leads.deliver_once()
        with leads.connect() as db:
            self.assertIsNone(db.execute('SELECT delivered FROM leads').fetchone()[0])

    def test_successful_delivery_marks_queue(self):
        leads.enqueue(copy.deepcopy(self.data), 'test-ip')
        lead_id = self.data['id']
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return json.dumps({'ok': True, 'id': lead_id}).encode()
        with patch.object(leads, 'urlopen', return_value=Reply()):
            leads.deliver_once()
        with leads.connect() as db:
            self.assertIsNotNone(db.execute('SELECT delivered FROM leads').fetchone()[0])

    def product_data(self):
        return dict(self.data, product_slug='chehol-na-kvadrocikl', product_name='Чехол на квадроцикл',
                    product_size='220 × 98 × 106', inquiry_type='wholesale', quantity=12,
                    source_path='/catalog/chehol-na-kvadrocikl/')

    def test_catalogue_fields_reach_archive_queue_and_google_task(self):
        data = leads.validate(self.product_data())
        with patch.object(leads, 'archive') as archive:
            self.assertEqual(leads.enqueue(copy.deepcopy(data), 'test-ip')[0], 202)
            self.assertEqual(archive.call_args.args[0]['quantity'], 12)
        sent = []
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return json.dumps({'ok': True, 'id': data['id']}).encode()
        def send(request, **kwargs):
            sent.append(json.loads(request.data)['lead'])
            return Reply()
        with patch.object(leads, 'urlopen', side_effect=send):
            leads.deliver_once()
        self.assertIn('Количество, шт.: 12', sent[0]['question'])
        self.assertIn('Размер, см: 220 × 98 × 106', sent[0]['question'])
        self.assertIn('Тип обращения: Партия для бизнеса', sent[0]['question'])
        with leads.connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM leads').fetchone()[0])
            self.assertEqual(payload['question'], self.data['question'])
            self.assertEqual(payload['source_path'], '/catalog/chehol-na-kvadrocikl/')

    def test_catalogue_retry_rejects_changed_quantity_and_size(self):
        data = leads.validate(self.product_data())
        self.assertEqual(leads.enqueue(copy.deepcopy(data), 'test-ip')[0], 202)
        self.assertEqual(leads.enqueue(copy.deepcopy(data), 'test-ip')[0], 200)
        for update in [{'quantity': 13}, {'product_size': '255 × 140 × 120'}]:
            self.assertEqual(leads.enqueue(dict(data, **update), 'test-ip')[0], 409)

    def test_invalid_catalogue_metadata_and_oversized_google_task(self):
        for update in [{'quantity': True}, {'quantity': 0}, {'quantity': 1.5}, {'quantity': '12'},
                       {'quantity': 1000001}, {'product_slug': '../test'}, {'inquiry_type': 'unknown'},
                       {'product_size': 'not a size'}, {'product_name': ''},
                       {'source_path': 'https://other.example/'}, {'source_path': '/catalog/?contact=private'},
                       {'question': 'x' * 4900}]:
            with self.subTest(update=list(update)), self.assertRaises(ValueError):
                leads.validate(dict(self.product_data(), **update))

    def test_legacy_request_keeps_its_payload_shape(self):
        data = leads.validate(self.data)
        self.assertNotIn('quantity', data)
        self.assertEqual(leads.google_payload(data), data)

    def test_valid_file_and_oversized_file(self):
        import base64
        attachment = {'name': 'test.pdf', 'type': 'application/pdf', 'data': base64.b64encode(b'%PDF-test').decode()}
        self.assertEqual(leads.validate(dict(self.data, attachment=attachment))['attachment']['name'], 'test.pdf')
        attachment['data'] = base64.b64encode(b'%PDF-' + b'x' * leads.MAX_FILE).decode()
        with self.assertRaises(ValueError):
            leads.validate(dict(self.data, attachment=attachment))


if __name__ == '__main__':
    unittest.main()
