import unittest
from datetime import datetime, timezone
from backend.features.supplier_access.response_deadlines import response_deadline

class ResponseDeadlineTests(unittest.TestCase):
    def test_next_weekday_preserves_moscow_time_including_weekend(self):
        for source,expected in [('2026-09-18T11:00:00+00:00','2026-09-21T11:00:00+00:00'),('2026-09-19T11:00:00+00:00','2026-09-21T11:00:00+00:00'),('2026-09-21T21:30:00+00:00','2026-09-22T21:30:00+00:00')]:
            self.assertEqual(response_deadline(None,datetime.fromisoformat(source)).isoformat(),expected)
    def test_override_requires_timezone_and_future_instant(self):
        now=datetime(2026,9,19,tzinfo=timezone.utc)
        self.assertEqual(response_deadline('2026-09-20T14:00:00+03:00',now).hour,11)
        for value in ['no','2026-09-20T14:00','2026-09-18T14:00:00Z',42,True]:
            with self.assertRaises(ValueError):response_deadline(value,now)
