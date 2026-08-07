import unittest
from copy import deepcopy
from decimal import Decimal

from backend.features.estimate_row_transfer.readiness_report import (
    MAX_SCAN_PLANS,
    build_ledger_report,
    collect_ledger_readiness,
    normalize_cutover_scope,
    run_readiness_report,
)
from backend.features.estimate_row_transfer.test_storage import (
    entry_row,
    header_row,
    reviewed_plan,
)


def approved_fixture():
    plan = reviewed_plan()
    header = header_row(
        plan,
        status="approved",
        approved_plan_sha256=plan["planSha256"],
        approved_by_user_id=2,
        approved_by_name="Director",
        approved_by_role="директор",
        approved_at="2026-08-07 10:00:00+03",
    )
    return plan, header, entry_row(plan)


def assignment_receipt(plan, **overrides):
    entry = plan["entries"][0]
    before = Decimal(entry["sourceTotalQuantity"])
    transferred = Decimal(entry["quantity"])
    row = {
        "id": 21,
        "entry_id": 8,
        "plan_id": 5,
        "company_id": plan["companyId"],
        "project_id": plan["projectId"],
        "reconciliation_id": plan["reconciliationId"],
        "plan_sha256": plan["planSha256"],
        "source_contract_id": entry["sourceParentId"],
        "source_item_id": entry["sourceId"],
        "source_estimate_version_id": entry["source"]["estimateVersionId"],
        "source_section_index": entry["source"]["sectionIndex"],
        "source_item_index": entry["source"]["itemIndex"],
        "source_item_key": entry["source"]["itemKey"],
        "target_estimate_version_id": entry["target"]["estimateVersionId"],
        "target_section_index": entry["target"]["sectionIndex"],
        "target_item_index": entry["target"]["itemIndex"],
        "target_item_key": entry["target"]["itemKey"],
        "source_quantity_before": before,
        "source_quantity_after": before - transferred,
        "source_done_quantity": Decimal(entry["sourceProtectedQuantity"]),
        "confirmed_quantity": Decimal(entry["sourceProtectedQuantity"]),
        "transfer_quantity": transferred,
        "contract_total_before": Decimal("1000"),
        "contract_total_after": Decimal("1000"),
    }
    row.update(overrides)
    return row


def mixed_fixture():
    from backend.features.estimate_row_transfer.plan import calculate_plan_sha256

    plan, header, assignment = approved_fixture()
    plan = deepcopy(plan)
    supply_canonical = deepcopy(plan["entries"][0])
    supply_canonical.update({
        "sourceKind": "supply",
        "sourceId": 61,
        "sourceParentId": 61,
        "requestItemIndex": 0,
    })
    plan["entries"].append(supply_canonical)
    plan["planSha256"] = calculate_plan_sha256(plan)
    header["plan_sha256"] = plan["planSha256"]
    header["approved_plan_sha256"] = plan["planSha256"]
    supply = deepcopy(assignment)
    supply.update({
        "id": 9,
        "source_kind": "supply",
        "source_id": 61,
        "source_parent_id": 61,
        "request_item_index": 0,
    })
    return plan, header, assignment, supply


def supply_allocation(plan, **overrides):
    entry = plan["entries"][1]
    requested = Decimal(entry["sourceTotalQuantity"])
    protected = Decimal(entry["sourceProtectedQuantity"])
    allocated = Decimal(entry["quantity"])
    received = protected / 2
    prior = protected - received
    row = {
        "id": 31,
        "entry_id": 9,
        "plan_id": 5,
        "company_id": plan["companyId"],
        "project_id": plan["projectId"],
        "reconciliation_id": plan["reconciliationId"],
        "plan_sha256": plan["planSha256"],
        "request_id": entry["sourceId"],
        "request_item_index": entry["requestItemIndex"],
        "request_item_sha256": "a" * 64,
        "source_estimate_id": entry["source"]["estimateId"],
        "source_estimate_version_id": entry["source"]["estimateVersionId"],
        "source_section_index": entry["source"]["sectionIndex"],
        "source_item_index": entry["source"]["itemIndex"],
        "source_item_key": entry["source"]["itemKey"],
        "source_sections_sha256": entry["source"]["sectionsSha256"],
        "target_estimate_id": entry["target"]["estimateId"],
        "target_estimate_version_id": entry["target"]["estimateVersionId"],
        "target_section_index": entry["target"]["sectionIndex"],
        "target_item_index": entry["target"]["itemIndex"],
        "target_item_key": entry["target"]["itemKey"],
        "target_sections_sha256": entry["target"]["sectionsSha256"],
        "requested_quantity": requested,
        "received_quantity": received,
        "previously_allocated_quantity": prior,
        "allocation_quantity": allocated,
        "remaining_unallocated_quantity": requested - protected - allocated,
    }
    row.update(overrides)
    return row


class EstimateRowTransferLedgerReadinessTests(unittest.TestCase):
    def test_empty_ledger_is_cutover_ready(self):
        report = build_ledger_report([], [], [], [])

        self.assertTrue(report["ledgerReady"])
        self.assertEqual(report["issueCount"], 0)
        self.assertEqual(report["summary"]["plansTotal"], 0)
        self.assertEqual(report["summary"]["completePlans"], 0)

    def test_pending_and_complete_approved_plans_are_valid_states(self):
        plan, header, entry = approved_fixture()

        pending = build_ledger_report([header], [entry], [], [])
        complete = build_ledger_report(
            [header], [entry], [assignment_receipt(plan)], []
        )

        self.assertTrue(pending["ledgerReady"])
        self.assertEqual(pending["plans"][0]["state"], "approved_pending")
        self.assertTrue(pending["plans"][0]["assignmentReadyForApply"])
        self.assertEqual(complete["plans"][0]["state"], "complete")
        self.assertFalse(complete["plans"][0]["assignmentReadyForApply"])

    def test_mixed_plan_allows_one_complete_kind_without_calling_it_partial(self):
        plan, header, assignment, supply = mixed_fixture()

        assignment_done = build_ledger_report(
            [header], [assignment, supply], [assignment_receipt(plan)], []
        )
        complete = build_ledger_report(
            [header], [assignment, supply], [assignment_receipt(plan)],
            [supply_allocation(plan)],
        )

        self.assertTrue(assignment_done["ledgerReady"])
        self.assertEqual(assignment_done["plans"][0]["state"], "assignment_applied")
        self.assertTrue(assignment_done["plans"][0]["supplyReadyForApply"])
        self.assertEqual(complete["plans"][0]["state"], "complete")

    def test_orphan_entry_and_foreign_receipts_are_never_silently_filtered(self):
        plan, _header, entry = approved_fixture()

        report = build_ledger_report(
            [],
            [dict(entry, plan_id=999)],
            [assignment_receipt(plan, plan_id=999)],
            [dict(supply_allocation(mixed_fixture()[0]), plan_id=998)],
        )

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(
            {item["reasonCode"] for item in report["issues"]},
            {
                "entry_plan_missing",
                "assignment_receipt_plan_missing",
                "supply_receipt_plan_missing",
            },
        )

    def test_partial_receipts_and_quantity_mismatch_are_blockers(self):
        plan, header, first_entry = approved_fixture()
        second_entry = deepcopy(first_entry)
        second_entry.update({"id": 9, "source_id": 42, "source_item_key": "source-2"})
        plan_two = deepcopy(plan)
        second_canonical = deepcopy(plan_two["entries"][0])
        second_canonical.update({"sourceId": 42})
        second_canonical["source"]["itemKey"] = "source-2"
        plan_two["entries"].append(second_canonical)
        from backend.features.estimate_row_transfer.plan import calculate_plan_sha256
        plan_two["planSha256"] = calculate_plan_sha256(plan_two)
        header["plan_sha256"] = plan_two["planSha256"]
        header["approved_plan_sha256"] = plan_two["planSha256"]
        first_entry["source_item_key"] = plan_two["entries"][0]["source"]["itemKey"]

        partial = build_ledger_report(
            [header], [first_entry, second_entry],
            [assignment_receipt(plan_two)], [],
        )
        mismatch = build_ledger_report(
            [header], [first_entry, second_entry],
            [
                assignment_receipt(plan_two),
                assignment_receipt(
                    plan_two, id=22, entry_id=9, transfer_quantity=Decimal("999")
                ),
            ], [],
        )

        self.assertFalse(partial["ledgerReady"])
        self.assertIn("assignment_receipts_partial", {
            item["reasonCode"] for item in partial["issues"]
        })
        self.assertFalse(mismatch["ledgerReady"])
        self.assertIn("assignment_receipt_quantity_mismatch", {
            item["reasonCode"] for item in mismatch["issues"]
        })

    def test_receipt_coordinate_and_balance_evidence_mismatch_are_blockers(self):
        plan, header, assignment, supply = mixed_fixture()

        report = build_ledger_report(
            [header],
            [assignment, supply],
            [assignment_receipt(plan, target_item_index=999)],
            [supply_allocation(plan, remaining_unallocated_quantity=Decimal("999"))],
        )

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(
            {item["reasonCode"] for item in report["issues"]},
            {
                "assignment_receipt_evidence_mismatch",
                "supply_receipt_evidence_mismatch",
            },
        )

    def test_plan_hash_drift_and_issue_preview_are_bounded(self):
        plan, header, entry = approved_fixture()
        header["plan_sha256"] = "0" * 64
        header["approved_plan_sha256"] = "0" * 64
        entries = [dict(entry, id=index + 1, plan_id=5, source_id=index + 100,
                        company_id=999)
                   for index in range(5)]

        report = build_ledger_report([header], entries, [], [], max_issues=2)

        self.assertFalse(report["ledgerReady"])
        self.assertGreater(report["issueCount"], len(report["issues"]))
        self.assertEqual(len(report["issues"]), 2)
        self.assertTrue(report["issuesTruncated"])
        self.assertIn("plan_hash_mismatch", {
            item["reasonCode"] for item in report["issues"]
        })

    def test_exact_scope_requires_positive_id_and_matching_lowercase_hash(self):
        plan, header, entry = approved_fixture()

        with self.assertRaisesRegex(ValueError, "cutover_scope_invalid"):
            normalize_cutover_scope(5, None)
        with self.assertRaisesRegex(ValueError, "cutover_scope_invalid"):
            normalize_cutover_scope(True, plan["planSha256"])
        exact = build_ledger_report(
            [header], [entry], [], [],
            expected_plan_id=5,
            expected_plan_sha256=plan["planSha256"],
        )
        wrong = build_ledger_report(
            [header], [entry], [], [],
            expected_plan_id=5,
            expected_plan_sha256="0" * 64,
        )

        self.assertTrue(exact["exactPlanReady"])
        self.assertFalse(wrong["exactPlanReady"])
        self.assertIn("expected_plan_hash_mismatch", {
            item["reasonCode"] for item in wrong["issues"]
        })

    def test_approval_metadata_must_match_the_plan_status(self):
        plan, header, entry = approved_fixture()
        invalid_approved = dict(header, approved_by_name=None)
        invalid_draft = header_row(plan, approved_by_role="директор")

        approved_report = build_ledger_report(
            [invalid_approved], [entry], [], []
        )
        draft_report = build_ledger_report([invalid_draft], [entry], [], [])

        self.assertIn("approved_metadata_invalid", {
            item["reasonCode"] for item in approved_report["issues"]
        })
        self.assertIn("draft_approval_residue", {
            item["reasonCode"] for item in draft_report["issues"]
        })


class FakeConnection:
    def __init__(self):
        self.session = None
        self.rollbacks = 0
        self.closed = False
        self.cursor_value = object()

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class EstimateRowTransferReadinessRunnerTests(unittest.TestCase):
    def test_global_collection_fails_closed_before_unbounded_ledger_fetch(self):
        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params=None):
                self.calls.append((" ".join(sql.split()), params))

            def fetchall(self):
                return [{"id": index + 1} for index in range(MAX_SCAN_PLANS + 1)]

        cursor = Cursor()

        report = collect_ledger_readiness(cursor)

        self.assertFalse(report["ledgerReady"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "ledger_scan_limit_exceeded",
        }])
        self.assertEqual(len(cursor.calls), 1)
        self.assertIn("LIMIT %s", cursor.calls[0][0])

    def test_runner_is_read_only_repeatable_read_and_always_rolls_back(self):
        connection = FakeConnection()
        schema = {"schemaReady": True, "changes": [], "blockers": []}
        ledger = {"ledgerReady": True, "issueCount": 0}
        inventory = {"ok": True}

        report = run_readiness_report(
            lambda: connection,
            collect_schema=lambda _cur: schema,
            collect_ledger=lambda _cur, **_scope: ledger,
            collect_inventory=lambda: inventory,
        )

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)
        self.assertTrue(report["readyForCutover"])
        self.assertTrue(report["dryRun"])
        self.assertTrue(report["readOnlyTransaction"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["rolledBack"])


if __name__ == "__main__":
    unittest.main()
