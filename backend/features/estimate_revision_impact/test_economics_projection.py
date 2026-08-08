import json
import unittest
from pathlib import Path

from backend.features.estimate_revision_impact.economics_projection import (
    ECONOMICS_REQUIRED_COLUMNS,
    build_economics_projection,
    collect_economics_impact_audit,
    run_economics_impact_audit,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    REQUIRED_SCHEMA_ROWS,
    estimate_row,
    reconciliation_row,
    source,
)


ECONOMICS_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in ECONOMICS_REQUIRED_COLUMNS.items()
    for column in columns
)


def source_context():
    return {
        "companyId": 4,
        "projectId": 17,
        "estimateId": 52,
        "baseEstimateId": 51,
        "reconciliationId": 91,
    }


def preview(**changes):
    value = {
        "reconciliationId": 91,
        "companyId": 4,
        "projectId": 17,
        "baseEstimateId": 51,
        "nextEstimateId": 52,
        "projectBudgetBefore": "1000.00",
        "estimateBaseTotal": "250.00",
        "estimateNextTotal": "275.50",
        "adjustmentAmount": "25.50",
        "projectBudgetAfter": "1025.50",
        "planSha256": (
            "697113e2eeec51f1126b57d12bf8f1d4347cd4c2acdedced45a4b8e6ba042f4f"
        ),
        "readyForApproval": True,
        "blockers": [],
    }
    value.update(changes)
    return value


class EconomicsProjectionContractTests(unittest.TestCase):
    def test_exact_plan_is_complete_but_requires_explicit_authorization(self):
        projection = build_economics_projection(
            source_context(), preview=preview(), authorized=False,
        )

        self.assertTrue(projection["complete"])
        self.assertFalse(projection["actionable"])
        self.assertEqual(projection["state"], "non_actionable")
        self.assertEqual(projection["authorizationState"], "not_evaluated")
        self.assertEqual(projection["reasonCounts"], {
            "budget_adjustment_authorization_required": 1,
        })
        self.assertEqual(projection["budget"], {
            "projectBudgetBefore": "1000.00",
            "estimateBaseTotal": "250.00",
            "estimateNextTotal": "275.50",
            "adjustmentAmount": "25.50",
            "projectBudgetAfter": "1025.50",
        })
        self.assertEqual(
            projection["planSha256"],
            "697113e2eeec51f1126b57d12bf8f1d4347cd4c2acdedced45a4b8e6ba042f4f",
        )

    def test_authorized_exact_plan_is_actionable_without_changing_the_plan(self):
        projection = build_economics_projection(
            source_context(), preview=preview(), authorized=True,
        )

        self.assertTrue(projection["complete"])
        self.assertTrue(projection["actionable"])
        self.assertEqual(projection["state"], "complete")
        self.assertEqual(projection["authorizationState"], "authorized")
        self.assertEqual(projection["reasonCounts"], {})
        self.assertEqual(
            projection["planSha256"],
            "697113e2eeec51f1126b57d12bf8f1d4347cd4c2acdedced45a4b8e6ba042f4f",
        )

        not_authorized = build_economics_projection(
            source_context(), preview=preview(), authorized="yes",
        )
        self.assertFalse(not_authorized["actionable"])
        self.assertEqual(not_authorized["authorizationState"], "not_evaluated")

    def test_zero_delta_is_complete_and_non_actionable(self):
        projection = build_economics_projection(
            source_context(),
            preview=preview(
                estimateNextTotal="250.00",
                adjustmentAmount="0.00",
                projectBudgetAfter="1000.00",
                planSha256=(
                    "4e19602bae011ccdf75945a9e0e58a27f702cecb5c1709662bd7533d9ab55408"
                ),
                readyForApproval=False,
                blockers=["budget_adjustment_zero_delta"],
            ),
            authorized=True,
        )

        self.assertTrue(projection["complete"])
        self.assertFalse(projection["actionable"])
        self.assertEqual(projection["state"], "non_actionable")
        self.assertEqual(projection["reasonCounts"], {
            "budget_adjustment_zero_delta": 1,
        })

    def test_unapproved_and_already_applied_are_explicit_complete_states(self):
        for blocker in (
            "budget_adjustment_reconciliation_not_approved",
            "budget_adjustment_already_applied",
        ):
            with self.subTest(blocker=blocker):
                projection = build_economics_projection(
                    source_context(), blocker=blocker,
                )
                self.assertTrue(projection["complete"])
                self.assertFalse(projection["actionable"])
                self.assertEqual(projection["state"], "non_actionable")
                self.assertEqual(projection["budget"], {})
                self.assertEqual(projection["reasonCounts"], {blocker: 1})

    def test_stale_or_malformed_evidence_is_incomplete(self):
        for blocker in (
            "budget_adjustment_source_drift",
            "budget_adjustment_owner_mismatch",
            "budget_adjustment_estimate_content_invalid",
        ):
            with self.subTest(blocker=blocker):
                projection = build_economics_projection(
                    source_context(), blocker=blocker,
                )
                self.assertFalse(projection["complete"])
                self.assertFalse(projection["actionable"])
                self.assertEqual(projection["state"], "incomplete")
                self.assertEqual(projection["reasonCounts"], {blocker: 1})

        unknown = build_economics_projection(
            source_context(), blocker="untrusted business text",
        )
        self.assertEqual(unknown["reasonCounts"], {
            "economics_preview_error": 1,
        })

    def test_rejects_preview_identity_money_and_hash_drift(self):
        invalid = (
            preview(companyId=5),
            preview(adjustmentAmount="25.500"),
            preview(planSha256="A" * 64),
            preview(extra=True),
        )

        for value in invalid:
            with self.subTest(value=value):
                projection = build_economics_projection(
                    source_context(), preview=value, authorized=True,
                )
                self.assertFalse(projection["complete"])
                self.assertEqual(projection["reasonCounts"], {
                    "economics_preview_contract_invalid": 1,
                })


class EconomicsProjectionCollectorTests(unittest.TestCase):
    def result_sets(self):
        return (
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            ECONOMICS_SCHEMA_ROWS,
        )

    def test_collects_exact_e6_preview_with_bounded_selects_only(self):
        cursor = FakeCursor(self.result_sets())
        calls = []

        def preview_builder(_cur, reconciliation_id, company_id):
            calls.append((reconciliation_id, company_id))
            return preview()

        report = collect_economics_impact_audit(
            cursor, source(), preview_builder=preview_builder,
        )

        self.assertTrue(report["readyForEconomicsProjection"])
        self.assertFalse(report["economicsImpact"]["actionable"])
        self.assertEqual(calls, [(91, 4)])
        self.assertEqual(report["writesAttempted"], 0)
        for sql, _params in cursor.calls:
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            for mutation in ("INSERT ", "UPDATE ", "DELETE "):
                self.assertNotIn(mutation, normalized)

    def test_preview_fixed_error_becomes_bounded_non_actionable_result(self):
        from backend.features.project_budget_adjustments.preview import (
            BudgetAdjustmentPreviewError,
        )

        cursor = FakeCursor(self.result_sets())

        def preview_builder(_cur, _reconciliation_id, _company_id):
            raise BudgetAdjustmentPreviewError(
                "budget_adjustment_reconciliation_not_approved"
            )

        report = collect_economics_impact_audit(
            cursor, source(), preview_builder=preview_builder,
        )

        self.assertTrue(report["readyForEconomicsProjection"])
        self.assertEqual(report["economicsImpact"]["reasonCounts"], {
            "budget_adjustment_reconciliation_not_approved": 1,
        })

    def test_missing_schema_is_incomplete_without_calling_e6_preview(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            (),
        ))

        report = collect_economics_impact_audit(
            cursor,
            source(),
            preview_builder=lambda *_args: self.fail("preview must not run"),
        )

        self.assertFalse(report["readyForEconomicsProjection"])
        self.assertFalse(report["economicsImpact"]["schemaReady"])
        self.assertEqual(report["economicsImpact"]["reasonCounts"], {
            "economics_impact_schema_not_ready": 1,
        })

    def test_runner_uses_one_read_only_transaction_and_rolls_back(self):
        cursor = FakeCursor(self.result_sets())
        connection = FakeConnection(cursor)

        report = run_economics_impact_audit(
            lambda: connection,
            source(),
            preview_builder=lambda *_args: preview(),
        )

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_operator_command_is_registered(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text())

        self.assertEqual(
            package["scripts"]["audit:estimate-revision-economics-impact"],
            (
                "python3 -m "
                "backend.features.estimate_revision_impact.economics_projection"
            ),
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "economics_projection",
                (root / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
