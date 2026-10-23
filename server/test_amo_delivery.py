import json
from pathlib import Path
import ssl
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).parent))
import amo_delivery as amo
import leads

ENV = {'AMO_ENABLED': '1', 'AMO_BASE_URL': 'https://example.amocrm.ru',
       'AMO_ACCESS_TOKEN': 'test-only-' * 5, 'AMO_PIPELINE_ID': '11', 'AMO_STATUS_ID': '12',
       'AMO_SUBMISSION_FIELD_ID': '21', 'AMO_DETAILS_FIELD_ID': '22', 'AMO_ORDER_FIELD_ID': '23'}


class AmoTests(unittest.TestCase):
    def setUp(self):
        self.config = amo.configuration(ENV)
        self.lead = dict(id='12345678-1234-4234-8234-123456789abc', order_id=42,
            name='ТЕСТ', contact='test@example.invalid', email='test@example.invalid', phone='+79990000000',
            question='ТЕСТ\n' + 'я' * 4995, created_at='2026-10-23T00:00:00Z',
            source_path='/napravleniya/chehly/', business_company='ТЕСТ компания',
            business_direction='chehly', business_material='canvas',
            **{k: 'qa_' + k for k in amo.UTM_FIELDS})
        self.job = dict(id=5, token='lease', lead=self.lead, create_started=False, amo_lead_id=None)
        self.client = MagicMock(config=self.config)
        self.client.list.return_value = []
        self.client.request.return_value = [{'id': 123, 'request_id': [self.lead['id']]}]
        self.save = MagicMock(return_value=True)

    def test_optional_configuration_strict_host_and_token(self):
        self.assertIsNone(amo.configuration({}))
        for host in ('http://example.amocrm.ru', 'https://example.amocrm.ru/evil',
                     'https://example.amocrm.ru@evil.example', 'https://example.amocrm.ru.evil.example',
                     'https://example.amocrm.ru?secret=value', 'https://example.amocrm.ru\n'):
            with self.subTest(host=host), self.assertRaises(amo.DeliveryError):
                amo.configuration(dict(ENV, AMO_BASE_URL=host))
        for change in ({'AMO_ACCESS_TOKEN': 'secret\nheader'}, {'AMO_PIPELINE_ID': '-1'},
                       {'AMO_RESPONSIBLE_ID': 'x'}, {'AMO_DETAILS_FIELD_ID': ''}):
            with self.assertRaises(amo.DeliveryError):
                amo.configuration(dict(ENV, **change))

    def test_payload_complete_fields_and_no_attachment_data(self):
        result = amo.payload(dict(self.lead, attachment={'name': 'private.pdf', 'content': b'secret'}), self.config)
        fields = result['custom_fields_values']
        details = next(f['values'][0]['value'] for f in fields if f.get('field_id') == 22)
        for text in (self.lead['question'], self.lead['phone'], self.lead['email'],
                     self.lead['source_path'], 'ТЕСТ компания', 'Брезент', 'Чехлы на технику'):
            self.assertIn(text, details)
        self.assertEqual({f['field_code'] for f in fields if 'field_code' in f}, {k.upper() for k in amo.UTM_FIELDS})
        self.assertEqual(len(result['_embedded']['contacts'][0]['custom_fields_values']), 2)
        self.assertNotIn('private.pdf', json.dumps(result))
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(amo.payload(self.lead, self.config, 456)['_embedded']['contacts'], [{'id': 456}])
        self.assertEqual(result['request_id'], self.lead['id'])

    def test_exact_contact_match_and_conflict(self):
        def row(cid, email):
            return {'id': cid, 'custom_fields_values': [{'field_code': 'EMAIL', 'values': [{'value': email}]}]}
        self.client.list.return_value = [row(1, 'another@example.invalid'), row(2, 'TEST@example.invalid')]
        self.assertEqual(amo.existing_contact(self.client, self.lead), 2)
        self.client.list.return_value = [row(2, self.lead['email']), row(3, self.lead['email'])]
        with self.assertRaisesRegex(amo.DeliveryError, 'amo_contact_conflict'):
            amo.existing_contact(self.client, self.lead)
        self.assertEqual(amo.contacts(dict(id='x', contact='+7 999 123-45-67')), {'PHONE': '+7 999 123-45-67'})

    def test_create_is_fenced_and_remote_id_persisted(self):
        self.assertEqual(amo.send(self.job, self.config, self.save, self.client), 123)
        self.assertEqual(self.save.call_args_list[0].kwargs, {'create_started': True})
        self.assertEqual(self.save.call_args_list[1].kwargs, {'amo_lead_id': 123})
        self.assertEqual(self.client.request.call_count, 1)

    def test_lost_response_never_blindly_recreates(self):
        self.client.request.side_effect = amo.DeliveryError('amo_network_error')
        with self.assertRaises(amo.DeliveryError):
            amo.send(self.job, self.config, self.save, self.client)
        self.assertEqual(self.save.call_count, 1)
        self.client.request.reset_mock()
        with self.assertRaisesRegex(amo.DeliveryError, 'amo_create_unconfirmed'):
            amo.send(dict(self.job, create_started=True), self.config, self.save, self.client)
        self.client.request.assert_not_called()
        self.client.list.return_value = [{'id': 123, 'custom_fields_values': [amo.field(21, self.lead['id'])]}]
        self.assertEqual(amo.send(dict(self.job, create_started=True), self.config, self.save, self.client), 123)
        self.client.request.assert_not_called()
        self.client.list.assert_called_with('leads', {'query': self.lead['id']})

    def test_submission_search_ignores_fuzzy_matches(self):
        self.client.list.return_value = [{'id': 99, 'custom_fields_values': [amo.field(21, 'other-uuid')]}]
        self.assertIsNone(amo.find_submission(self.client, self.lead['id']))
        self.client.list.assert_called_once_with('leads', {'query': self.lead['id']})

    def test_saved_result_finishes_without_any_remote_write(self):
        self.assertEqual(amo.send(dict(self.job, amo_lead_id=123), self.config, self.save, self.client), 123)
        self.client.list.assert_not_called()
        self.client.request.assert_not_called()

    def test_explicit_rejection_releases_create_fence_but_500_does_not(self):
        for code in (400, 401, 403, 422, 429, 500):
            self.save.reset_mock()
            self.client.request.side_effect = amo.DeliveryError('amo_http_' + str(code))
            with self.assertRaises(amo.DeliveryError):
                amo.send(self.job, self.config, self.save, self.client)
            self.assertEqual(self.save.call_count, 1 if code == 500 else 2)
            if code != 500:
                self.assertEqual(self.save.call_args.kwargs, {'create_started': False})

    def test_invalid_create_response_keeps_fence(self):
        for result in ({'ok': True}, [], [None], [{'id': 123, 'request_id': ['different']}], [{'id': 0}]):
            self.save.reset_mock()
            self.client.request.return_value = result
            with self.assertRaises(amo.DeliveryError):
                amo.send(self.job, self.config, self.save, self.client)
            self.assertEqual(self.save.call_count, 1)

    def test_expired_worker_cannot_create(self):
        self.save.return_value = False
        with self.assertRaisesRegex(amo.DeliveryError, 'amo_lease_lost'):
            amo.send(self.job, self.config, self.save, self.client)
        self.client.request.assert_not_called()

    def test_tls_no_proxy_no_redirect_redacted_errors_and_response_bound(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status, response.read.return_value = 200, b'{"id":1}'
        with patch.object(amo.urllib.request, 'build_opener', return_value=opener) as build:
            client = amo.Client(self.config)
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsNone(handlers[1].redirect_request(None, None, 302, '', {}, 'https://evil.example'))
        self.assertEqual(handlers[2]._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(handlers[2]._context.check_hostname)
        with patch.object(amo.time, 'sleep'):
            self.assertEqual(client.request('GET', '/api/v4/account'), {'id': 1})
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer ' + self.config['token'])
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 20)
            opener.open.side_effect = urllib.error.HTTPError('private-url', 401, 'private-text', {}, None)
            with self.assertRaisesRegex(amo.DeliveryError, '^amo_http_401$'):
                client.request('GET', '/api/v4/account')
        self.assertEqual(amo.error_code(RuntimeError('private-text')), 'amo_delivery_error')

    def test_worker_preserves_pending_on_error_and_independent_mail(self):
        with patch.object(amo, 'configuration', return_value=self.config), \
             patch.object(leads.delivery_store, 'claim', side_effect=[self.job, None]) as claim, \
             patch.object(amo, 'send', side_effect=amo.DeliveryError('amo_http_429')), \
             patch.object(leads.delivery_store, 'finish') as finish:
            leads.deliver_amo_once()
            finish.assert_called_once_with(self.job, 'amo_http_429')
            claim.assert_called_with('amo')
        with patch.object(amo, 'configuration', return_value=None), patch.object(leads.delivery_store, 'claim') as claim:
            leads.deliver_amo_once()
            claim.assert_not_called()

    def test_preflight_rejects_wrong_account_stage_and_fields_without_writes(self):
        fields = [{'id': 21, 'type': 'text'}, {'id': 22, 'type': 'textarea'}, {'id': 23, 'type': 'text'}]
        fields += [{'id': 100 + i, 'type': 'tracking_data', 'code': k.upper()} for i, k in enumerate(amo.UTM_FIELDS)]
        for account, stage, rows, expected in [
                ('example', 12, fields, None),
                ('wrong', 12, fields, 'amo_account_mismatch'),
                ('example', 13, fields, 'amo_status_missing'),
                ('example', 12, fields[1:], 'amo_field_mismatch'),
                ('example', 12, fields[:-1], 'amo_utm_fields_missing')]:
            client = MagicMock()
            client.request.side_effect = [{'subdomain': account}, {'_embedded': {'statuses': [{'id': stage}]}}]
            client.list.return_value = rows
            with patch.object(amo, 'Client', return_value=client):
                if expected:
                    with self.assertRaisesRegex(amo.DeliveryError, expected):
                        amo.preflight(self.config)
                else:
                    amo.preflight(self.config)
            self.assertTrue(all(call.args[0] == 'GET' for call in client.request.call_args_list))


if __name__ == '__main__':
    unittest.main()
