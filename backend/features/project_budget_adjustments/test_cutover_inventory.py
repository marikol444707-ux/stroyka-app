import unittest

from backend.features.project_budget_adjustments.cutover_inventory import (
    audit_cutover_inventory,
)


PREVIEW_ROUTES = '''
def register_project_budget_adjustment_preview_module(app, deps):
    @app.get("/estimate-reconciliations/{reconciliation_id}/budget-adjustment-preview")
    def get_budget_adjustment_preview():
        return None
'''

RUNTIME_ROUTES = '''
def register_project_budget_adjustment_runtime_module(app, deps):
    apply_adjustment = deps.get("apply_budget_adjustment")

    @app.post("/estimate-reconciliations/{reconciliation_id}/budget-adjustment-approval")
    def approve_budget_adjustment():
        return apply_adjustment()

    @app.get("/projects/{project_id}/budget-adjustments")
    def get_project_budget_adjustments():
        return None
'''

MAIN = '''
register_project_budget_adjustment_preview_module(app, {})
register_project_budget_adjustment_runtime_module(app, {})
'''

SMOKE = '''
check_not_spa_fallback "estimate budget adjustment preview route" "$BASE_URL/estimate-reconciliations/1/budget-adjustment-preview" "401 403"
check_post_not_spa_fallback "estimate budget adjustment approval route" "$BASE_URL/estimate-reconciliations/1/budget-adjustment-approval" "401 403 422"
check_not_spa_fallback "project budget adjustment history route" "$BASE_URL/projects/1/budget-adjustments" "401 403"
'''

POSTGRES_TESTS = '''
def test_transactional_kernel_applies_delta_once_and_is_idempotent(): pass
def test_stale_hash_and_source_drift_roll_back_without_receipt(): pass
def test_budget_conflict_after_receipt_insert_rolls_back_both_writes(): pass
def test_apply_preserves_protected_history_byte_for_byte(): pass
def test_concurrent_double_approval_changes_budget_once(): pass
'''

ROUTE_TESTS = '''
def test_missing_approval_body_uses_fixed_public_error_code(): pass
def test_invalid_history_range_uses_fixed_public_error_code(): pass
def test_exact_approval_commits_once_in_serializable_transaction(): pass
def test_idempotent_approval_rolls_back_without_commit(): pass
def test_invalid_identity_and_non_leader_never_reach_approval_kernel(): pass
def test_approval_maps_fixed_domain_and_write_conflicts(): pass
def test_history_is_tenant_bound_newest_first_bounded_and_read_only(): pass
'''


def audit(**overrides):
    values = {
        "route_sources": {
            "backend/features/project_budget_adjustments/preview_routes.py": (
                PREVIEW_ROUTES
            ),
            "backend/features/project_budget_adjustments/runtime_routes.py": (
                RUNTIME_ROUTES
            ),
        },
        "main_source": MAIN,
        "smoke_source": SMOKE,
        "integration_test_sources": {
            "backend/features/project_budget_adjustments/test_postgres_schema.py": (
                POSTGRES_TESTS
            ),
            "backend/features/project_budget_adjustments/test_runtime_routes.py": (
                ROUTE_TESTS
            ),
        },
    }
    values.update(overrides)
    return audit_cutover_inventory(**values)


class BudgetAdjustmentCutoverInventoryTests(unittest.TestCase):
    def test_exact_routes_registration_smoke_and_integration_proofs_are_ready(self):
        report = audit()

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["routeInventoryReady"])
        self.assertTrue(report["integrationInventoryReady"])
        self.assertEqual(report["routeCount"], 3)
        self.assertEqual(report["registrationCount"], 2)
        self.assertEqual(report["smokeCheckCount"], 3)
        self.assertEqual(report["requiredIntegrationChecks"], 12)
        self.assertEqual(report["missingIntegrationChecks"], [])
        self.assertEqual(report["writesAttempted"], 0)

    def test_missing_or_duplicate_route_fails_closed(self):
        missing = audit(route_sources={
            "backend/features/project_budget_adjustments/preview_routes.py": (
                PREVIEW_ROUTES
            ),
            "backend/features/project_budget_adjustments/runtime_routes.py": "",
        })
        duplicate = audit(route_sources={
            "backend/features/project_budget_adjustments/preview_routes.py": (
                PREVIEW_ROUTES
            ),
            "backend/features/project_budget_adjustments/runtime_routes.py": (
                RUNTIME_ROUTES
                + '\n@app.post("/estimate-reconciliations/{reconciliation_id}/budget-adjustment-approval")\n'
                + "def duplicate_approval(): pass\n"
            ),
        })

        self.assertFalse(missing["routeInventoryReady"])
        self.assertFalse(duplicate["routeInventoryReady"])
        for report in (missing, duplicate):
            self.assertIn(
                "budget_adjustment_route_inventory_mismatch",
                {item["reasonCode"] for item in report["violations"]},
            )

    def test_registration_smoke_or_kernel_entrypoint_drift_fails_closed(self):
        missing_registration = audit(main_source=(
            "register_project_budget_adjustment_preview_module(app, {})\n"
        ))
        missing_smoke = audit(smoke_source=SMOKE.replace(
            'check_post_not_spa_fallback "estimate budget adjustment approval route" "$BASE_URL/estimate-reconciliations/1/budget-adjustment-approval" "401 403 422"\n',
            "",
        ))
        automatic_apply = audit(route_sources={
            "backend/features/project_budget_adjustments/preview_routes.py": (
                PREVIEW_ROUTES
                + "\ndef automatic_reconciliation_flow():\n"
                + "    return apply_adjustment()\n"
            ),
            "backend/features/project_budget_adjustments/runtime_routes.py": (
                RUNTIME_ROUTES
            ),
        })

        self.assertFalse(missing_registration["routeInventoryReady"])
        self.assertFalse(missing_smoke["routeInventoryReady"])
        self.assertFalse(automatic_apply["routeInventoryReady"])

    def test_missing_or_renamed_integration_proof_fails_closed(self):
        sources = {
            "backend/features/project_budget_adjustments/test_postgres_schema.py": (
                POSTGRES_TESTS.replace(
                    "test_concurrent_double_approval_changes_budget_once",
                    "test_concurrent_approval",
                )
            ),
            "backend/features/project_budget_adjustments/test_runtime_routes.py": (
                ROUTE_TESTS
            ),
        }

        report = audit(integration_test_sources=sources)

        self.assertFalse(report["ok"])
        self.assertFalse(report["integrationInventoryReady"])
        self.assertEqual(report["missingIntegrationChecks"], [
            "test_concurrent_double_approval_changes_budget_once",
        ])

    def test_parse_failure_is_a_fixed_bounded_blocker(self):
        report = audit(route_sources={"backend/broken.py": "def broken(:\n"})

        self.assertFalse(report["ok"])
        self.assertEqual(report["violationCount"], 3)
        self.assertIn(
            "source_parse_error",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_real_repository_has_exact_cutover_inventory(self):
        report = audit_cutover_inventory()

        self.assertTrue(report["ok"], report["violations"])
        self.assertEqual(report["routeCount"], 3)
        self.assertEqual(report["registrationCount"], 2)
        self.assertEqual(report["smokeCheckCount"], 3)
        self.assertEqual(report["requiredIntegrationChecks"], 12)


if __name__ == "__main__":
    unittest.main()
