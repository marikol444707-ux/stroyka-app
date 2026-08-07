import json
import math
import unittest

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.audit import (
    PREVIEW_LIMIT,
    build_impact_report,
    classify_target_mapping,
    parse_reconciliation_id,
    run_impact_audit,
)


def _sections(item_key, *, name="Работа", unit="м2", quantity=10, item_type=None):
    item = {
        "name": name,
        "unit": unit,
        "quantity": quantity,
        "estimateItemKey": item_key,
        "priceWork": 900,
        "commercialNote": "must-not-leak",
    }
    if item_type is not None:
        item["itemType"] = item_type
    return [{
        "name": "Раздел",
        "items": [item],
    }]


def reconciliation_row(**overrides):
    base_sections = _sections("old-row")
    target_sections = _sections("new-row")
    row = {
        "reconciliation_exists": True,
        "reconciliation_id": 9,
        "reconciliation_status": "Утверждена",
        "reconciliation_work_package": "Отделка",
        "reconciliation_smeta_type": "Заказчик",
        "project_exists": True,
        "project_id": 3,
        "project_company_id": 1,
        "base_estimate_id": 14,
        "base_company_id": 1,
        "base_project_id": 3,
        "base_work_package": "Отделка",
        "base_smeta_type": "Заказчик",
        "base_sections_json": json.dumps(base_sections, ensure_ascii=False),
        "target_estimate_id": 15,
        "target_company_id": 1,
        "target_project_id": 3,
        "target_work_package": "Отделка",
        "target_smeta_type": "Заказчик",
        "target_sections_json": json.dumps(target_sections, ensure_ascii=False),
    }
    row.update(overrides)
    return row


def assignment_row(**overrides):
    sections = _sections("old-row")
    row = {
        "contract_item_id": 41,
        "contract_id": 7,
        "contract_company_id": 1,
        "contract_project_id": 3,
        "contract_work_package": "Отделка",
        "source_type": "estimate",
        "source_estimate_id": 14,
        "source_estimate_version_id": 71,
        "source_section_index": 0,
        "source_item_index": 0,
        "source_item_key": "old-row",
        "snapshot_sections_json": json.dumps(sections, ensure_ascii=False),
        "snapshot_sections_sha256": sections_sha256(sections),
        "assignment_quantity": 10,
        "confirmed_quantity": 4,
        "journal_count": 3,
        "confirmed_journal_count": 2,
        "hidden_act_count": 1,
        "brigade_act_count": 1,
        "brigade_payment_count": 2,
        "description": "must-not-leak",
        "price_smeta": 900,
        "price_brigade": 700,
    }
    row.update(overrides)
    return row


def supply_request_row(**overrides):
    items = [{
        "materialName": "Смесь",
        "quantity": 10,
        "unit": "кг",
        "workPackage": "Отделка",
        "sourceType": "estimate_material_control",
        "estimateLineage": {
            "version": 1,
            "validated": True,
            "projectName": "Школа",
            "workPackage": "Отделка",
            "sources": [{
                "estimateId": 14,
                "sectionIndex": 0,
                "itemIndex": 0,
                "materialName": "Смесь",
                "unit": "кг",
                "quantity": 10,
                "validated": True,
            }],
        },
        "notes": "must-not-leak",
    }]
    row = {
        "request_id": 61,
        "request_company_id": 1,
        "request_project": "Школа",
        "request_status": "КП запрошены",
        "request_work_package": "Отделка",
        "items_json": json.dumps(items, ensure_ascii=False),
        "offer_count": 2,
        "supplier_invoice_count": 1,
        "warehouse_invoice_count": 1,
        "warehouse_history_count": 3,
        "supply_history_count": 2,
        "claim_count": 1,
        "paid_invoice_count": 1,
    }
    row.update(overrides)
    return row


def supply_reconciliation_row(**overrides):
    row = reconciliation_row(
        project_name="Школа",
        project_name_owner_count=1,
        reconciliation_smeta_type="Материалы",
        base_smeta_type="Материалы",
        target_smeta_type="Материалы",
        base_sections_json=json.dumps(_sections(
            "old-material", name="Смесь", unit="кг", item_type="material"
        ), ensure_ascii=False),
        target_sections_json=json.dumps(_sections(
            "new-material", name="Смесь", unit="кг", item_type="material"
        ), ensure_ascii=False),
    )
    row.update(overrides)
    return row


class EstimateRowTransferPureAuditTests(unittest.TestCase):
    def test_exact_assignment_reports_only_transferable_balance_and_counts(self):
        report = build_impact_report(reconciliation_row(), [assignment_row()], [], [])

        self.assertTrue(report["ok"])
        self.assertFalse(report["readyForMapping"])
        self.assertEqual(report["summary"]["assignmentCandidates"], 1)
        self.assertEqual(report["assignmentCandidates"][0]["transferableQuantity"], 6.0)
        self.assertEqual(report["assignmentCandidates"][0]["confirmedQuantity"], 4.0)
        self.assertEqual(report["assignmentCandidates"][0]["protectedHistoryCounts"], {
            "journalRows": 3,
            "confirmedJournalRows": 2,
            "hiddenActs": 1,
            "brigadeActs": 1,
            "brigadePayments": 2,
        })
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("must-not-leak", serialized)
        self.assertNotIn("price_smeta", serialized)
        self.assertNotIn("price_brigade", serialized)

    def test_assignment_rejects_overcompleted_and_non_finite_balances(self):
        rows = [
            assignment_row(contract_item_id=41, confirmed_quantity=11),
            assignment_row(contract_item_id=42, assignment_quantity=math.inf),
        ]

        report = build_impact_report(reconciliation_row(), rows, [], [])

        self.assertEqual(report["summary"]["assignmentCandidates"], 0)
        self.assertEqual(report["reasonCounts"], {
            "assignment_quantity_non_finite": 1,
            "confirmed_quantity_exceeds_assignment": 1,
            "exact_target_mapping_required": 1,
        })

    def test_assignment_rejects_stale_snapshot_hash(self):
        report = build_impact_report(
            reconciliation_row(),
            [assignment_row(snapshot_sections_sha256="0" * 64)],
            [],
            [],
        )

        self.assertEqual(report["needsReview"][0]["reasonCode"], "source_snapshot_hash_mismatch")

    def test_cross_owner_reconciliation_blocks_before_candidates_are_used(self):
        report = build_impact_report(
            reconciliation_row(target_company_id=2),
            [assignment_row()],
            [],
            [],
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["reasonCounts"], {"reconciliation_owner_mismatch": 1})
        self.assertEqual(report["assignmentCandidates"], [])

    def test_no_descriptive_reconciliation_mapping_is_inferred(self):
        report = build_impact_report(reconciliation_row(), [assignment_row()], [], [])

        self.assertEqual(report["reasonCounts"]["exact_target_mapping_required"], 1)
        self.assertEqual(report["targetSnapshot"], {
            "estimateId": 15,
            "sectionsSha256": sections_sha256(_sections("new-row")),
            "rowCount": 1,
        })

    def test_exact_target_mapping_is_validated_against_current_target_snapshot(self):
        result = classify_target_mapping(
            reconciliation_row(),
            {
                "sourceKind": "assignment",
                "sourceId": 41,
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": "new-row",
                "quantity": 3,
            },
        )

        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["target"], {
            "estimateId": 15,
            "sectionIndex": 0,
            "itemIndex": 0,
            "itemKey": "new-row",
            "sectionsSha256": sections_sha256(_sections("new-row")),
        })

    def test_target_mapping_rejects_fuzzy_or_wrong_key(self):
        result = classify_target_mapping(
            reconciliation_row(),
            {
                "sourceKind": "assignment",
                "sourceId": 41,
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": "similar-name-is-not-identity",
                "quantity": 3,
            },
        )

        self.assertEqual(result, {
            "sourceKind": "assignment",
            "sourceId": 41,
            "state": "blocked",
            "reasonCode": "target_item_key_mismatch",
        })

    def test_target_mapping_rejects_fractional_source_id(self):
        result = classify_target_mapping(
            reconciliation_row(),
            {
                "sourceKind": "assignment",
                "sourceId": 41.5,
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": "new-row",
                "quantity": 3,
            },
        )

        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reasonCode"], "mapping_source_identity_invalid")

    def test_supply_target_must_be_explicit_material_row(self):
        result = classify_target_mapping(
            supply_reconciliation_row(
                target_sections_json=json.dumps(
                    _sections("new-material", name="Смесь", unit="кг"),
                    ensure_ascii=False,
                ),
            ),
            {
                "sourceKind": "supply",
                "sourceId": 61,
                "requestItemIndex": 0,
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": "new-material",
                "quantity": 3,
            },
        )

        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reasonCode"], "target_not_explicit_material")

    def test_open_supply_item_reports_unreceived_balance_but_requires_snapshot_review(self):
        deliveries = [{
            "delivery_id": 81,
            "request_id": 61,
            "delivery_company_id": 1,
            "material_name": "Смесь",
            "unit": "кг",
            "received_quantity": 4,
        }]

        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row()],
            deliveries,
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 1)
        candidate = report["supplyCandidates"][0]
        self.assertEqual(candidate["transferableQuantity"], 6.0)
        self.assertEqual(candidate["receivedQuantity"], 4.0)
        self.assertEqual(candidate["reasonCode"], "supply_source_snapshot_missing")
        self.assertEqual(candidate["protectedHistoryCounts"], {
            "deliveries": 1,
            "offers": 2,
            "supplierInvoices": 1,
            "warehouseInvoices": 1,
            "warehouseHistoryRows": 3,
            "supplyHistoryRows": 2,
            "claims": 1,
            "paidInvoices": 1,
            "allocationReceipts": 0,
        })

    def test_prior_supply_allocations_reduce_only_remaining_open_balance(self):
        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row()],
            [{
                "delivery_id": 81,
                "request_id": 61,
                "delivery_company_id": 1,
                "material_name": "Смесь",
                "unit": "кг",
                "received_quantity": 2,
            }],
            allocation_rows=[{
                "allocation_id": 301,
                "request_id": 61,
                "request_item_index": 0,
                "allocation_company_id": 1,
                "allocation_quantity": 3,
            }],
        )

        candidate = report["supplyCandidates"][0]
        self.assertEqual(candidate["receivedQuantity"], 2.0)
        self.assertEqual(candidate["allocatedQuantity"], 3.0)
        self.assertEqual(candidate["protectedQuantity"], 5.0)
        self.assertEqual(candidate["transferableQuantity"], 5.0)
        self.assertEqual(candidate["protectedHistoryCounts"]["allocationReceipts"], 1)

    def test_ambiguous_supply_delivery_allocation_fails_closed(self):
        items = json.loads(supply_request_row()["items_json"])
        items.append(dict(items[0]))
        request = supply_request_row(items_json=json.dumps(items, ensure_ascii=False))

        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [request],
            [{
                "delivery_id": 81,
                "request_id": 61,
                "delivery_company_id": 1,
                "material_name": "Смесь",
                "unit": "кг",
                "received_quantity": 4,
            }],
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 0)
        self.assertEqual(report["needsReview"][0]["reasonCode"], "supply_delivery_allocation_ambiguous")

    def test_malformed_supply_json_fails_closed_without_echoing_content(self):
        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(items_json='[{"notes":"secret"}')],
            [],
        )

        self.assertEqual(report["needsReview"][0], {
            "sourceKind": "supply",
            "sourceId": 61,
            "reasonCode": "supply_items_json_invalid",
        })
        self.assertNotIn("secret", json.dumps(report))

    def test_closed_supply_request_is_not_a_candidate_or_blocker(self):
        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(request_status="Поставлено")],
            [],
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 0)
        self.assertEqual(report["reasonCounts"], {"exact_target_mapping_required": 1})

    def test_delivery_chain_status_is_blocked_until_projection_can_avoid_double_count(self):
        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(request_status="В пути")],
            [],
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 0)
        self.assertEqual(
            report["needsReview"][0]["reasonCode"],
            "supply_projection_status_unsupported",
        )

    def test_supply_lineage_project_must_match_stored_project(self):
        items = json.loads(supply_request_row()["items_json"])
        items[0]["estimateLineage"]["projectName"] = "Другой объект"

        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(items_json=json.dumps(items, ensure_ascii=False))],
            [],
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 0)
        self.assertEqual(report["needsReview"][0]["reasonCode"], "supply_source_lineage_drift")

    def test_supply_lineage_v2_requires_the_exact_plan_owner(self):
        items = json.loads(supply_request_row()["items_json"])
        items[0]["estimateLineage"].update({
            "version": 2,
            "companyId": 1,
            "projectId": 3,
        })

        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(items_json=json.dumps(items, ensure_ascii=False))],
            [],
        )
        self.assertEqual(report["summary"]["supplyCandidates"], 1)

        items[0]["estimateLineage"]["projectId"] = 4
        tampered = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(items_json=json.dumps(items, ensure_ascii=False))],
            [],
        )
        self.assertEqual(tampered["summary"]["supplyCandidates"], 0)
        self.assertEqual(
            tampered["needsReview"][0]["reasonCode"],
            "supply_source_lineage_drift",
        )

    def test_fractional_supply_source_coordinate_is_rejected_not_truncated(self):
        items = json.loads(supply_request_row()["items_json"])
        items[0]["estimateLineage"]["sources"][0]["sectionIndex"] = 0.5

        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(items_json=json.dumps(items, ensure_ascii=False))],
            [],
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 0)
        self.assertEqual(report["needsReview"][0]["reasonCode"], "supply_source_coordinate_invalid")

    def test_duplicate_supply_source_coordinate_is_blocked_without_deliveries(self):
        items = json.loads(supply_request_row()["items_json"])
        items.append(dict(items[0]))

        report = build_impact_report(
            supply_reconciliation_row(),
            [],
            [supply_request_row(items_json=json.dumps(items, ensure_ascii=False))],
            [],
        )

        self.assertEqual(report["summary"]["supplyCandidates"], 0)
        self.assertEqual(report["needsReview"][0]["reasonCode"], "supply_source_coordinate_duplicate")

    def test_preview_is_bounded_and_count_is_not_truncated(self):
        rows = [
            assignment_row(
                contract_item_id=index + 1,
                source_type="manual",
            )
            for index in range(PREVIEW_LIMIT + 7)
        ]

        report = build_impact_report(reconciliation_row(), rows, [], [])

        self.assertEqual(report["summary"]["needsReview"], PREVIEW_LIMIT + 8)
        self.assertEqual(len(report["needsReview"]), PREVIEW_LIMIT)
        self.assertTrue(report["needsReviewTruncated"])


class FakeCursor:
    def __init__(self, results, fail_at=None):
        self.results = list(results)
        self.fail_at = fail_at
        self.calls = []
        self.current = None
        self.closed = False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise RuntimeError("database read failed")
        self.current = self.results.pop(0)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.session = None
        self.rollback_count = 0
        self.commit_count = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def rollback(self):
        self.rollback_count += 1

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


class EstimateRowTransferDatabaseBoundaryTests(unittest.TestCase):
    def test_reconciliation_id_parser_is_strict_and_positive(self):
        self.assertEqual(parse_reconciliation_id("17"), 17)
        for value in (None, "", "0", "-1", "1.0", True, " 17 "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "reconciliation_id_invalid"):
                    parse_reconciliation_id(value)

    def test_runner_uses_read_only_repeatable_read_and_always_rolls_back(self):
        cursor = FakeCursor([
            reconciliation_row(project_name="Школа", project_name_owner_count=1),
            [assignment_row()],
            [],
        ])
        connection = FakeConnection(cursor)

        report = run_impact_audit(lambda: connection, 9)

        self.assertTrue(report["rolledBack"])
        self.assertTrue(report["readOnlyTransaction"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollback_count, 1)
        self.assertEqual(connection.commit_count, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

        self.assertTrue(cursor.calls)
        self.assertTrue(all(sql.startswith("SELECT") for sql, _params in cursor.calls))
        self.assertTrue(all(params is not None for _sql, params in cursor.calls))
        self.assertFalse(any("estimate_reconciliation_items" in sql for sql, _params in cursor.calls))
        self.assertTrue(any("COUNT(*)" in sql and "hidden_works_acts" in sql for sql, _ in cursor.calls))

    def test_runner_rolls_back_and_closes_when_a_read_fails(self):
        cursor = FakeCursor(
            [reconciliation_row(project_name="Школа", project_name_owner_count=1)],
            fail_at=2,
        )
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "database read failed"):
            run_impact_audit(lambda: connection, 9)

        self.assertEqual(connection.rollback_count, 1)
        self.assertEqual(connection.commit_count, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_invalid_id_is_rejected_before_database_connection(self):
        calls = []

        with self.assertRaisesRegex(ValueError, "reconciliation_id_invalid"):
            run_impact_audit(lambda: calls.append("connected"), "9 OR 1=1")

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
