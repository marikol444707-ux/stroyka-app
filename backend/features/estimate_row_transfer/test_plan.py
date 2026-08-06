import copy
import json
import unittest

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.audit import build_impact_report
from backend.features.estimate_row_transfer.plan import (
    PlanValidationError,
    build_reviewed_plan,
    calculate_plan_sha256,
    normalize_draft_payload,
    reviewed_plan_to_draft_payload,
)
from backend.features.estimate_row_transfer.test_audit import (
    _sections,
    assignment_row,
    reconciliation_row,
    supply_reconciliation_row,
    supply_request_row,
)


def assignment_mapping(source_id=41, quantity="3", target_key="new-row"):
    return {
        "sourceKind": "assignment",
        "sourceId": source_id,
        "quantity": quantity,
        "targetSectionIndex": 0,
        "targetItemIndex": 0,
        "targetItemKey": target_key,
    }


def assignment_report(*, mapping=None, row=None):
    selected_mapping = mapping or assignment_mapping()
    report = build_impact_report(
        reconciliation_row(),
        [row or assignment_row()],
        [],
        [],
        [selected_mapping],
    )
    report["targetSnapshot"]["estimateVersionId"] = 72
    return report


def supply_mapping(quantity="3"):
    return {
        "sourceKind": "supply",
        "sourceId": 61,
        "requestItemIndex": 0,
        "sourceEstimateVersionId": 71,
        "quantity": quantity,
        "targetSectionIndex": 0,
        "targetItemIndex": 0,
        "targetItemKey": "new-material",
    }


def supply_report(mapping=None):
    selected = mapping or supply_mapping()
    report = build_impact_report(
        supply_reconciliation_row(),
        [],
        [supply_request_row()],
        [],
        [selected],
    )
    report["targetSnapshot"]["estimateVersionId"] = 72
    return report


class EstimateRowTransferDraftPayloadTests(unittest.TestCase):
    def test_normalizes_strict_assignment_payload(self):
        result = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping(quantity="3.250000")],
        })

        self.assertEqual(result, {
            "reconciliationId": 9,
            "entries": [assignment_mapping(quantity="3.25")],
        })

    def test_rejects_unknown_fields_fractional_ids_and_excess_scale(self):
        invalid_payloads = [
            {"reconciliationId": 9, "entries": [{**assignment_mapping(), "note": "no"}]},
            {"reconciliationId": 9.5, "entries": [assignment_mapping()]},
            {"reconciliationId": 9, "entries": [assignment_mapping(source_id=41.5)]},
            {"reconciliationId": 9, "entries": [assignment_mapping(quantity="0.0000001")]},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(PlanValidationError):
                    normalize_draft_payload(payload)

    def test_rejects_duplicate_assignment_sources(self):
        with self.assertRaisesRegex(PlanValidationError, "mapping_source_duplicate"):
            normalize_draft_payload({
                "reconciliationId": 9,
                "entries": [assignment_mapping(), assignment_mapping(quantity="2")],
            })

    def test_supply_payload_requires_item_and_snapshot_identity(self):
        result = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [supply_mapping()],
        })

        self.assertEqual(result["entries"][0], supply_mapping())


class EstimateRowTransferPlanTests(unittest.TestCase):
    def test_builds_bounded_assignment_plan_without_commercial_content(self):
        normalized = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })

        plan = build_reviewed_plan(assignment_report(), normalized["entries"])

        self.assertEqual(plan["planVersion"], 1)
        self.assertEqual(plan["companyId"], 1)
        self.assertEqual(plan["projectId"], 3)
        self.assertEqual(plan["reconciliationId"], 9)
        self.assertEqual(plan["baseSnapshot"]["sectionsSha256"], sections_sha256(_sections("old-row")))
        self.assertEqual(plan["targetSnapshot"]["sectionsSha256"], sections_sha256(_sections("new-row")))
        self.assertEqual(plan["entries"][0]["sourceTotalQuantity"], "10")
        self.assertEqual(plan["entries"][0]["sourceProtectedQuantity"], "4")
        self.assertEqual(plan["entries"][0]["sourceAvailableQuantity"], "6")
        self.assertEqual(plan["entries"][0]["quantity"], "3")
        self.assertEqual(plan["entries"][0]["target"]["estimateVersionId"], 72)
        self.assertRegex(plan["planSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(calculate_plan_sha256(plan), plan["planSha256"])
        self.assertEqual(
            reviewed_plan_to_draft_payload(plan),
            {"reconciliationId": 9, "entries": [assignment_mapping()]},
        )
        serialized = json.dumps(plan, ensure_ascii=False)
        self.assertNotIn("must-not-leak", serialized)
        self.assertNotIn("price", serialized.lower())

    def test_hash_changes_when_authoritative_balance_drifts(self):
        entries = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })["entries"]
        original = build_reviewed_plan(assignment_report(), entries)
        drifted_row = assignment_row(confirmed_quantity=5)
        drifted = build_reviewed_plan(assignment_report(row=drifted_row), entries)

        self.assertNotEqual(original["planSha256"], drifted["planSha256"])

    def test_rejects_quantity_above_current_available_balance(self):
        mapping = assignment_mapping(quantity="7")
        entries = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [mapping],
        })["entries"]

        with self.assertRaisesRegex(PlanValidationError, "mapping_quantity_exceeds_available"):
            build_reviewed_plan(assignment_report(mapping=mapping), entries)

    def test_unselected_blocked_source_does_not_poison_exact_selected_entry(self):
        mapping = assignment_mapping()
        report = build_impact_report(
            reconciliation_row(),
            [assignment_row(), assignment_row(contract_item_id=42, source_type="manual")],
            [],
            [],
            [mapping],
        )
        report["targetSnapshot"]["estimateVersionId"] = 72
        entries = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [mapping],
        })["entries"]

        plan = build_reviewed_plan(report, entries)

        self.assertEqual([entry["sourceId"] for entry in plan["entries"]], [41])

    def test_hash_is_independent_of_client_entry_order(self):
        mappings = [assignment_mapping(41, "3"), assignment_mapping(42, "2")]
        report = build_impact_report(
            reconciliation_row(),
            [assignment_row(), assignment_row(contract_item_id=42)],
            [],
            [],
            mappings,
        )
        report["targetSnapshot"]["estimateVersionId"] = 72
        first = normalize_draft_payload({"reconciliationId": 9, "entries": mappings})["entries"]
        second = list(reversed(copy.deepcopy(first)))

        self.assertEqual(
            build_reviewed_plan(report, first)["planSha256"],
            build_reviewed_plan(report, second)["planSha256"],
        )

    def test_builds_supply_plan_only_with_exact_current_base_snapshot(self):
        entries = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [supply_mapping()],
        })["entries"]
        report = supply_report()
        source_hash = sections_sha256(_sections("old-material", name="Смесь", unit="кг"))
        snapshots = {(61, 0, 71): {
            "estimateId": 14,
            "estimateVersionId": 71,
            "sectionIndex": 0,
            "itemIndex": 0,
            "itemKey": "old-material",
            "sectionsSha256": source_hash,
        }}

        plan = build_reviewed_plan(report, entries, snapshots)

        self.assertEqual(plan["entries"][0]["source"]["estimateVersionId"], 71)
        self.assertEqual(plan["entries"][0]["requestItemIndex"], 0)
        self.assertEqual(plan["entries"][0]["sourceProtectedQuantity"], "0")

    def test_rejects_invalid_authoritative_context(self):
        report = assignment_report()
        report["reconciliation"]["companyId"] = None
        entries = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })["entries"]

        with self.assertRaisesRegex(PlanValidationError, "impact_context_invalid"):
            build_reviewed_plan(report, entries)

    def test_rejects_target_snapshot_without_immutable_version_id(self):
        report = assignment_report()
        report["targetSnapshot"].pop("estimateVersionId")
        entries = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })["entries"]

        with self.assertRaisesRegex(PlanValidationError, "impact_context_invalid"):
            build_reviewed_plan(report, entries)


if __name__ == "__main__":
    unittest.main()
