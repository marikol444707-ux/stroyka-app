import unittest

from .routes import _event_sort_key, _json_list


class ProjectEventRouteHelpersTest(unittest.TestCase):
    def test_invoice_photos_and_items_accept_json_arrays(self):
        self.assertEqual(
            _json_list('[{"name":"Кабель", "quantity":25}]'),
            [{"name": "Кабель", "quantity": 25}],
        )

    def test_invalid_legacy_json_does_not_break_event_feed(self):
        self.assertEqual(_json_list('not-json'), [])
        self.assertEqual(_json_list({"photo": "url"}), [])

    def test_events_sort_by_full_timestamp_before_document_day(self):
        created = _event_sort_key({"eventAt": "2026-07-27T15:30:00"})
        document_day = _event_sort_key({"eventAt": "2026-07-27"})
        self.assertGreater(created, document_day)

    def test_timezone_timestamp_can_be_sorted_with_legacy_date(self):
        self.assertGreater(
            _event_sort_key({"eventAt": "2026-07-27T15:30:00Z"}),
            _event_sort_key({"eventAt": "2026-07-27"}),
        )


if __name__ == "__main__":
    unittest.main()
