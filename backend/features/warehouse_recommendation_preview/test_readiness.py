import ast
import copy
import json
import unittest
from collections import Counter
from pathlib import Path

import backend.features.warehouse_recommendation_preview as preview_package
from backend.features.estimate_revision_impact.combined_contract import (
    PREVIEW_LIMIT,
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    _empty_projection,
)
from backend.features.estimate_revision_impact.supply_warehouse_projection import (
    build_supply_warehouse_projection,
)
from backend.features.estimate_revision_impact.test_combined_report import (
    combined,
)
from backend.features.estimate_revision_impact.test_supply_warehouse_projection import (
    context,
    delivery_row,
    history_row,
    movement_row,
    request_row,
    warehouse_invoice_row,
)
from backend.features.warehouse_recommendation_preview.readiness import (
    WAREHOUSE_ANOMALY_READINESS_VERSION,
    WarehouseAnomalyReadinessError,
    build_warehouse_anomaly_readiness,
)


CANDIDATE_CASES = (
    (
        "warehouse_invoice_request_mismatch",
        "warehouseInvoice",
        "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    (
        "warehouse_invoice_project_mismatch",
        "warehouseInvoice",
        "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    (
        "warehouse_invoice_delivery_mismatch",
        "warehouseInvoice",
        "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    (
        "warehouse_invoice_supplier_invoice_mismatch",
        "warehouseInvoice",
        "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    (
        "warehouse_invoice_items_invalid",
        "warehouseInvoice",
        "warehouseInvoice",
        "review_warehouse_invoice_items",
    ),
    (
        "warehouse_receipt_invoice_mismatch",
        None,
        "warehouseHistory",
        "review_warehouse_receipt_lineage",
    ),
    (
        "warehouse_receipt_line_invalid",
        None,
        "warehouseHistory",
        "review_warehouse_receipt_lineage",
    ),
    (
        "warehouse_receipt_package_mismatch",
        None,
        "warehouseHistory",
        "review_warehouse_receipt_lineage",
    ),
    (
        "warehouse_receipt_lot_invoice_mismatch",
        None,
        "receiptLot",
        "review_receipt_lot_lineage",
    ),
    (
        "warehouse_receipt_lot_line_invalid",
        None,
        "receiptLot",
        "review_receipt_lot_lineage",
    ),
    (
        "warehouse_receipt_lot_project_mismatch",
        None,
        "receiptLot",
        "review_receipt_lot_lineage",
    ),
    (
        "warehouse_movement_invoice_mismatch",
        None,
        "warehouseMovement",
        "review_warehouse_movement_lineage",
    ),
    (
        "warehouse_movement_line_invalid",
        None,
        "warehouseMovement",
        "review_warehouse_movement_lineage",
    ),
    (
        "warehouse_movement_package_mismatch",
        None,
        "warehouseMovement",
        "review_warehouse_movement_lineage",
    ),
    (
        "warehouse_movement_lot_missing",
        "warehouseMovement",
        "warehouseMovement",
        "review_warehouse_movement_traceability",
    ),
    (
        "warehouse_lot_movement_missing",
        "warehouseMovement",
        "warehouseMovement",
        "review_warehouse_movement_traceability",
    ),
    (
        "warehouse_lot_movement_parent_mismatch",
        "lotMovement",
        "lotMovement",
        "review_lot_movement_lineage",
    ),
    (
        "warehouse_lot_movement_source_mismatch",
        "lotMovement",
        "lotMovement",
        "review_lot_movement_lineage",
    ),
)


def stored_report():
    report = combined()
    report["readOnlyTransaction"] = True
    report["rolledBack"] = True
    return report


def rehash(report):
    report["evidenceSha256"] = calculate_evidence_sha256(report)
    return report


def refresh_envelope(report):
    reasons = Counter()
    for domain in report["domainOrder"]:
        reasons.update(report["domains"][domain]["reasonCounts"])
    report["reasonCounts"] = dict(sorted(reasons.items()))
    report["complete"] = all(
        report["domains"][domain]["complete"]
        for domain in report["domainOrder"]
    )
    report["actionable"] = bool(
        report["complete"]
        and report["domains"]["economics"]["actionable"]
    )
    return rehash(report)


def review(reason_code, source_id=31, source_kind=None):
    item = {"reasonCode": reason_code, "sourceId": source_id}
    if source_kind is not None:
        item["sourceKind"] = source_kind
    return item


def candidate_review(reason_code, source_id=31):
    case = next(item for item in CANDIDATE_CASES if item[0] == reason_code)
    return review(reason_code, source_id, case[1])


def warehouse_report(*reviews, reason_counts=None):
    report = stored_report()
    warehouse = report["domains"]["warehouse"]
    warehouse["state"] = "review_required"
    warehouse["complete"] = False
    warehouse["needsReview"] = [copy.deepcopy(item) for item in reviews]
    if reason_counts is None:
        reason_counts = Counter(item["reasonCode"] for item in reviews)
    warehouse["reasonCounts"] = dict(sorted(reason_counts.items()))
    warehouse["summary"]["needsReview"] = sum(reason_counts.values())
    return refresh_envelope(report)


def systemic_report(reason_code):
    report = stored_report()
    supply = report["domains"]["supply"]
    supply.update({
        "state": "review_required",
        "complete": False,
        "reasonCounts": {reason_code: 1},
        "needsReview": [review(
            reason_code, source_id=None, source_kind="supplyWarehouse",
        )],
    })
    supply["summary"]["needsReview"] = 1

    warehouse = report["domains"]["warehouse"]
    warehouse.update({
        "state": "review_required",
        "complete": False,
        "reasonCounts": {reason_code: 1},
        "needsReview": [],
    })
    warehouse["summary"]["needsReview"] = 1
    return refresh_envelope(report)


class WarehouseAnomalyReadinessTests(unittest.TestCase):
    maxDiff = None

    def assert_blocked(self, result, *blockers):
        self.assertEqual(result["state"], "blocked")
        self.assertFalse(result["classificationComplete"])
        self.assertFalse(result["readyForRecommendationPreview"])
        self.assertEqual(result["candidateCount"], 0)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["blockers"], sorted(set(blockers)))
        self.assertTrue(result["previewOnly"])
        self.assertFalse(result["stockMovementAllowed"])
        self.assertFalse(result["inventoryAdjustmentAllowed"])
        self.assertFalse(result["applyAllowed"])

    def assert_contract_error(self, report, code):
        with self.assertRaises(WarehouseAnomalyReadinessError) as error:
            build_warehouse_anomaly_readiness(report)
        self.assertEqual(error.exception.code, code)
        self.assertEqual(str(error.exception), code)
        self.assertNotIn("must-not-leak", str(error.exception))

    def test_public_api_and_clear_snapshot_result_are_exact(self):
        report = stored_report()

        result = build_warehouse_anomaly_readiness(report)

        self.assertEqual(WAREHOUSE_ANOMALY_READINESS_VERSION, 1)
        self.assertEqual(set(preview_package.__all__), {
            "WAREHOUSE_ANOMALY_READINESS_VERSION",
            "WarehouseAnomalyReadinessError",
            "build_warehouse_anomaly_readiness",
        })
        self.assertEqual(result, {
            "warehouseAnomalyReadinessVersion": 1,
            "ok": True,
            "dryRun": True,
            "writesAttempted": 0,
            "previewOnly": True,
            "stockMovementAllowed": False,
            "inventoryAdjustmentAllowed": False,
            "applyAllowed": False,
            "state": "clear",
            "source": {
                "companyId": 4,
                "projectId": 17,
                "estimateId": 52,
                "sourceRevision": report["source"]["sourceRevision"],
                "reconciliationId": 91,
                "baseEstimateId": 51,
                "impactEvidenceSha256": report["evidenceSha256"],
            },
            "classificationComplete": True,
            "readyForRecommendationPreview": False,
            "candidateCount": 0,
            "candidates": [],
            "blockers": [],
        })

    def test_maps_every_exact_allowlisted_reason_and_source_shape(self):
        for index, (
            reason_code,
            source_kind,
            subject_kind,
            recommendation_code,
        ) in enumerate(CANDIDATE_CASES, start=1):
            with self.subTest(reason_code=reason_code):
                report = warehouse_report(
                    review(reason_code, 100 + index, source_kind),
                )

                result = build_warehouse_anomaly_readiness(report)

                self.assertEqual(result["state"], "ready")
                self.assertTrue(result["classificationComplete"])
                self.assertTrue(result["readyForRecommendationPreview"])
                self.assertEqual(result["candidateCount"], 1)
                self.assertEqual(result["blockers"], [])
                self.assertEqual(result["candidates"], [{
                    "subjectKind": subject_kind,
                    "subjectId": 100 + index,
                    "anomalyCode": reason_code,
                    "recommendationCode": recommendation_code,
                }])

    def test_accepts_actual_a7_candidate_and_systemic_producer_shapes(self):
        projection = build_supply_warehouse_projection(
            context(),
            [request_row()],
            [delivery_row()],
            [],
            [],
            [warehouse_invoice_row(supplier_invoice_id=None)],
            [history_row(source_invoice_line_index=4)],
            [],
            [movement_row()],
            [],
        )
        report = combined(supply_warehouse=projection)
        report.update({"readOnlyTransaction": True, "rolledBack": True})

        result = build_warehouse_anomaly_readiness(report)

        self.assertEqual(result["state"], "ready")
        self.assertEqual(
            [item["anomalyCode"] for item in result["candidates"]],
            [
                "warehouse_receipt_line_invalid",
                "warehouse_movement_lot_missing",
            ],
        )

        systemic_cases = (
            (
                "supply_warehouse_impact_schema_not_ready",
                "incomplete",
                False,
                ["warehouse_main.id"],
            ),
            (
                "supply_warehouse_project_identity_invalid",
                "review_required",
                True,
                [],
            ),
            (
                "supply_warehouse_scan_limit_exceeded",
                "incomplete",
                True,
                [],
            ),
            (
                "supply_warehouse_source_snapshot_invalid",
                "review_required",
                True,
                [],
            ),
        )
        for reason_code, state, schema_ready, missing in systemic_cases:
            with self.subTest(reason_code=reason_code):
                systemic_projection = _empty_projection(
                    state,
                    reason_code,
                    schema_ready=schema_ready,
                    missing_columns=missing,
                )
                systemic = combined(
                    supply_warehouse=systemic_projection,
                )
                systemic.update({
                    "readOnlyTransaction": True,
                    "rolledBack": True,
                })
                self.assert_blocked(
                    build_warehouse_anomaly_readiness(systemic),
                    "warehouse_anomaly_systemic_source_incomplete",
                )

    def test_is_deterministic_sorted_id_only_and_does_not_mutate_input(self):
        report = warehouse_report(
            candidate_review("warehouse_movement_lot_missing", 9),
            candidate_review("warehouse_invoice_items_invalid", 4),
            candidate_review("warehouse_receipt_line_invalid", 7),
        )
        before = copy.deepcopy(report)

        first = build_warehouse_anomaly_readiness(report)
        second = build_warehouse_anomaly_readiness(copy.deepcopy(report))

        self.assertEqual(first, second)
        self.assertEqual(report, before)
        self.assertEqual(first["state"], "ready")
        self.assertEqual(first["candidates"], sorted(
            first["candidates"],
            key=lambda item: (
                item["subjectKind"], item["subjectId"], item["anomalyCode"],
            ),
        ))
        self.assertEqual(set(first["candidates"][0]), {
            "subjectKind", "subjectId", "anomalyCode", "recommendationCode",
        })
        serialized = json.dumps(first, ensure_ascii=False)
        for forbidden in (
            "materialName", "projectName", "quantity", "price", "unit",
            "supplier", "notes", "actor", "session",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_unrelated_domain_readiness_does_not_gate_warehouse(self):
        report = warehouse_report(
            candidate_review("warehouse_invoice_request_mismatch", 31),
        )
        for name in ("assignments", "materials", "economics"):
            report["domains"][name]["state"] = "incomplete"
            report["domains"][name]["complete"] = False
        refresh_envelope(report)

        result = build_warehouse_anomaly_readiness(report)

        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["candidateCount"], 1)

    def test_exact_non_candidates_and_unknown_reason_block_whole_result(self):
        cases = (
            (
                review(
                    "warehouse_invoice_owner_mismatch",
                    source_id=None,
                    source_kind="warehouseInvoice",
                ),
                "warehouse_anomaly_subject_invalid",
            ),
            (
                review(
                    "warehouse_invoice_identity_invalid",
                    source_id=31,
                    source_kind="warehouseInvoice",
                ),
                "warehouse_anomaly_subject_invalid",
            ),
            (
                review(
                    "warehouse_invoice_items_limit_exceeded",
                    source_id=31,
                    source_kind="warehouseInvoice",
                ),
                "warehouse_anomaly_source_items_limit_exceeded",
            ),
            (
                review("warehouse_invoice_future_suffix", source_id=31),
                "warehouse_anomaly_reason_unsupported",
            ),
        )
        for item, blocker in cases:
            with self.subTest(reason_code=item["reasonCode"]):
                result = build_warehouse_anomaly_readiness(
                    warehouse_report(item),
                )
                self.assert_blocked(result, blocker)
                serialized = json.dumps(result)
                self.assertNotIn("subjectId", serialized)
                self.assertNotIn("sourceId", serialized)

    def test_candidate_identity_and_exact_source_kind_fail_closed(self):
        null_id = warehouse_report(candidate_review(
            "warehouse_invoice_request_mismatch", source_id=None,
        ))
        wrong_kind = warehouse_report(review(
            "warehouse_invoice_request_mismatch",
            source_id=31,
            source_kind="warehouseMovement",
        ))

        self.assert_blocked(
            build_warehouse_anomaly_readiness(null_id),
            "warehouse_anomaly_subject_invalid",
        )
        self.assert_blocked(
            build_warehouse_anomaly_readiness(wrong_kind),
            "warehouse_anomaly_subject_invalid",
        )

        missing_kind = warehouse_report(review(
            "warehouse_invoice_request_mismatch", source_id=31,
        ))
        injected_kind = warehouse_report(review(
            "warehouse_receipt_line_invalid",
            source_id=31,
            source_kind="warehouseHistory",
        ))
        self.assert_contract_error(
            missing_kind, "warehouse_anomaly_relevant_domain_invalid",
        )
        self.assert_contract_error(
            injected_kind, "warehouse_anomaly_relevant_domain_invalid",
        )

    def test_exact_duplicate_blocks_but_distinct_codes_for_subject_are_allowed(self):
        duplicate = candidate_review(
            "warehouse_invoice_request_mismatch", 31,
        )
        duplicate_result = build_warehouse_anomaly_readiness(
            warehouse_report(duplicate, copy.deepcopy(duplicate)),
        )
        self.assert_blocked(
            duplicate_result, "warehouse_anomaly_duplicate_candidate",
        )

        distinct_result = build_warehouse_anomaly_readiness(warehouse_report(
            candidate_review("warehouse_invoice_request_mismatch", 31),
            candidate_review("warehouse_invoice_project_mismatch", 31),
        ))
        self.assertEqual(distinct_result["state"], "ready")
        self.assertEqual(distinct_result["candidateCount"], 2)
        self.assertEqual(
            [item["anomalyCode"] for item in distinct_result["candidates"]],
            [
                "warehouse_invoice_project_mismatch",
                "warehouse_invoice_request_mismatch",
            ],
        )

    def test_supply_not_ready_blocks_without_partial_candidates(self):
        report = warehouse_report(
            candidate_review("warehouse_invoice_request_mismatch", 31),
        )
        supply = report["domains"]["supply"]
        supply.update({
            "state": "review_required",
            "complete": False,
            "reasonCounts": {"supply_quantity_invalid": 1},
            "needsReview": [review(
                "supply_quantity_invalid", 21, "supply",
            )],
        })
        supply["summary"]["needsReview"] = 1
        refresh_envelope(report)

        self.assert_blocked(
            build_warehouse_anomaly_readiness(report),
            "warehouse_anomaly_supply_not_ready",
        )

    def test_each_incomplete_supply_gate_blocks_without_partial_candidates(self):
        cases = {
            "scan": {"scanComplete": False},
            "facts": {"factsTruncated": True},
            "reviews": {"needsReviewTruncated": True},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                report = warehouse_report(candidate_review(
                    "warehouse_invoice_request_mismatch", 31,
                ))
                report["domains"]["supply"].update({
                    "state": "incomplete",
                    "complete": False,
                    **changes,
                })
                refresh_envelope(report)

                self.assert_blocked(
                    build_warehouse_anomaly_readiness(report),
                    "warehouse_anomaly_supply_not_ready",
                )

    def test_warehouse_completeness_flags_have_fixed_blockers(self):
        cases = {
            "schema": (
                {"schemaReady": False, "missingColumns": ["x.y"]},
                "warehouse_anomaly_schema_not_ready",
            ),
            "scan": (
                {"scanComplete": False},
                "warehouse_anomaly_scan_incomplete",
            ),
            "facts": (
                {"factsTruncated": True},
                "warehouse_anomaly_facts_truncated",
            ),
            "reviews": (
                {"needsReviewTruncated": True},
                "warehouse_anomaly_reviews_truncated",
            ),
        }
        for name, (changes, blocker) in cases.items():
            with self.subTest(name=name):
                report = stored_report()
                warehouse = report["domains"]["warehouse"]
                warehouse.update({
                    "state": "incomplete", "complete": False, **changes,
                })
                refresh_envelope(report)
                self.assert_blocked(
                    build_warehouse_anomaly_readiness(report), blocker,
                )

    def test_every_exact_systemic_gap_blocks_and_other_count_gaps_are_invalid(self):
        systemic_codes = (
            "supply_warehouse_impact_schema_not_ready",
            "supply_warehouse_project_identity_invalid",
            "supply_warehouse_scan_limit_exceeded",
            "supply_warehouse_source_snapshot_invalid",
        )
        for reason_code in systemic_codes:
            with self.subTest(reason_code=reason_code):
                self.assert_blocked(
                    build_warehouse_anomaly_readiness(
                        systemic_report(reason_code),
                    ),
                    "warehouse_anomaly_systemic_source_incomplete",
                )

        ordinary_gap = warehouse_report(
            reason_counts={"warehouse_invoice_request_mismatch": 1},
        )
        self.assert_contract_error(
            ordinary_gap, "warehouse_anomaly_relevant_domain_invalid",
        )

        malformed_systemic = systemic_report(systemic_codes[0])
        malformed_systemic["domains"]["warehouse"]["reasonCounts"] = {
            systemic_codes[0]: 2,
        }
        malformed_systemic["domains"]["warehouse"]["summary"][
            "needsReview"
        ] = 2
        refresh_envelope(malformed_systemic)
        self.assert_contract_error(
            malformed_systemic, "warehouse_anomaly_relevant_domain_invalid",
        )

    def test_rejects_report_source_evidence_and_relevant_domain_tamper(self):
        invalid_cases = []

        extra_report = stored_report()
        extra_report["privateBusinessText"] = "must-not-leak"
        invalid_cases.append((
            extra_report, "warehouse_anomaly_report_invalid",
        ))

        for invalid_version in (True, 1.0):
            bad_version = stored_report()
            bad_version["combinedReportVersion"] = invalid_version
            rehash(bad_version)
            invalid_cases.append((
                bad_version, "warehouse_anomaly_report_invalid",
            ))

        bad_flag = stored_report()
        bad_flag["writesAttempted"] = True
        invalid_cases.append((bad_flag, "warehouse_anomaly_report_invalid"))

        bool_zero = stored_report()
        bool_zero["writesAttempted"] = False
        invalid_cases.append((bool_zero, "warehouse_anomaly_report_invalid"))

        bad_order = stored_report()
        bad_order["domainOrder"] = list(reversed(bad_order["domainOrder"]))
        invalid_cases.append((bad_order, "warehouse_anomaly_report_invalid"))

        false_complete = stored_report()
        false_complete["complete"] = False
        rehash(false_complete)
        invalid_cases.append((
            false_complete, "warehouse_anomaly_report_invalid",
        ))

        false_actionable = stored_report()
        false_actionable["actionable"] = True
        rehash(false_actionable)
        invalid_cases.append((
            false_actionable, "warehouse_anomaly_report_invalid",
        ))

        bad_source = stored_report()
        bad_source["source"]["estimateId"] = True
        rehash(bad_source)
        invalid_cases.append((bad_source, "warehouse_anomaly_source_invalid"))

        supply_source_mismatch = stored_report()
        supply_source_mismatch["domains"]["supply"]["openSupply"][0][
            "sourceEstimateId"
        ] = 999
        rehash(supply_source_mismatch)
        invalid_cases.append((
            supply_source_mismatch, "warehouse_anomaly_source_invalid",
        ))

        source_alias = stored_report()
        source_alias["source"]["baseEstimateId"] = source_alias["source"][
            "estimateId"
        ]
        rehash(source_alias)
        invalid_cases.append((source_alias, "warehouse_anomaly_source_invalid"))

        bad_hash = stored_report()
        bad_hash["evidenceSha256"] = "0" * 64
        invalid_cases.append((bad_hash, "warehouse_anomaly_evidence_invalid"))

        extra_domain = stored_report()
        extra_domain["domains"]["warehouse"]["businessName"] = (
            "must-not-leak"
        )
        rehash(extra_domain)
        invalid_cases.append((
            extra_domain, "warehouse_anomaly_relevant_domain_invalid",
        ))

        summary_drift = warehouse_report(candidate_review(
            "warehouse_invoice_request_mismatch", 31,
        ))
        summary_drift["domains"]["warehouse"]["summary"]["needsReview"] = 2
        rehash(summary_drift)
        invalid_cases.append((
            summary_drift, "warehouse_anomaly_relevant_domain_invalid",
        ))

        review_extra = warehouse_report(candidate_review(
            "warehouse_invoice_request_mismatch", 31,
        ))
        review_extra["domains"]["warehouse"]["needsReview"][0][
            "materialName"
        ] = "must-not-leak"
        rehash(review_extra)
        invalid_cases.append((
            review_extra, "warehouse_anomaly_relevant_domain_invalid",
        ))

        incoherent_state = warehouse_report(candidate_review(
            "warehouse_invoice_request_mismatch", 31,
        ))
        incoherent_state["domains"]["warehouse"].update({
            "state": "complete", "complete": True,
        })
        refresh_envelope(incoherent_state)
        invalid_cases.append((
            incoherent_state, "warehouse_anomaly_relevant_domain_invalid",
        ))

        truncated_count_gap = warehouse_report(candidate_review(
            "warehouse_invoice_request_mismatch", 31,
        ))
        truncated_warehouse = truncated_count_gap["domains"]["warehouse"]
        truncated_warehouse.update({
            "state": "incomplete",
            "reasonCounts": {},
            "needsReviewTruncated": True,
        })
        truncated_warehouse["summary"]["needsReview"] = 0
        refresh_envelope(truncated_count_gap)
        invalid_cases.append((
            truncated_count_gap,
            "warehouse_anomaly_relevant_domain_invalid",
        ))

        unsorted_evidence = stored_report()
        unsorted_evidence["domains"]["warehouse"]["protectedEvidence"][
            "warehouseInvoiceIds"
        ] = [2, 1]
        rehash(unsorted_evidence)
        invalid_cases.append((
            unsorted_evidence, "warehouse_anomaly_relevant_domain_invalid",
        ))

        evidence_count_drift = stored_report()
        evidence_count_drift["domains"]["warehouse"]["summary"][
            "warehouseInvoices"
        ] = 1
        rehash(evidence_count_drift)
        invalid_cases.append((
            evidence_count_drift,
            "warehouse_anomaly_relevant_domain_invalid",
        ))

        for invalid_source_id in (-1, 0, True, "31", {"id": 31}):
            invalid_review_id = warehouse_report(review(
                "warehouse_invoice_request_mismatch",
                source_id=invalid_source_id,
                source_kind="warehouseInvoice",
            ))
            invalid_cases.append((
                invalid_review_id,
                "warehouse_anomaly_relevant_domain_invalid",
            ))

        for report, code in invalid_cases:
            with self.subTest(code=code):
                self.assert_contract_error(report, code)

    def test_rejects_more_than_a7_preview_limit_candidates(self):
        rows = [candidate_review(
            "warehouse_invoice_request_mismatch", source_id + 1,
        ) for source_id in range(PREVIEW_LIMIT + 1)]
        report = warehouse_report(*rows)

        self.assert_contract_error(
            report, "warehouse_anomaly_candidate_limit_exceeded",
        )

    def test_production_module_has_only_pure_allowlisted_dependencies(self):
        module_path = Path(__file__).with_name("readiness.py")
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                self.assertIsNotNone(node.module)
                imported.add(node.module)

        self.assertEqual(imported, {
            "re",
            "collections",
            "collections.abc",
            "types",
            "backend.features.estimate_revision_impact.combined_contract",
            "backend.features.estimate_revision_impact.contract",
        })
        forbidden_import_roots = {
            "psycopg2", "sqlalchemy", "requests", "httpx", "urllib",
            "socket", "openai", "anthropic", "subprocess",
        }
        self.assertTrue(imported.isdisjoint(forbidden_import_roots))
        for forbidden_text in (
            ".execute(", ".commit(", "FOR UPDATE", "INSERT INTO",
            "UPDATE warehouse", "DELETE FROM", "create_task(",
        ):
            self.assertNotIn(forbidden_text, source)


if __name__ == "__main__":
    unittest.main()
