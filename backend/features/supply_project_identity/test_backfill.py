import unittest
from unittest.mock import Mock

from .backfill import build_report, run_backfill


def rows(requests):
    return {
        "projects": [
            {"id": 11, "company_id": 3, "name": "Лицей"},
            {"id": 12, "company_id": 4, "name": "Лицей"},
        ],
        "supply_requests": requests,
    }


class SupplyProjectBackfillTests(unittest.TestCase):
    def test_exact_company_and_name_is_ready_without_exposing_name(self):
        report = build_report(rows([
            {"id": 21, "company_id": 3, "project": "Лицей", "project_id": None},
        ]))
        self.assertEqual(report["readyCount"], 1)
        self.assertEqual(report["backfillPreview"][0]["projectId"], 11)
        self.assertNotIn("Лицей", str(report))

    def test_duplicate_inside_same_company_is_review_not_guess(self):
        source = rows([{"id": 21, "company_id": 3, "project": "Лицей", "project_id": None}])
        source["projects"].append({"id": 13, "company_id": 3, "name": "Лицей"})
        report = build_report(source)
        self.assertEqual(report["readyCount"], 0)
        self.assertEqual(report["needsReview"][0]["reason"], "project_name_ambiguous")

    def test_stored_project_must_match_company_and_name(self):
        report = build_report(rows([
            {"id": 21, "company_id": 3, "project": "Лицей", "project_id": 12},
        ]))
        self.assertEqual(report["needsReview"][0]["reason"], "stored_project_company_mismatch")

    def test_main_warehouse_remains_verified_company_scope(self):
        report = build_report(rows([
            {"id": 21, "company_id": 3, "project": "Основной склад", "project_id": None},
        ]))
        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedCount"], 1)

    def test_dry_run_uses_readonly_transaction_and_rolls_back(self):
        conn = Mock()
        cur = conn.cursor.return_value
        cur.fetchall.side_effect = [
            [{"id": 11, "company_id": 3, "name": "Лицей"}],
            [{"id": 21, "company_id": 3, "project": "Лицей", "project_id": None}],
        ]
        result = run_backfill(conn)
        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)

    def test_apply_is_not_limited_to_preview_size(self):
        source = rows([
            {"id": request_id, "company_id": 3, "project": "Лицей", "project_id": None}
            for request_id in range(1, 102)
        ])
        report = build_report(source)
        self.assertEqual(report["readyCount"], 101)
        self.assertEqual(len(report["backfillPreview"]), 100)
        self.assertTrue(report["previewTruncated"])


if __name__ == "__main__":
    unittest.main()
