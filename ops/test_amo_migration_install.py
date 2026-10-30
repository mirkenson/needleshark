from pathlib import Path
import unittest

class MigrationInstallTests(unittest.TestCase):
    def test_every_uploaded_sql_runs_before_application_validation(self):
        import re
        script=Path(__file__).with_name('install-server-mail.sh').read_text()
        uploaded=set(re.findall(r'project_dir/server/migrations/([0-9_a-z]+\.sql)',script))
        applied=set(re.findall(r'psql[^\n]+-f "\$release_dir/([0-9_a-z]+\.sql)"',script))
        self.assertTrue(uploaded)
        self.assertEqual(uploaded,applied)
        for name in uploaded:
            self.assertLess(script.index('-f "$release_dir/'+name+'"'),script.index('systemd-run --quiet'))
        self.assertIn('GRANT SELECT,INSERT,UPDATE ON amo_loop_cursor,amo_loop_notifications TO needle_app',script)
