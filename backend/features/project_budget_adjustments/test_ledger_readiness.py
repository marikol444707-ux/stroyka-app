import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.features.project_budget_adjustments.ledger_readiness import (
    build_receipt_ledger_readiness,
    collect_receipt_ledger_readiness,
)
from backend.features.project_budget_adjustments.plan import (
    build_budget_adjustment_plan,
)


def valid_receipt(**overrides):
    now = datetime(2026, 8, 7, tzinfo=timezone.utc)
    row = {
        "id": 1,
        "company_id": 10,
        "project_id": 20,
        "reconciliation_id": 7,
        "base_estimate_id": 100,
        "next_estimate_id": 101,
        "project_budget_before": Decimal("1000.00"),
        "estimate_base_total": Decimal("100.00"),
        "estimate_next_total": Decimal("125.00"),
        "adjustment_amount": Decimal("25.00"),
        "project_budget_after": Decimal("1025.00"),
        "plan_sha256": None,
        "approved_by_user_id": 55,
        "approved_by_name": "Director",
        "approved_by_role": "директор",
        "approved_at": now,
        "created_at": now,
        "current_project_id": 20,
        "current_project_company_id": 10,
        "current_reconciliation_id": 7,
        "current_base_estimate_id": 100,
        "current_next_estimate_id": 101,
        "current_base_id": 100,
        "current_base_company_id": 10,
        "current_base_project_id": 20,
        "current_next_id": 101,
        "current_next_company_id": 10,
        "current_next_project_id": 20,
        "current_approved_user_id": 55,
    }
    row.update(overrides)
    if "plan_sha256" not in overrides:
        row["plan_sha256"] = build_budget_adjustment_plan({
            "reconciliationId": row["reconciliation_id"],
            "companyId": row["company_id"],
            "projectId": row["project_id"],
            "baseEstimateId": row["base_estimate_id"],
            "nextEstimateId": row["next_estimate_id"],
            "projectBudgetBefore": row["project_budget_before"],
            "estimateBaseTotal": row["estimate_base_total"],
            "estimateNextTotal": row["estimate_next_total"],
        })["planSha256"]
    return row


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.rows


class BudgetAdjustmentLedgerPureTests(unittest.TestCase):
    def test_empty_and_exact_valid_receipt_ledgers_are_ready(self):
        empty = build_receipt_ledger_readiness([])
        report = build_receipt_ledger_readiness([valid_receipt()])

        self.assertTrue(empty["ledgerReady"])
        self.assertTrue(report["ledgerReady"])
        self.assertEqual(report["summary"], {
            "receiptsTotal": 1,
            "validReceipts": 1,
            "projectsWithReceipts": 1,
            "uniqueReconciliations": 1,
            "duplicateReconciliations": 0,
            "duplicatePlanHashes": 0,
        })
        self.assertEqual(report["issues"], [])

    def test_money_equation_and_hash_tampering_fail_with_id_only_evidence(self):
        report = build_receipt_ledger_readiness([
            valid_receipt(
                approved_by_name="Sensitive Person",
                adjustment_amount=Decimal("24.00"),
                plan_sha256="f" * 64,
            )
        ])

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(report["validReceipts"], 0)
        self.assertEqual(
            set(report["reasonCounts"]),
            {
                "budget_adjustment_receipt_equation_mismatch",
                "budget_adjustment_receipt_plan_hash_mismatch",
            },
        )
        encoded = json.dumps(report, ensure_ascii=False, default=str)
        self.assertNotIn("Sensitive Person", encoded)
        self.assertNotIn("1000.00", encoded)
        self.assertNotIn("f" * 64, encoded)
        for issue in report["issues"]:
            self.assertEqual(
                set(issue),
                {"reasonCode", "receiptId", "projectId", "reconciliationId"},
            )

    def test_duplicate_reconciliation_and_hash_are_both_blockers(self):
        first = valid_receipt()
        second = valid_receipt(id=2)

        report = build_receipt_ledger_readiness([first, second])

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(report["summary"]["duplicateReconciliations"], 1)
        self.assertEqual(report["summary"]["duplicatePlanHashes"], 1)
        self.assertEqual(report["reasonCounts"], {
            "budget_adjustment_duplicate_plan_hash": 1,
            "budget_adjustment_duplicate_reconciliation": 1,
        })

    def test_owner_source_actor_and_timestamp_drift_fail_closed(self):
        row = valid_receipt(
            current_project_company_id=11,
            current_next_project_id=21,
            current_base_estimate_id=999,
            current_approved_user_id=None,
            approved_by_role="сметчик",
            created_at=None,
        )

        report = build_receipt_ledger_readiness([row])

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(set(report["reasonCounts"]), {
            "budget_adjustment_receipt_actor_invalid",
            "budget_adjustment_receipt_base_source_mismatch",
            "budget_adjustment_receipt_project_owner_mismatch",
            "budget_adjustment_receipt_timestamp_invalid",
            "budget_adjustment_receipt_user_missing",
            "budget_adjustment_receipt_next_owner_mismatch",
        })

    def test_issue_preview_is_bounded_but_total_count_is_exact(self):
        rows = [
            valid_receipt(
                id=index + 1,
                reconciliation_id=index + 1000,
                current_reconciliation_id=None,
            )
            for index in range(5)
        ]

        report = build_receipt_ledger_readiness(rows, max_issues=2)

        self.assertEqual(report["issueCount"], 5)
        self.assertEqual(len(report["issues"]), 2)
        self.assertTrue(report["issuesTruncated"])

    def test_created_timestamp_cannot_precede_approval(self):
        approved_at = datetime(2026, 8, 7, tzinfo=timezone.utc)
        report = build_receipt_ledger_readiness([valid_receipt(
            approved_at=approved_at,
            created_at=approved_at - timedelta(seconds=1),
        )])

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(report["reasonCounts"], {
            "budget_adjustment_receipt_timestamp_invalid": 1,
        })


class BudgetAdjustmentLedgerCollectionTests(unittest.TestCase):
    def test_collector_uses_one_bounded_select_without_current_money_or_payload(self):
        cursor = FakeCursor([valid_receipt()])

        report = collect_receipt_ledger_readiness(cursor, max_receipt_rows=2)

        self.assertTrue(report["ledgerReady"], report["issues"])
        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        self.assertTrue(sql.upper().startswith("SELECT "))
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(params, (3,))
        for forbidden in (
            "sections_json", "project_name", "estimate_name", "p.budget",
            "r.base_total", "r.next_total", "b.total", "n.total",
        ):
            self.assertNotIn(forbidden, sql.lower())

    def test_scan_limit_returns_one_fixed_blocker_without_classifying_rows(self):
        cursor = FakeCursor([valid_receipt(), valid_receipt(id=2)])

        report = collect_receipt_ledger_readiness(
            cursor,
            max_receipt_rows=1,
        )

        self.assertFalse(report["ledgerReady"])
        self.assertFalse(report["scanComplete"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "budget_adjustment_receipt_scan_limit_exceeded",
        }])
        self.assertEqual(report["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
