import unittest
from unittest.mock import Mock

from backend.features.legacy_fallback.audit import build_report, classify_record, run_report


class LegacyFallbackAuditTests(unittest.TestCase):
    def test_stored_company_is_verified(self):
        result = classify_record({"record_id": 5, "company_id": 2, "company_found": True})

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["reason"], "stored_company")
        self.assertEqual(result["companyId"], 2)

    def test_missing_owner_uses_verified_parent_as_explicit_fallback(self):
        result = classify_record({"record_id": 5, "company_id": None, "parent_company_id": 2})

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["reason"], "verified_parent")
        self.assertEqual(result["companyId"], 2)

    def test_missing_company_or_mismatched_parent_requires_review(self):
        missing_company = classify_record({"record_id": 5, "company_id": 99, "company_found": False})
        mismatch = classify_record({
            "record_id": 6,
            "company_id": 1,
            "company_found": True,
            "parent_company_id": 2,
        })

        self.assertEqual(missing_company["reason"], "company_not_found")
        self.assertEqual(mismatch["reason"], "parent_company_mismatch")
        self.assertEqual(missing_company["status"], "unresolved")
        self.assertEqual(mismatch["status"], "unresolved")

    def test_report_is_consistent_and_not_strict_ready_while_fallback_exists(self):
        report = build_report({
            "projects": [{"record_id": 1, "company_id": 1, "company_found": True}],
            "estimates": [{"record_id": 2, "parent_company_id": 1}],
            "staff": [{"record_id": 3, "company_id": None}],
        })

        self.assertTrue(report["reportConsistent"])
        self.assertFalse(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 3,
            "verified": 1,
            "fallback": 1,
            "unresolved": 1,
        })
        self.assertEqual(report["fallbackPreview"][0]["table"], "estimates")
        self.assertEqual(report["needsReview"][0]["table"], "staff")

    def test_database_run_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        cur.fetchall.return_value = []

        result = run_report(lambda: conn)

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        conn.close.assert_called_once_with()
        cur.close.assert_called_once_with()
        self.assertEqual(cur.execute.call_count, 6)
        self.assertTrue(result["rolledBack"])


if __name__ == "__main__":
    unittest.main()
