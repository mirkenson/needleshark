import unittest
from unittest.mock import Mock
import maintenance


class Alerts(unittest.TestCase):
    def test_alert_suppression_repeat_and_recovery(self):
        send = Mock()
        state = maintenance.report({}, {}, 100, send)
        send.assert_not_called()
        state = maintenance.report({'disk': '80%'}, state, 200, send)
        self.assertEqual(send.call_count, 1)
        state = maintenance.report({'disk': '81%'}, state, 300, send)
        self.assertEqual(send.call_count, 1)
        state = maintenance.report({'disk': '82%'}, state, 22000, send)
        self.assertEqual(send.call_count, 2)
        state = maintenance.report({}, state, 22100, send)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(state['issues'], [])
        maintenance.report({}, state, 22200, send)
        self.assertEqual(send.call_count, 3)

    def test_failed_send_does_not_suppress_retry(self):
        state = {'issues': [], 'sent_at': 1}
        with self.assertRaises(OSError):
            maintenance.report({'database': 'failed'}, state, 100, Mock(side_effect=OSError))
        self.assertEqual(state, {'issues': [], 'sent_at': 1})

    def test_changed_problem_notifies_immediately(self):
        send = Mock()
        maintenance.report({'queue': 'delayed'}, {'issues': ['disk'], 'sent_at': 100}, 101, send)
        send.assert_called_once()
