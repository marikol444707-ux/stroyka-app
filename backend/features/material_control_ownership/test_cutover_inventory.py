import unittest
from pathlib import Path

from backend.features.material_control_ownership.cutover_inventory import (
    audit_cutover_inventory,
)


REQUIRED_CHECKS = (
    "test_same_name_cross_company_fixture_is_ready_and_unchanged",
    "test_zz_same_name_runtime_queries_are_owner_isolated",
    "test_zzz_foreign_lineage_rolls_back_without_protected_history_changes",
    "test_zzzz_concurrent_lineage_requests_serialize_without_duplicate",
    "test_zzzzz_final_cutover_report_is_read_only_and_exact",
)


def integration_source(*names):
    return "\n".join(f"def {name}(): pass" for name in names)


class MaterialControlCutoverInventoryTests(unittest.TestCase):
    def test_repository_inventory_has_only_reviewed_writers_and_all_real_postgres_checks(self):
        report = audit_cutover_inventory(
            Path(__file__).resolve().parents[3],
            integration_test_source=integration_source(*REQUIRED_CHECKS),
        )

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["writerInventoryReady"], report["violations"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["dmlStatements"], 5)
        self.assertEqual(report["requiredIntegrationChecks"], 5)
        self.assertEqual(report["missingIntegrationChecks"], [])
        self.assertEqual(report["violations"], [])

    def test_protected_history_mutation_fails_closed(self):
        report = audit_cutover_inventory(
            source_files={
                "backend/features/supply_lineage/service.py": """
                    def unsafe(cur):
                        cur.execute(
                            "UPDATE public.work_journal SET quantity=0 WHERE id=%s",
                            (1,),
                        )
                """,
            },
            integration_test_source=integration_source(*REQUIRED_CHECKS),
            enforce_complete_inventory=False,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertIn(
            "protected_history_mutation",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_writer_drift_or_missing_postgres_check_blocks_cutover(self):
        report = audit_cutover_inventory(
            source_files={
                "backend/main.py": """
                    def create_supply_request(cur):
                        cur.execute("INSERT INTO supply_requests(id) VALUES (1)")
                """,
            },
            integration_test_source=integration_source(REQUIRED_CHECKS[0]),
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["writerInventoryReady"])
        reasons = {item["reasonCode"] for item in report["violations"]}
        self.assertIn("writer_inventory_mismatch", reasons)
        self.assertIn("integration_check_missing", reasons)


if __name__ == "__main__":
    unittest.main()
