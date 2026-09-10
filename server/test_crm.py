import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import crm


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.lead = dict(id='12345678-1234-4234-8234-123456789abc', name='ТЕСТ',
                         contact='test@example.invalid', question='Тестовая заявка', consent=True,
                         created_at='2026-09-10T00:00:00Z', product_slug='chehol-na-kvadrocikl',
                         product_name='Чехол на квадроцикл', product_size='220 × 98 × 106',
                         inquiry_type='wholesale', quantity=12, source_path='/catalog/chehol-na-kvadrocikl/')
        self.conn = MagicMock()
        self.cur = self.conn.cursor.return_value.__enter__.return_value
        self.driver = SimpleNamespace(connect=MagicMock(return_value=self.conn))

    def archive(self, lead):
        with patch.dict('os.environ', {'CRM_DSN': 'test-only'}), patch.dict(sys.modules, {'psycopg2': self.driver}):
            crm.archive(lead)

    def test_product_metadata_is_bound_to_order_insert(self):
        self.cur.fetchone.side_effect = [None, (7,)]
        self.archive(self.lead)
        sql, args = self.cur.execute.call_args.args
        self.assertIn('product_size', sql)
        self.assertIn('quantity', sql)
        self.assertEqual(args[-6:], tuple(self.lead[key] for key in crm.CONTEXT_FIELDS))
        self.conn.close.assert_called_once()

    def test_expired_queue_retry_compares_product_context(self):
        self.cur.fetchone.return_value = (self.lead['name'], self.lead['contact'], self.lead['question'],
                                         *(self.lead[key] for key in crm.CONTEXT_FIELDS))
        self.archive(self.lead)
        self.assertEqual(self.cur.execute.call_count, 1)
        with self.assertRaises(ValueError):
            self.archive(dict(self.lead, quantity=13))

    def test_legacy_order_uses_null_context(self):
        legacy = {k: v for k, v in self.lead.items() if k not in crm.CONTEXT_FIELDS}
        self.cur.fetchone.return_value = (legacy['name'], legacy['contact'], legacy['question'], *(None for _ in crm.CONTEXT_FIELDS))
        self.archive(legacy)
        self.assertEqual(self.cur.execute.call_count, 1)


if __name__ == '__main__':
    unittest.main()
