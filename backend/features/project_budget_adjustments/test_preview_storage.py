import unittest

from backend.features.project_budget_adjustments.preview_storage import (
    load_budget_adjustment_source,
)


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row


class BudgetAdjustmentPreviewStorageTests(unittest.TestCase):
    def test_loads_one_company_bound_source_without_names_or_notes(self):
        row = {"reconciliation_id": 7, "company_id": 10}
        cursor = FakeCursor(row)

        result = load_budget_adjustment_source(cursor, 7, 10)

        self.assertEqual(result, row)
        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        self.assertTrue(sql.startswith("SELECT "))
        self.assertIn("FROM public.estimate_reconciliations r", sql)
        self.assertIn("JOIN public.estimates base_estimate", sql)
        self.assertIn("JOIN public.estimates next_estimate", sql)
        self.assertIn("JOIN public.projects project", sql)
        self.assertIn("LEFT JOIN public.project_budget_adjustments receipt", sql)
        self.assertIn("project.company_id=%s", sql)
        self.assertIn("r.id=%s", sql)
        self.assertIn("active_scope_count", sql)
        self.assertNotIn("base_estimate.total", sql)
        self.assertNotIn("next_estimate.total", sql)
        self.assertIn("base_estimate.sections_json", sql)
        self.assertIn("next_estimate.sections_json", sql)
        self.assertIn("LIMIT 1", sql)
        self.assertEqual(params, (7, 10))
        for forbidden in (
            "project_name", "base_estimate_name", "next_estimate_name",
            "notes", "approved_by", "estimate_reconciliation_items",
        ):
            self.assertNotIn(forbidden, sql.lower())

    def test_missing_or_foreign_source_returns_none(self):
        cursor = FakeCursor(None)

        result = load_budget_adjustment_source(cursor, 99, 10)

        self.assertIsNone(result)
        self.assertEqual(cursor.calls[0][1], (99, 10))


if __name__ == "__main__":
    unittest.main()
