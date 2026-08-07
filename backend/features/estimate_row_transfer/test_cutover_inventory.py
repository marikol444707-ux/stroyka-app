import unittest
from pathlib import Path

from backend.features.estimate_row_transfer.cutover_inventory import (
    audit_cutover_inventory,
)


class EstimateRowTransferCutoverInventoryTests(unittest.TestCase):
    def test_repository_inventory_contains_only_reviewed_writers_and_required_tests(self):
        report = audit_cutover_inventory(Path(__file__).resolve().parents[3])

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["dmlStatements"], 8)
        self.assertEqual(report["requiredIntegrationChecks"], 6)
        self.assertEqual(report["missingIntegrationChecks"], [])
        self.assertEqual(report["violations"], [])

    def test_unreviewed_protected_history_writer_is_a_blocker(self):
        report = audit_cutover_inventory(source_files={
            "backend/features/estimate_row_transfer/assignment_apply.py": """
                def unsafe(cur):
                    statement = "UPDATE public.work_journal SET quantity=0 WHERE id=1"
                    cur.execute(statement)
            """,
        }, integration_test_source="\n".join(
            "def %s(): pass" % name
            for name in (
                "test_zz_assignment_apply_preserves_history_and_is_idempotent",
                "test_zz_supply_apply_preserves_history_and_is_idempotent",
                "test_zzz_concurrent_apply_never_duplicates_the_split",
                "test_zzz_concurrent_supply_apply_never_duplicates_allocation",
                "test_zzzz_stale_confirmed_quantity_rolls_back_every_apply_write",
                "test_zzzz_supply_delivery_drift_rolls_back_allocation",
            )
        ))

        self.assertFalse(report["ok"])
        self.assertIn("protected_table_mutation", {
            item["reasonCode"] for item in report["violations"]
        })

    def test_missing_reviewed_statement_or_integration_case_fails_closed(self):
        report = audit_cutover_inventory(
            source_files={"backend/features/estimate_row_transfer/storage.py": "value = 1\n"},
            integration_test_source="def test_zzz_concurrent_apply_never_duplicates_the_split(): pass\n",
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["ok"])
        reasons = {item["reasonCode"] for item in report["violations"]}
        self.assertIn("writer_inventory_mismatch", reasons)
        self.assertIn("integration_check_missing", reasons)


if __name__ == "__main__":
    unittest.main()
