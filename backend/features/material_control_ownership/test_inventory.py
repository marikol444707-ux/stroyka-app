import unittest
from pathlib import Path

from backend.features.material_control_ownership.inventory import (
    audit_runtime_inventory,
)


class MaterialControlRuntimeInventoryTests(unittest.TestCase):
    def test_repository_inventory_requires_every_runtime_boundary_to_be_owner_scoped(self):
        report = audit_runtime_inventory(Path(__file__).resolve().parents[3])

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["runtimeInventoryReady"], report["violations"])
        self.assertEqual(report["candidateCount"], 6)
        self.assertEqual(report["nameScopedCount"], 0)
        self.assertEqual(report["ownerScopedCount"], 6)
        self.assertEqual(report["violations"], [])

    def test_reviewed_frontend_owner_matcher_is_owner_scoped(self):
        sources = {
            "src/features/estimates/projectEstimateRuntime.jsx": """
                const activeEstimatesForProject = (project) => {
                  return estimates.filter(estimate => (
                    sameStoredProjectOwner(project, estimate)
                    && estimate.status === 'Активная'
                  ));
                };
            """,
        }

        report = audit_runtime_inventory(
            source_files=sources,
            expected_candidates={
                (
                    "src/features/estimates/projectEstimateRuntime.jsx",
                    "activeEstimatesForProject",
                ),
            },
        )

        self.assertTrue(report["runtimeInventoryReady"], report["violations"])
        self.assertEqual(report["ownerScopedCount"], 1)

    def test_exact_owner_candidates_are_ready(self):
        sources = {
            "src/features/estimates/projectEstimateRuntime.jsx": """
                const activeEstimatesForProject = (p) => {
                  return estimates.filter(e => (
                    e.companyId === p.companyId && e.projectId === p.id
                    && e.status === 'Активная'
                  ));
                };
            """,
            "backend/main.py": """
                def _supply_material_estimate_control(cur, company_id, project_id):
                    cur.execute(\"\"\"SELECT id,sections_json FROM estimates e
                        WHERE e.company_id=%s AND e.project_id=%s
                        AND e.status='Активная' AND e.smeta_type='Материалы'\"\"\")

                def _supply_linked_work_estimate_control(cur, company_id, project_id):
                    cur.execute(\"\"\"SELECT id,sections_json FROM estimates e
                        WHERE e.company_id=%s AND e.project_id=%s
                        AND e.status='Активная' AND e.smeta_type='Заказчик'\"\"\")
            """,
        }

        report = audit_runtime_inventory(
            source_files=sources,
            expected_candidates={
                (
                    "src/features/estimates/projectEstimateRuntime.jsx",
                    "activeEstimatesForProject",
                ),
                ("backend/main.py", "_supply_material_estimate_control"),
                ("backend/main.py", "_supply_linked_work_estimate_control"),
            },
        )

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["runtimeInventoryReady"], report["violations"])
        self.assertEqual(report["candidateCount"], 3)
        self.assertEqual(report["nameScopedCount"], 0)
        self.assertEqual(report["violations"], [])

    def test_missing_or_unreviewed_candidate_fails_closed(self):
        sources = {
            "src/features/estimates/projectEstimateRuntime.jsx": "",
            "backend/main.py": """
                def _supply_new_estimate_control(cur, company_id, project_id):
                    cur.execute(\"\"\"SELECT id,sections_json FROM estimates e
                        WHERE e.company_id=%s AND e.project_id=%s
                        AND e.status='Активная' AND e.smeta_type='Материалы'\"\"\")
            """,
        }

        report = audit_runtime_inventory(source_files=sources)

        self.assertFalse(report["runtimeInventoryReady"])
        reasons = {item["reasonCode"] for item in report["violations"]}
        self.assertIn("active_estimate_inventory_missing", reasons)
        self.assertIn("active_estimate_inventory_unreviewed", reasons)


if __name__ == "__main__":
    unittest.main()
