import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import antispam
import leads

ID = '12345678-1234-4234-8234-123456789abc'
OTHER = '12345678-1234-4234-8234-123456789abd'
IP = '192.0.2.1'
DATA = {'id': ID, 'name': 'ТЕСТ', 'contact': 'qa@example.invalid', 'question': 'ТЕСТ защиты', 'consent': True}


def solve(token):
    for nonce in range(2**24):
        digest = hashlib.sha256(f'{token}:{nonce}'.encode()).digest()
        if digest[0] == 0 and digest[1] < 4:
            return {'challenge': token, 'nonce': nonce}
    raise AssertionError('No solution')


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'IP_HASH_SECRET': 'test-only-key-' * 4, 'LEAD_PROTECTION_REQUIRED': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_bound_proof_validity_expiry_and_tampering(self):
        with patch.object(antispam.time, 'time', return_value=1800000000):
            issued = antispam.issue(ID, IP)
            proof = solve(issued['challenge'])
            antispam.verify(proof, ID, IP)
            for bad, bound_id, ip in [(None, ID, IP), ({}, ID, IP), (proof, OTHER, IP), (proof, ID, '192.0.2.2'),
                                      (dict(proof, nonce=True), ID, IP), (dict(proof, nonce=-1), ID, IP),
                                      (dict(proof, nonce=2**24), ID, IP), (dict(proof, challenge='x'*201), ID, IP),
                                      (dict(proof, challenge=proof['challenge'][:-1] + ('a' if proof['challenge'][-1] != 'a' else 'b')), ID, IP)]:
                with self.assertRaises(antispam.Rejected):
                    antispam.verify(bad, bound_id, ip)
        for timestamp in (1799999999, 1800000601):
            with patch.object(antispam.time, 'time', return_value=timestamp), self.assertRaises(antispam.Rejected):
                antispam.verify(proof, ID, IP)

    def test_incorrect_work_and_configuration_rejected(self):
        token = antispam.issue(ID, IP)['challenge']
        nonce = 0
        while hashlib.sha256(f'{token}:{nonce}'.encode()).digest()[:2] < b'\x00\x04':
            nonce += 1
        with self.assertRaises(antispam.Rejected):
            antispam.verify({'challenge': token, 'nonce': nonce}, ID, IP)
        with patch.dict(os.environ, {'IP_HASH_SECRET': ''}), self.assertRaises(RuntimeError):
            antispam.issue(ID, IP)
        with patch.dict(os.environ, {'LEAD_PROTECTION_REQUIRED': 'typo'}), self.assertRaises(RuntimeError):
            antispam.required()

    def test_http_guard_precedes_storage_and_preserves_retry_and_failure(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), leads.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(data, origin='https://needle-shark.ru'):
            conn = HTTPConnection(*server.server_address)
            conn.request('POST', '/api/leads', json.dumps(data),
                         {'Origin': origin, 'Content-Type': 'application/json', 'X-Real-IP': IP})
            response = conn.getresponse()
            result = response.status, json.loads(response.read())
            self.assertEqual(response.getheader('Cache-Control'), 'no-store')
            conn.close()
            return result
        try:
            with patch.object(leads, 'enqueue', return_value=(202, {'ok': True, 'id': ID})) as enqueue:
                self.assertEqual(request(DATA)[0], 403)
                self.assertEqual(request(dict(DATA, protection={}))[0], 403)
                self.assertEqual(request({'action': 'challenge', 'id': ID}, 'https://evil.example')[0], 403)
                self.assertEqual(request({'action': 'challenge', 'id': 'bad'})[0], 400)
                status, challenge = request({'action': 'challenge', 'id': ID})
                self.assertEqual(status, 200)
                enqueue.assert_not_called()
                proof = solve(challenge['challenge'])
                self.assertEqual(request(dict(DATA, protection=proof, website='spam'))[0], 400)
                self.assertEqual(request(dict(DATA, protection=proof))[0], 202)
                saved = enqueue.call_args.args[0]
                self.assertNotIn('protection', saved)
                self.assertNotIn('website', saved)
                enqueue.return_value = (200, {'ok': True, 'id': ID})
                self.assertEqual(request(dict(DATA, protection=proof))[0], 200)
                enqueue.side_effect = RuntimeError('database unavailable')
                status, result = request(dict(DATA, protection=proof))
                self.assertEqual(status, 503)
                self.assertFalse(result['ok'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
