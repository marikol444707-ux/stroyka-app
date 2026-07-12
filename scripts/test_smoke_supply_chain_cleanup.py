import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("smoke-supply-chain.py")
SPEC = importlib.util.spec_from_file_location("smoke_supply_chain", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SupplyChainCleanupTests(unittest.TestCase):
    def test_cleanup_request_ids_include_every_created_request_once(self):
        created = {
            "requestId": 10,
            "withdrawRequestId": 11,
            "diagnosticRequestId": 12,
            "notificationRequestId": 13,
        }

        self.assertEqual(MODULE.cleanup_request_ids(created), [10, 11, 12, 13])

    def test_cleanup_request_ids_ignore_missing_invalid_and_duplicate_values(self):
        created = {
            "requestId": "10",
            "withdrawRequestId": 10,
            "diagnosticRequestId": None,
            "notificationRequestId": "bad",
        }

        self.assertEqual(MODULE.cleanup_request_ids(created), [10])

    def test_cleanup_request_outbox_deletes_only_max_supply_rows_for_created_requests(self):
        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params):
                self.calls.append((" ".join(sql.split()), params))

        cursor = Cursor()
        MODULE.cleanup_request_outbox(cursor, {"requestId": 10, "withdrawRequestId": 11})

        self.assertEqual([params for _sql, params in cursor.calls], [(10,), (11,)])
        self.assertTrue(all("provider='max'" in sql for sql, _params in cursor.calls))
        self.assertTrue(all("entity_type='supply_request'" in sql for sql, _params in cursor.calls))


if __name__ == "__main__":
    unittest.main()
