import json
import unittest
from decimal import Decimal

from backend.features.project_budget_adjustments.preview import (
    BudgetAdjustmentPreviewError,
)
from backend.features.project_budget_adjustments.preview_service import (
    PUBLIC_PREVIEW_FIELDS,
    build_budget_adjustment_preview,
)


def sections(total):
    return json.dumps([{
        "name": "Работы",
        "items": [{
            "quantity": "1",
            "priceWork": str(total),
            "priceMaterial": "0",
        }],
    }])


def source_row(**changes):
    row = {
        "reconciliation_id": 7,
        "base_estimate_id": 100,
        "next_estimate_id": 101,
        "reconciliation_status": "Утверждена",
        "reconciliation_type": "Заказчик",
        "reconciliation_package": "Основная",
        "reconciliation_base_total": Decimal("250.00"),
        "reconciliation_next_total": Decimal("275.50"),
        "project_id": 20,
        "company_id": 10,
        "project_budget": Decimal("1000.00"),
        "stored_base_estimate_id": 100,
        "base_company_id": 10,
        "base_project_id": 20,
        "base_status": "Черновик",
        "base_type": "Заказчик",
        "base_package": "Основная",
        "base_stored_total": Decimal("250.00"),
        "base_sections_json": sections("250.00"),
        "stored_next_estimate_id": 101,
        "next_company_id": 10,
        "next_project_id": 20,
        "next_status": "Активная",
        "next_type": "Заказчик",
        "next_package": "Основная",
        "next_stored_total": Decimal("275.50"),
        "next_sections_json": sections("275.50"),
        "existing_adjustment_id": None,
        "active_scope_count": 1,
    }
    row.update(changes)
    return row


def build(row=None, *, reconciliation_id=7, company_id=10):
    calls = []

    def loader(_cur, actual_reconciliation_id, actual_company_id):
        calls.append((actual_reconciliation_id, actual_company_id))
        return row

    result = build_budget_adjustment_preview(
        object(),
        reconciliation_id,
        company_id,
        source_loader=loader,
    )
    return result, calls


def error_code(row=None, *, reconciliation_id=7, company_id=10):
    with unittest.TestCase().assertRaises(BudgetAdjustmentPreviewError) as raised:
        build(row, reconciliation_id=reconciliation_id, company_id=company_id)
    return raised.exception.code


class BudgetAdjustmentPreviewServiceTests(unittest.TestCase):
    def test_builds_bounded_exact_public_preview(self):
        preview, calls = build(source_row())

        self.assertEqual(set(preview), PUBLIC_PREVIEW_FIELDS)
        self.assertEqual(calls, [(7, 10)])
        self.assertEqual(preview, {
            "reconciliationId": 7,
            "companyId": 10,
            "projectId": 20,
            "baseEstimateId": 100,
            "nextEstimateId": 101,
            "projectBudgetBefore": "1000.00",
            "estimateBaseTotal": "250.00",
            "estimateNextTotal": "275.50",
            "adjustmentAmount": "25.50",
            "projectBudgetAfter": "1025.50",
            "planSha256": "bc6ba21cb278830bf87ce83c1e5ae945893fb8a8cf62ee0d68f473e54feb4fbb",
            "readyForApproval": True,
            "blockers": [],
        })
        self.assertNotIn("base_sections_json", preview)
        self.assertNotIn("noOp", preview)

    def test_missing_or_foreign_source_uses_the_same_not_found_code(self):
        self.assertEqual(error_code(None), "budget_adjustment_not_found")

    def test_rejects_invalid_external_identity_before_loading(self):
        for reconciliation_id, company_id in (
            (0, 10), (True, 10), ("7", 10), (7, 0), (7, True),
        ):
            with self.subTest(
                reconciliation_id=reconciliation_id,
                company_id=company_id,
            ):
                self.assertEqual(
                    error_code(
                        source_row(),
                        reconciliation_id=reconciliation_id,
                        company_id=company_id,
                    ),
                    "budget_adjustment_identity_invalid",
                )

    def test_requires_approved_reconciliation(self):
        self.assertEqual(
            error_code(source_row(reconciliation_status="Черновик")),
            "budget_adjustment_reconciliation_not_approved",
        )

    def test_rejects_every_owner_mismatch(self):
        cases = (
            {"company_id": 11},
            {"project_id": 21},
            {"base_company_id": 11},
            {"base_project_id": 21},
            {"next_company_id": 11},
            {"next_project_id": 21},
            {"stored_base_estimate_id": 999},
            {"stored_next_estimate_id": 999},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(
                    error_code(source_row(**changes)),
                    "budget_adjustment_owner_mismatch",
                )

    def test_rejects_type_and_package_mismatch(self):
        for field in ("reconciliation_type", "base_type", "next_type"):
            with self.subTest(field=field):
                self.assertEqual(
                    error_code(source_row(**{field: "Подрядчик"})),
                    "budget_adjustment_type_not_customer",
                )
        for field in ("base_package", "next_package"):
            with self.subTest(field=field):
                self.assertEqual(
                    error_code(source_row(**{field: "Электрика"})),
                    "budget_adjustment_package_mismatch",
                )

    def test_requires_one_active_next_revision(self):
        self.assertEqual(
            error_code(source_row(next_status="Черновик")),
            "budget_adjustment_next_not_active",
        )
        for count in (0, 2):
            with self.subTest(count=count):
                self.assertEqual(
                    error_code(source_row(active_scope_count=count)),
                    "budget_adjustment_active_revision_conflict",
                )

    def test_rejects_existing_receipt_before_building_a_second_plan(self):
        self.assertEqual(
            error_code(source_row(existing_adjustment_id=55)),
            "budget_adjustment_already_applied",
        )

    def test_recomputes_both_estimate_totals_and_rejects_drift(self):
        for changes in (
            {"base_sections_json": sections("249.99")},
            {"next_sections_json": sections("275.51")},
            {"base_stored_total": Decimal("249.99")},
            {"next_stored_total": Decimal("275.51")},
            {"reconciliation_base_total": Decimal("249.99")},
            {"reconciliation_next_total": Decimal("275.51")},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(
                    error_code(source_row(**changes)),
                    "budget_adjustment_source_drift",
                )

    def test_zero_delta_returns_hashed_non_approvable_preview(self):
        preview, _calls = build(source_row(
            reconciliation_next_total=Decimal("250.00"),
            next_stored_total=Decimal("250.00"),
            next_sections_json=sections("250.00"),
        ))

        self.assertEqual(preview["adjustmentAmount"], "0.00")
        self.assertEqual(preview["projectBudgetAfter"], "1000.00")
        self.assertFalse(preview["readyForApproval"])
        self.assertEqual(preview["blockers"], ["budget_adjustment_zero_delta"])


if __name__ == "__main__":
    unittest.main()
