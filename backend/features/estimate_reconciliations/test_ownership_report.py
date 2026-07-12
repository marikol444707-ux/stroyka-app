import unittest

from backend.features.estimate_reconciliations.ownership_report import (
    build_estimate_reconciliation_ownership_report,
    classify_reconciliation,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)


def owned_row(**overrides):
    row = {
        "reconciliation_id": 7,
        "base_estimate_id": 100,
        "next_estimate_id": 101,
        "reconciliation_work_package": "Основная",
        "reconciliation_smeta_type": "Заказчик",
        "base_exists": True,
        "base_company_id": 4,
        "base_project_id": 14,
        "base_work_package": "Основная",
        "base_smeta_type": "Заказчик",
        "next_exists": True,
        "next_company_id": 4,
        "next_project_id": 14,
        "next_work_package": "Основная",
        "next_smeta_type": "Заказчик",
        "project_id": 14,
        "project_company_id": 4,
    }
    row.update(overrides)
    return row


class EstimateReconciliationOwnershipReportTests(unittest.TestCase):
    def test_clean_pair_is_ready_without_business_payload(self):
        result = classify_reconciliation(owned_row())

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["companyId"], 4)
        self.assertEqual(result["projectId"], 14)
        self.assertNotIn("projectName", result)

    def test_cross_company_pair_requires_review(self):
        result = classify_reconciliation(owned_row(next_company_id=8, next_project_id=88))

        self.assertEqual(result["status"], "mismatched")
        self.assertEqual(result["reason"], "estimate_owner_mismatch")

    def test_reconciliation_package_mismatch_requires_review(self):
        result = classify_reconciliation(owned_row(reconciliation_work_package="Электрика"))

        self.assertEqual(result["status"], "mismatched")
        self.assertEqual(result["reason"], "reconciliation_work_package_mismatch")

    def test_report_is_read_only_and_lists_only_review_ids(self):
        cursor = FakeCursor([
            owned_row(),
            owned_row(reconciliation_id=8, next_exists=False),
        ])

        report = build_estimate_reconciliation_ownership_report(cursor)

        self.assertEqual(report["writesAttempted"], 0)
        self.assertFalse(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 2,
            "ready": 1,
            "unresolved": 1,
            "mismatched": 0,
        })
        self.assertEqual(report["needsReview"][0]["reconciliationId"], 8)
        self.assertEqual(len(cursor.calls), 1)
        self.assertTrue(cursor.calls[0][0].startswith("SELECT"))


if __name__ == "__main__":
    unittest.main()
