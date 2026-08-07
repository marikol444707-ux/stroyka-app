import unittest
from pathlib import Path

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
from .approval import apply_budget_adjustment

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
def test_zzz_readiness_gate_is_read_only_and_green(): pass
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
        self.assertTrue(report["frontendInventoryReady"])
        self.assertEqual(report["routeCount"], 3)
        self.assertEqual(report["registrationCount"], 2)
        self.assertEqual(report["smokeCheckCount"], 3)
        self.assertEqual(report["requiredIntegrationChecks"], 13)
        self.assertEqual(report["requiredFrontendChecks"], 17)
        self.assertEqual(report["missingFrontendChecks"], [])
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

        unexpected_registration = audit(main_source=(
            MAIN
            + "register_project_budget_adjustment_backdoor_module(app, {})\n"
        ))
        aliased_kernel_import = audit(application_sources={
            "backend/features/project_budget_adjustments/runtime_routes.py": (
                RUNTIME_ROUTES
            ),
            "backend/features/other/routes.py": '''
from backend.features.project_budget_adjustments.approval import apply_budget_adjustment as execute
def automatic_reconciliation_flow():
    return execute()
''',
        })

        self.assertFalse(unexpected_registration["routeInventoryReady"])
        self.assertFalse(aliased_kernel_import["routeInventoryReady"])

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

    def test_frontend_wiring_or_required_ui_proof_drift_fails_closed(self):
        action_path = "src/features/estimates/projectBudgetAdjustmentActions.js"
        test_path = "src/components/ProjectBudgetAdjustmentPanel.test.jsx"
        frontend_sources = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "src/App.js",
                action_path,
                "src/features/app-shell/useAppBusinessRuntime.js",
                "src/features/estimates/projectEstimateRuntime.jsx",
                "src/components/EstimateReconciliationsPanel.jsx",
                "src/components/ProjectBudgetAdjustmentPanel.jsx",
            )
        }
        frontend_tests = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "src/features/estimates/projectBudgetAdjustmentActions.test.js",
                test_path,
                "src/components/EstimateReconciliationsPanel.test.jsx",
                "src/features/estimates/projectEstimateRuntime.test.jsx",
            )
        }
        missing_wiring = dict(frontend_sources)
        missing_wiring[action_path] = missing_wiring[action_path].replace(
            "/budget-adjustment-approval",
            "/budget-adjustment-disabled",
        )
        renamed_test = dict(frontend_tests)
        renamed_test[test_path] = renamed_test[test_path].replace(
            "shows exact before, delta and after values before one explicit approval",
            "shows budget values",
        )

        wiring_report = audit_cutover_inventory(
            frontend_sources=missing_wiring,
            frontend_test_sources=frontend_tests,
        )
        proof_report = audit_cutover_inventory(
            frontend_sources=frontend_sources,
            frontend_test_sources=renamed_test,
        )

        self.assertFalse(wiring_report["frontendInventoryReady"])
        self.assertFalse(proof_report["frontendInventoryReady"])
        self.assertIn(
            "budget_adjustment_frontend_wiring_mismatch",
            {item["reasonCode"] for item in wiring_report["violations"]},
        )
        self.assertEqual(proof_report["missingFrontendChecks"], [
            "shows exact before, delta and after values before one explicit approval",
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
        self.assertEqual(report["requiredIntegrationChecks"], 13)
        self.assertTrue(report["frontendInventoryReady"])
        self.assertEqual(report["requiredFrontendChecks"], 17)


if __name__ == "__main__":
    unittest.main()
