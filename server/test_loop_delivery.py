import json
import ssl
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).parent))
import leads
import loop_delivery as loop

TEST_WEBHOOK = 'https://neesha.loop.ru/hooks/' + 'a' * 26


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.lead = dict(id='12345678-1234-4234-8234-123456789abc', name='ТЕСТ',
            contact='test@example.invalid', question='ТЕСТ текст\n@channel <!here> ``` ![image](https://example.invalid)',
            created_at='2026-09-21T22:00:00Z', source_path='/catalog/chehol-na-kvadrocikl/',
            product_name='Чехол на квадроцикл', product_slug='chehol-na-kvadrocikl',
            product_size='220 × 98 × 106', inquiry_type='sizing', quantity=2,
            business_company='ТЕСТ компания', business_intent='custom',
            attachment={'name': 'private.pdf', 'type': 'application/pdf', 'content': b'private file bytes'})

    def test_complete_literal_message_moscow_time_and_no_file(self):
        payload = loop.message(self.lead)
        text = payload['text']
        for expected in ('22.09.2026 01:00:00 МСК', self.lead['contact'], 'Компания / сфера: ТЕСТ компания',
                         'Количество, шт.: 2', 'Подбор размера', 'Изделие на заказ',
                         'Размер, см: 220 × 98 × 106', 'Карточка товара — форма обращения',
                         'https://needle-shark.ru/catalog/chehol-na-kvadrocikl/'):
            self.assertIn(expected, text)
        self.assertIn('\n~~~\n', text)
        self.assertTrue(text.endswith('\n~~~'))
        self.assertIn(self.lead['question'], text)
        self.assertTrue(payload['skip_slack_parsing'])
        self.assertEqual(set(payload), {'text', 'skip_slack_parsing'})
        self.assertNotIn('private.pdf', json.dumps(payload))
        self.assertNotIn('private file bytes', json.dumps(payload))
        self.assertNotIn(TEST_WEBHOOK, json.dumps(payload))

    def test_long_message_is_complete_and_absent_source_is_not_invented(self):
        lead = dict(self.lead, question='Ю' * 5000)
        lead.pop('source_path')
        text = loop.message(lead)['text']
        self.assertIn('Ю' * 5000, text)
        self.assertLess(len(text), 16000)
        self.assertIn('Страница: Не передана', text)
        self.assertNotIn('https://needle-shark.ru', text)
        for path, expected in [('/', 'Главная'), ('/catalog/', 'Каталог'), ('/business/', 'Для бизнеса')]:
            self.assertIn(expected, loop.message(dict(lead, source_path=path))['text'])
        for question in ('\n' * 4999 + 'Я', '`' * 2500 + '~' * 2500):
            text = loop.message(dict(lead, question=question))['text']
            self.assertIn(question, text)
            self.assertLess(len(text), 16000)

    def test_url_configuration_is_restricted_and_optional(self):
        self.assertEqual(loop.webhook_url(TEST_WEBHOOK), TEST_WEBHOOK)
        with patch.dict('os.environ', {}, clear=True):
            self.assertIsNone(loop.webhook_url())
        for value in (TEST_WEBHOOK.replace('https:', 'http:'), TEST_WEBHOOK + '?x=1',
                      TEST_WEBHOOK + '#x', TEST_WEBHOOK.replace('neesha.loop.ru', 'other.loop.ru'),
                      TEST_WEBHOOK.replace('neesha.loop.ru', 'neesha.loop.ru@evil.example'),
                      'https://neesha.loop.ru/login', TEST_WEBHOOK + '\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loop.webhook_url(value)

    def test_sender_requires_explicit_ack_uses_tls_and_rejects_redirects(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status, response.read.return_value = 200, b'ok\n'
        with patch.object(loop.urllib.request, 'build_opener', return_value=opener) as build:
            loop.send(self.lead, TEST_WEBHOOK)
        request = opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data), loop.message(self.lead))
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 15)
        handlers = build.call_args.args
        context = handlers[-1]._context
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsNone(handlers[1].redirect_request(request, None, 302, '', {}, 'https://evil.example/'))
        for status, body in [(200, b'<html>login</html>'), (201, b'ok'), (200, b'{"ok":true}')]:
            response.status, response.read.return_value = status, body
            with patch.object(loop.urllib.request, 'build_opener', return_value=opener), self.assertRaises(RuntimeError):
                loop.send(self.lead, TEST_WEBHOOK)

    def test_loop_worker_independent_from_smtp_and_failure_retried(self):
        jobs = [dict(id=i, channel='loop', lead=self.lead) for i in (1, 2)]
        failure = urllib.error.HTTPError(TEST_WEBHOOK, 429, 'private', {}, None)
        with patch.object(loop, 'webhook_url', return_value=TEST_WEBHOOK), \
             patch.object(leads.mail_delivery, 'smtp_config', return_value=None), \
             patch.object(leads.delivery_store, 'claim', side_effect=[*jobs, None]) as claim, \
             patch.object(loop, 'send', side_effect=[failure, None]), \
             patch.object(leads.delivery_store, 'finish') as finish:
            leads.deliver_once()  # Disabled mail does not block the other worker.
            claim.assert_not_called()
            leads.deliver_loop_once()
        failure.close()
        self.assertEqual(finish.call_args_list[0].args, (jobs[0], 'loop_http_429'))
        self.assertEqual(finish.call_args_list[1].args, (jobs[1],))
        self.assertTrue(all(call.args == ('loop',) for call in claim.call_args_list))
        self.assertEqual(loop.error_code(ValueError('secret')), 'loop_delivery_error')
        with patch.object(loop, 'webhook_url', return_value=None), patch.object(leads.delivery_store, 'claim') as claim:
            leads.deliver_loop_once()
            claim.assert_not_called()
