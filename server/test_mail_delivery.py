import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import smtplib
import ssl
import unittest
from unittest.mock import patch, MagicMock
import mail_delivery as mail


class MailTests(unittest.TestCase):
    def setUp(self):
        self.lead = dict(id='12345678-1234-4234-8234-123456789abc', name='ТЕСТ',
                         contact='test@example.invalid', question='ТЕСТ письмо',
                         created_at='2026-09-18T00:00:00Z', business_company='Компания',
                         business_intent='custom', attachment={'name': 'Тест.pdf',
                         'type': 'application/pdf', 'content': b'%PDF-test'})
        self.cfg = dict(host='smtp.example.invalid', port=465, mode='ssl', user='site@example.invalid',
                        password='test-only', sender='site@example.invalid')

    def test_private_file_attached_and_no_google_link(self):
        msg = mail.message(self.lead, 'test@example.invalid', self.cfg['sender'])
        attachment = list(msg.iter_attachments())[0]
        self.assertEqual(attachment.get_payload(decode=True), b'%PDF-test')
        self.assertEqual(attachment.get_filename(), 'Тест.pdf')
        self.assertEqual(msg['Reply-To'], 'test@example.invalid')
        self.assertIn('Компания / сфера: Компания', msg.get_body().get_content())
        self.assertNotIn('google.com', msg.as_string())
        self.assertEqual(msg['Message-ID'], mail.message(self.lead, 'test@example.invalid', self.cfg['sender'])['Message-ID'])

    def test_recipient_and_header_injection_rejected(self):
        for address in ['x@example.invalid\nBcc:other@example.invalid', 'Name <x@example.invalid>', 'a@example.invalid,b@example.invalid', 'missing-domain', '']:
            with self.subTest(address=address), self.assertRaises(ValueError):
                mail.mailbox(address)
        msg = mail.message(dict(self.lead, contact='tel\nBcc:other@example.invalid'), 'test@example.invalid', self.cfg['sender'])
        self.assertIsNone(msg['Reply-To'])
        self.assertIsNone(msg['Bcc'])

    def test_only_explicit_recipients_no_defaults(self):
        with patch.dict('os.environ', {'MAIL_RECIPIENTS': 'test@example.invalid,test@example.invalid'}, clear=True):
            self.assertEqual(mail.recipients(), ('test@example.invalid',))
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(ValueError):
            mail.recipients()

    def test_missing_credentials_pause_and_plaintext_rejected(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertIsNone(mail.smtp_config())
        with patch.dict('os.environ', {'SMTP_HOST': 'test', 'SMTP_USER': 'test', 'SMTP_PASSWORD': 'test',
                                     'MAIL_FROM': 'test@example.invalid', 'SMTP_SECURITY': 'none'}, clear=True):
            with self.assertRaises(ValueError):
                mail.smtp_config()

    def test_tls_verified_and_single_envelope_recipient(self):
        client = MagicMock()
        client.send_message.return_value = {}
        with patch.object(mail.smtplib, 'SMTP_SSL', return_value=client) as smtp:
            mail.send(self.lead, 'test@example.invalid', self.cfg)
        context = smtp.call_args.kwargs['context']
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(client.send_message.call_args.kwargs['to_addrs'], ['test@example.invalid'])
        client.close.assert_called_once()

    def test_starttls_failure_never_authenticates(self):
        client = MagicMock()
        client.starttls.side_effect = ssl.SSLError('test-only')
        with patch.object(mail.smtplib, 'SMTP', return_value=client), self.assertRaises(ssl.SSLError):
            mail.send(self.lead, 'test@example.invalid', dict(self.cfg, mode='starttls', port=587))
        client.login.assert_not_called()
        client.send_message.assert_not_called()

    def test_refused_recipient_is_failure_and_errors_are_redacted(self):
        client = MagicMock()
        client.send_message.return_value = {'test@example.invalid': (550, b'private response')}
        with patch.object(mail.smtplib, 'SMTP_SSL', return_value=client), self.assertRaises(smtplib.SMTPRecipientsRefused):
            mail.send(self.lead, 'test@example.invalid', self.cfg)
        self.assertEqual(mail.error_code(smtplib.SMTPAuthenticationError(535, b'private response')), 'smtp_535')
        self.assertEqual(mail.error_code(ValueError('private response')), 'delivery_error')
