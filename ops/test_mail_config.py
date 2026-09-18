import importlib.util
from pathlib import Path
import tempfile
import unittest

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
