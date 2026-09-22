"""Exercise the actual installer EXIT guard, including errors that skip ERR traps."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


class InstallRecoveryTests(unittest.TestCase):
    def test_failure_and_unbound_parameter_restore_but_success_does_not(self):
        source = Path(__file__).with_name('install-server-mail.sh').read_text()
        guard = re.search(r"^trap '.*' EXIT$", source, re.MULTILINE).group()
        self.assertLess(source.index(guard), source.index('systemctl stop needle-leads'))
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'restored'
            for statement, restores in [('false', True), (': "$NEEDLE_UNBOUND_QA"', True), ('true\ntrap - EXIT', False)]:
                marker.unlink(missing_ok=True)
                script = 'set -eu\nmarker="$1"\nrestore_backend() { printf restored > "$marker"; }\n'
                result = subprocess.run(['bash', '-c', script + guard + '\n' + statement, 'qa', str(marker)],
                                        capture_output=True)
                self.assertEqual(marker.exists(), restores)
                self.assertEqual(result.returncode != 0, restores)
