import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))

spec = importlib.util.spec_from_file_location('mail_config', Path(__file__).with_name('configure-server-mail.py'))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class MailConfigTests(unittest.TestCase):
    def test_systemd_roundtrip_keeps_literal_password_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.env'
            for value in ['words with spaces', 'a$`b#c', 'a"b\\c', "a'b"]:
                path.write_text('VALUE=' + config.quoted(value) + '\n')
                self.assertEqual(config.read_env(path)['VALUE'], value)
            path.write_text("VALUE=a'b$`#literal\n")
            self.assertEqual(config.read_env(path)['VALUE'], "a'b$`#literal")

    def test_multiline_values_are_rejected(self):
        with self.assertRaises(ValueError):
            config.quoted('value\nOTHER=bad')

    def test_loop_update_preserves_mail_and_rejects_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            target, incoming = (Path(directory) / name for name in ('existing.env', 'incoming.env'))
            old = {'CRM_DSN': 'dbname=test', 'MAIL_RECIPIENTS': 'test@example.invalid',
                   'SMTP_PASSWORD': 'private$`#value', 'IP_HASH_SECRET': 'unchanged'}
            config.write_env(str(target), old)
            webhook = 'https://neesha.loop.ru/hooks/' + 'a' * 26
            config.write_env(str(incoming), {'LOOP_LEADS_WEBHOOK_URL': webhook})
            config.configure_loop(str(target), str(incoming))
            self.assertEqual(config.read_env(target), dict(old, LOOP_LEADS_WEBHOOK_URL=webhook))
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            for update in ({'MAIL_RECIPIENTS': 'other@example.invalid', 'LOOP_LEADS_WEBHOOK_URL': webhook},
                           {'LOOP_LEADS_WEBHOOK_URL': 'https://other.example/hooks/private'}):
                config.write_env(str(incoming), update)
                with self.assertRaises(ValueError):
                    config.configure_loop(str(target), str(incoming))
                self.assertEqual(config.read_env(target), dict(old, LOOP_LEADS_WEBHOOK_URL=webhook))
