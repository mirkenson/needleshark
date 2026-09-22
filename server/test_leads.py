import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import unittest
from unittest.mock import patch
import leads


class LeadTests(unittest.TestCase):
    def setUp(self):
        self.data = {'id': '12345678-1234-4234-8234-123456789abc', 'name': 'ТЕСТ',
                     'contact': 'test@example.invalid', 'question': 'Тестовая заявка', 'consent': True}

    def test_http_origin_gate_allows_owned_domains_only(self):
        # Exercise the real HTTP handler with an invalid payload so no lead is saved.
        from http.server import ThreadingHTTPServer
        from http.client import HTTPConnection
        import threading
        server = ThreadingHTTPServer(('127.0.0.1', 0), leads.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for origin in ('https://needle-shark.ru', 'https://www.needle-shark.ru',
                           'https://needleshark.ru', 'https://www.needleshark.ru',
                           'https://needle-shark.ru.evil.example', 'http://needle-shark.ru'):
                conn = HTTPConnection(*server.server_address)
                conn.request('POST', '/api/leads', '{}', {'Origin': origin, 'Content-Type': 'application/json'})
                response = conn.getresponse()
                self.assertEqual(response.status, 403 if origin in ('https://needle-shark.ru.evil.example', 'http://needle-shark.ru') else 400)
                response.read()
                conn.close()
            self.assertEqual(leads.validate(self.data)['consent_documents'],
                             ['https://needle-shark.ru/user-agreement', 'https://needle-shark.ru/privacy-policy'])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_validation_rejects_spam_bad_contact_and_bad_attachment(self):
        for changes in [{'website': 'spam'}, {'contact': 'not a contact'}, {'attachment': {'name': 'bad.png', 'type': 'image/png', 'data': 'aGVsbG8='}}]:
            with self.assertRaises(ValueError):
                leads.validate(dict(self.data, **changes))
        self.assertEqual(leads.validate(dict(self.data, contact='+7 (999) 123-45-67'))['name'], 'ТЕСТ')

    def test_consent_requires_explicit_boolean_true(self):
        for value in [False, None, 'true', 1]:
            with self.assertRaises(ValueError):
                leads.validate(dict(self.data, consent=value))
        missing = dict(self.data)
        del missing['consent']
        with self.assertRaises(ValueError):
            leads.validate(missing)
        self.assertIs(leads.validate(self.data)['consent'], True)

    def product_data(self):
        return dict(self.data, product_slug='chehol-na-kvadrocikl', product_name='Чехол на квадроцикл',
                    product_size='220 × 98 × 106', inquiry_type='wholesale', quantity=12,
                    source_path='/catalog/chehol-na-kvadrocikl/')

    def test_invalid_catalogue_metadata(self):
        for update in [{'quantity': True}, {'quantity': 0}, {'quantity': 1.5}, {'quantity': '12'},
                       {'quantity': 1000001}, {'product_slug': '../test'}, {'inquiry_type': 'unknown'},
                       {'product_size': 'not a size'}, {'product_name': ''},
                       {'source_path': 'https://other.example/'}, {'source_path': '/catalog/?contact=private'}]:
            with self.subTest(update=list(update)), self.assertRaises(ValueError):
                leads.validate(dict(self.product_data(), **update))

    def test_source_metadata_does_not_shorten_the_full_message_limit(self):
        for data in (dict(self.data, source_path='/'), self.product_data(),
                     dict(self.data, source_path='/business/', business_company='ТЕСТ', business_intent='custom')):
            self.assertEqual(leads.validate(dict(data, question='Я' * 5000))['question'], 'Я' * 5000)
            with self.assertRaises(ValueError):
                leads.validate(dict(data, question='Я' * 5001))

    def test_invalid_business_fields_and_client_link_are_not_accepted(self):
        for update in [{'business_intent': 'unknown'}, {'business_company': 'x' * 161},
                       {'business_intent': 1}, {'business_company': 'foo\nbar'}]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                leads.validate(dict(self.data, **update))
        self.assertNotIn('attachment_url', leads.validate(dict(self.data, attachment_url='https://evil.example/')))

    def test_valid_file_and_oversized_file(self):
        import base64
        attachment = {'name': 'test.pdf', 'type': 'application/pdf', 'data': base64.b64encode(b'%PDF-test').decode()}
        self.assertEqual(leads.validate(dict(self.data, attachment=attachment))['attachment']['name'], 'test.pdf')
        attachment['data'] = base64.b64encode(b'%PDF-' + b'x' * leads.MAX_FILE).decode()
        with self.assertRaises(ValueError):
            leads.validate(dict(self.data, attachment=attachment))

    def test_notification_preserves_original_and_business_fields(self):
        for intent in ('ready', 'custom', 'materials'):
            data = leads.validate(dict(self.product_data(), business_intent=intent,
                                  business_company='ТЕСТ компания', source_path='/business/'))
            enriched = leads.notification_payload(data)
            self.assertEqual(data['question'], self.data['question'])
            self.assertEqual(enriched['business_intent'], intent)
            for part in ('Количество, шт.: 12', 'Размер, см: 220 × 98 × 106', 'Компания / сфера: ТЕСТ компания'):
                self.assertIn(part, enriched['question'])

    def test_api_does_not_report_success_when_database_fails(self):
        import json
        import threading
        from http.server import ThreadingHTTPServer
        from http.client import HTTPConnection
        server = ThreadingHTTPServer(('127.0.0.1', 0), leads.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(leads, 'enqueue', side_effect=RuntimeError('database unavailable')):
                conn = HTTPConnection(*server.server_address)
                conn.request('POST', '/api/leads', json.dumps(self.data),
                             {'Origin': 'https://needle-shark.ru', 'Content-Type': 'application/json'})
                response = conn.getresponse()
                self.assertEqual(response.status, 503)
                self.assertFalse(json.loads(response.read())['ok'])
                conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_unconfigured_smtp_keeps_jobs_pending(self):
        with patch.object(leads.mail_delivery, 'smtp_config', return_value=None), patch.object(leads.delivery_store, 'claim') as claim:
            leads.deliver_once()
            claim.assert_not_called()

    def test_worker_retries_failures_and_continues_other_deliveries(self):
        jobs = [{'id': i, 'lead': self.data, 'recipient': 'test@example.invalid'} for i in (1, 2)]
        with patch.object(leads.mail_delivery, 'smtp_config', return_value={}), \
             patch.object(leads.delivery_store, 'claim', side_effect=[*jobs, None]), \
             patch.object(leads.mail_delivery, 'send', side_effect=[TimeoutError(), None]), \
             patch.object(leads.delivery_store, 'finish') as finish:
            leads.deliver_once()
        self.assertEqual(finish.call_args_list[0].args, (jobs[0], 'network_error'))
        self.assertEqual(finish.call_args_list[1].args, (jobs[1],))
