from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import metrika_reports as reports


def fixture():
    current = dict(zip(reports.KEYS, [40, 50, 80, 20, 1.6, 35, 3, 2, 5, 3, 4, 2]))
    previous = dict(zip(reports.KEYS, [30, 40, 60, 25, 1.5, 30, 1, 1, 4, 2, 2, 1]))
    return dict(current=current, previous=previous, sources=[], pages=[], lag=60)


class ReportTests(unittest.TestCase):
    def test_month_year_boundary_and_leap_year(self):
        p = reports.period_for('monthly', date(2025, 1, 1))
        self.assertEqual((p.start, p.end, p.previous_start, p.previous_end),
                         (date(2024, 12, 1), date(2024, 12, 31), date(2024, 11, 1), date(2024, 11, 30)))
        p = reports.period_for('monthly', date(2024, 3, 1))
        self.assertEqual(p.end, date(2024, 2, 29))

    def test_week_is_complete_monday_sunday_daily_same_weekday(self):
        p = reports.period_for('weekly', date(2026, 9, 28))
        self.assertEqual((p.start, p.end), (date(2026, 9, 21), date(2026, 9, 27)))
        p = reports.period_for('daily', date(2026, 9, 24))
        self.assertEqual(p.previous_start, date(2026, 9, 16))

    def test_schedule_moscow_and_no_historical_backfill(self):
        enabled = datetime(2026, 9, 24, 12, tzinfo=reports.MSK)
        self.assertEqual(reports.due_periods(enabled, enabled), [])
        before = datetime.fromisoformat('2026-09-25T06:59:00+00:00')
        self.assertEqual(reports.due_periods(before, enabled), [])
        after = datetime.fromisoformat('2026-09-25T07:00:00+00:00')
        self.assertEqual([p.kind for p in reports.due_periods(after, enabled)], ['daily'])
        month = datetime(2026, 10, 1, 10, tzinfo=reports.MSK)
        self.assertEqual([p.kind for p in reports.due_periods(month, enabled)], ['daily', 'weekly', 'monthly'])

    def test_no_zero_division_and_percentage_points(self):
        self.assertEqual(reports.change(3, 0), 'было 0; +3')
        self.assertEqual(reports.change(0, 0), 'без изменений')
        p = reports.period_for('monthly', date(2026, 12, 1))
        text = reports.render(p, fixture(), set())
        self.assertIn('30 и 31 дн.', text)
        self.assertIn('4,00% (+1,50 п. п.)', text)

    def test_incomplete_baseline_does_not_claim_growth(self):
        p = reports.period_for('monthly', date(2026, 10, 1))
        text = reports.render(p, fixture(), set())
        self.assertIn('Процент роста не оцениваем', text)
        self.assertNotIn('+25,0%', text)

    def test_visitor_controlled_urls_names_and_mentions_are_not_sent(self):
        data = fixture()
        data['pages'] = [dict(dimensions=[{'name': '/private/alice@example.com/'}], metrics=[10]),
                         dict(dimensions=[{'name': '/business/'}], metrics=[9])]
        data['sources'] = [dict(dimensions=[{'id': 'unknown', 'name': '@channel'}], metrics=[50])]
        text = reports.render(reports.period_for('daily', date(2026, 9, 24)), data, {'/business/'})
        self.assertNotIn('alice', text)
        self.assertNotIn('@channel', text)
        self.assertIn('https://needle-shark.ru/business/', text)
        self.assertIn('Прочие / не определено', text)

    def test_empty_traffic_is_not_zero_percent_conversion(self):
        data = fixture()
        data['current'] = {key: 0 for key in reports.KEYS}
        text = reports.render(reports.period_for('daily', date(2026, 9, 24)), data, set())
        self.assertIn('конверсия: — (нет визитов)', text)
        self.assertIn('нет визитов', text)

    def test_api_error_missing_null_or_sampled_data_are_not_zero(self):
        base = dict(sampled=False, totals=[2], data=[], data_lag=20, total_rows=0)
        reports.validate_result(base, ['ym:s:visits'])
        for patch in ({'totals': [None]}, {'totals': []}, {'sampled': True}, {'data_lag': None},
                      {'totals': [float('nan')]}, {'totals': [-1]}):
            with self.subTest(patch=patch), self.assertRaises(reports.ReportError):
                reports.validate_result(dict(base, **patch), ['ym:s:visits'])
        with self.assertRaises(reports.ReportError):
            reports.validate_result(dict(base, total_rows=2), ['ym:s:visits'], 'source')

    def test_filters_and_request_avoid_mutations_and_direct(self):
        client = reports.Metrika('test-token')
        response = Mock()
        response.read.return_value = json.dumps(dict(sampled=False, totals=[1], data=[], data_lag=0)).encode()
        client.opener = Mock()
        client.opener.open.return_value.__enter__ = Mock(return_value=response)
        client.opener.open.return_value.__exit__ = Mock(return_value=False)
        client.query(date(2026, 9, 1), date(2026, 9, 2), ['ym:s:visits'])
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'GET')
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(params['ids'], ['112428810'])
        self.assertEqual(params['timezone'], ['+03:00'])
        self.assertIn('release_check', params['filters'][0])
        self.assertIn('lastUTMMedium', params['filters'][0])
        self.assertNotIn('test-token', request.full_url)

    def test_durable_success_retry_failure_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            state = {'enabled_at': '2026-09-24T12:00:00+03:00', 'sent': {}}
            now = datetime(2026, 9, 25, 10, tzinfo=reports.MSK)
            send = Mock(side_effect=OSError('private URL'))
            with self.assertRaisesRegex(reports.ReportError, '^loop_unconfirmed$'):
                reports.dispatch(state, path, now, lambda _: 'text', send)
            self.assertEqual(state['sent'], {})
            send = Mock()
            reports.dispatch(state, path, now, lambda _: 'text', send)
            restored = json.loads(path.read_text())
            reports.dispatch(restored, path, now, lambda _: 'text', send)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(send.call_args.args[0]['skip_slack_parsing'])


if __name__ == '__main__':
    unittest.main()
