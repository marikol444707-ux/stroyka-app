import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    REQUIRED_SCHEMA_ROWS,
    estimate_row as baseline_estimate_row,
    reconciliation_row,
)
from backend.features.estimate_revision_impact.test_supply_warehouse_audit import (
    SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
    _bounded_allocation_row as bounded_collector_allocation_row,
    _bounded_allocation_rows as bounded_collector_allocation_rows,
    _bounded_context_row as bounded_collector_context_row,
    _bounded_delivery_row as bounded_collector_delivery_row,
    _bounded_delivery_rows as bounded_collector_delivery_rows,
    _bounded_history_row as bounded_collector_history_row,
    _bounded_history_rows as bounded_collector_history_rows,
    _bounded_invoice_row as bounded_collector_invoice_row,
    _bounded_invoice_rows as bounded_collector_invoice_rows,
    _bounded_movement_row as bounded_collector_movement_row,
    _bounded_movement_rows as bounded_collector_movement_rows,
    _bounded_request_row as bounded_collector_request_row,
    _bounded_request_rows as bounded_collector_request_rows,
)
from backend.features.estimate_revision_impact.contract import (
    build_source_revision,
)
from backend.features.estimate_revision_impact.supply_warehouse_projection import (
    build_supply_warehouse_projection,
)
from backend.features.supply_recommendation_preview.readiness import (
    build_supply_recommendation_readiness,
)
from backend.features.supply_recommendation_preview.test_readiness import (
    rehash,
    stored_report,
)
from backend.features.supply_recommendation_preview import rfq_content


def material_item(*, quantity="10", name="Private material", **overrides):
    item = {
        "itemType": "material",
        "name": name,
        "unit": "кг",
        "quantity": quantity,
        "estimateItemKey": "material-1",
    }
    item.update(overrides)
    return item


def sections(*, quantity="10", name="Private material", **overrides):
    return [{
        "name": "Private section",
        "items": [material_item(quantity=quantity, name=name, **overrides)],
    }]


def target_sections():
    return sections(quantity="12", name="PRIVATE MATERIAL")


def valid_report():
    report = stored_report()
    report["source"]["sourceRevision"] = build_source_revision(
        "v2.0", target_sections(),
    )
    return rehash(report)


def confirmed_alias_report():
    target = sections(
        quantity="12", name="Canonical material", estimateItemKey=None,
    )
    report = stored_report()
    report["source"]["sourceRevision"] = build_source_revision("v2.0", target)
    pair = report["domains"]["materials"]["changedPairs"][0]
    pair["matchKind"] = "confirmed_alias"
    pair["aliasIds"] = [7]
    pair["changeKinds"] = ["alias_identity_changed", "quantity_changed"]
    return rehash(report)


def request_item(**overrides):
    item = {
        "sourceType": "estimate_material_control",
        "materialName": "Private material",
        "unit": "кг",
        "quantity": "10",
        "workPackage": "Основная",
        "estimateLineage": {
            "version": 2,
            "companyId": 4,
            "projectId": 17,
            "projectName": "Private project",
            "workPackage": "Основная",
            "validated": True,
            "sources": [{
                "estimateId": 51,
                "sectionIndex": 0,
                "itemIndex": 0,
                "materialName": "Private material",
                "unit": "кг",
                "validated": True,
            }],
        },
        "privateNote": "must-not-leak",
    }
    item.update(overrides)
    return item


def confirmed_alias_request_item():
    item = request_item(materialName="Old material")
    item["estimateLineage"]["sources"][0]["materialName"] = "Old material"
    return item


def project_row(**overrides):
    row = {
        "project_name": "Private project",
        "same_company_owner_count": 1,
        "global_owner_count": 1,
    }
    row.update(overrides)
    return row


def estimate_row(estimate_id, stored_sections, **overrides):
    encoded = json.dumps(stored_sections, ensure_ascii=False)
    row = {
        "estimate_id": estimate_id,
        "company_id": 4,
        "project_id": 17,
        "work_package": "Основная",
        "sections_json": encoded,
        "sections_bytes": len(encoded.encode("utf-8")),
    }
    row.update(overrides)
    return row


def request_row(*, items=None, **overrides):
    encoded = json.dumps(
        [request_item()] if items is None else items,
        ensure_ascii=False,
    )
    row = {
        "request_id": 21,
        "request_company_id": 4,
        "request_project": "Private project",
        "request_work_package": "Основная",
        "request_status": "Утверждена",
        "items_json": encoded,
        "items_bytes": len(encoded.encode("utf-8")),
    }
    row.update(overrides)
    return row


def delivery_row(**overrides):
    row = {
        "delivery_id": 31,
        "request_id": 21,
        "delivery_company_id": 4,
        "delivery_project": "Private project",
        "delivery_work_package": "Основная",
        "material_name": "Private material",
        "unit": "кг",
        "received_quantity": "3",
    }
    row.update(overrides)
    return row


def allocation_row(**overrides):
    row = {
        "allocation_id": 41,
        "request_id": 21,
        "request_item_index": 0,
        "allocation_company_id": 4,
        "source_estimate_id": 51,
        "source_section_index": 0,
        "source_item_index": 0,
        "allocation_quantity": "2",
    }
    row.update(overrides)
    return row


def baseline_report(report=None, **overrides):
    report = report or valid_report()
    value = {
        "reportVersion": 1,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": True,
        "sourceReady": True,
        "readyForDomainScan": True,
        "source": copy.deepcopy(report["source"]),
        "summary": {"estimateRows": 1, "reconciliationRows": 1},
        "issueCount": 0,
        "reasonCounts": {},
        "issues": [],
        "issuesTruncated": False,
    }
    value.update(overrides)
    return value


def current_supply_report(report=None, *, projection=None, **overrides):
    report = report or valid_report()
    if projection is None:
        projection = build_supply_warehouse_projection(
            {
                "companyId": 4,
                "projectId": 17,
                "projectName": "Private project",
                "projectNameOwnerCount": 1,
                "baseEstimateId": 51,
                "targetEstimateId": 52,
                "workPackage": "Основная",
                "baseSections": sections(quantity="10"),
            },
            [request_row()],
            [delivery_row()],
            [allocation_row()],
            [], [], [], [], [], [],
        )
    value = baseline_report(report)
    value["readyForSupplyWarehouseProjection"] = bool(
        projection.get("complete")
    )
    value["supplyWarehouseImpact"] = projection
    value.update(overrides)
    return value


def schema_rows():
    return tuple(
        {"table_name": table, "column_name": column}
        for table, columns in rfq_content.RFQ_CONTENT_REQUIRED_COLUMNS.items()
        for column in columns
    )


def valid_result_sets(
    *, schema=None, projects=None, estimates=None, aliases=(), requests=None,
    deliveries=None, allocations=None,
):
    return (
        schema_rows() if schema is None else schema,
        (project_row(),) if projects is None else projects,
        (
            estimate_row(51, sections(quantity="10")),
            estimate_row(52, target_sections()),
        ) if estimates is None else estimates,
        aliases,
        (request_row(),) if requests is None else requests,
        (delivery_row(),) if deliveries is None else deliveries,
        (allocation_row(),) if allocations is None else allocations,
    )


def full_collector_result_sets(
    *, requests=None, deliveries=None, allocations=None, supplier_invoices=(),
    warehouse_invoices=(), history=(), lots=(), movements=(), lot_movements=(),
):
    raw_requests = (request_row(),) if requests is None else requests
    bounded_requests = bounded_collector_request_rows(*(
        bounded_collector_request_row(**{
            key: value
            for key, value in dict(row).items()
            if key != "items_bytes"
        })
        for row in raw_requests
        if isinstance(dict(row).get("items_json"), str)
    ))
    raw_deliveries = (delivery_row(),) if deliveries is None else deliveries
    bounded_deliveries = bounded_collector_delivery_rows(*(
        bounded_collector_delivery_row(**dict(row))
        for row in raw_deliveries
    ))
    raw_allocations = (allocation_row(),) if allocations is None else allocations
    bounded_allocations = bounded_collector_allocation_rows(*(
        bounded_collector_allocation_row(**dict(row))
        for row in raw_allocations
    ))
    bounded_invoices = bounded_collector_invoice_rows(*(
        bounded_collector_invoice_row(**dict(row))
        for row in warehouse_invoices
    ))
    bounded_history = bounded_collector_history_rows(*(
        bounded_collector_history_row(**dict(row))
        for row in history
    ))
    bounded_movements = bounded_collector_movement_rows(*(
        bounded_collector_movement_row(**dict(row))
        for row in movements
    ))
    return (
        REQUIRED_SCHEMA_ROWS,
        (baseline_estimate_row(
            sections_json=json.dumps(target_sections(), ensure_ascii=False),
        ),),
        (reconciliation_row(),),
        SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
        (bounded_collector_context_row(
            project_name="Private project",
            owner_count=1,
            base_work_package="Основная",
            base_sections_json=json.dumps(
                sections(quantity="10"), ensure_ascii=False,
            ),
        ),),
        bounded_requests,
        bounded_deliveries,
        bounded_allocations,
        supplier_invoices,
        bounded_invoices,
        bounded_history,
        lots,
        bounded_movements,
        lot_movements,
    )


def run_case(
    *, report=None, selection=None, result_sets=None, baseline=None,
    current_supply=None,
):
    report = report or valid_report()
    cursor = FakeCursor(result_sets or valid_result_sets())
    connection = FakeConnection(cursor)
    baseline = baseline or baseline_report(report)
    current_supply = current_supply or current_supply_report(report)
    if baseline is not None:
        current_supply.update(copy.deepcopy(baseline))
    with mock.patch.object(
        rfq_content, "collect_supply_warehouse_impact_audit",
        return_value=current_supply, create=True,
    ):
        result = rfq_content.run_supply_rfq_content_preview(
            lambda: connection,
            report,
            selection or {"requestId": 21, "requestItemIndex": 0},
        )
    return result, connection, cursor


class SupplyRfqContentPreviewTests(unittest.TestCase):
    def test_builds_deterministic_target_content_and_exact_open_balance(self):
        first, connection, cursor = run_case()
        second, _, _ = run_case()

        self.assertEqual(first, second)
        self.assertEqual(first["contentVersion"], 1)
        self.assertEqual(first["state"], "draft_ready")
        self.assertTrue(first["readyForRfqDraft"])
        self.assertEqual(first["blockers"], [])
        self.assertEqual(first["request"], {
            "requestId": 21,
            "requestItemIndex": 0,
            "status": "Утверждена",
        })
        self.assertEqual(first["balance"], {
            "requestedQuantity": "10.000000",
            "receivedQuantity": "3.000000",
            "allocatedQuantity": "2.000000",
            "openQuantity": "5.000000",
            "unit": "кг",
        })
        self.assertEqual(first["rfqDraft"], {
            "status": "human_supplier_selection_required",
            "sendAllowed": False,
            "supplierIds": [],
            "items": [{
                "materialName": "PRIVATE MATERIAL",
                "quantity": "5.000000",
                "unit": "кг",
                "lineage": {
                    "requestId": 21,
                    "requestItemIndex": 0,
                    "base": {
                        "estimateId": 51,
                        "sectionIndex": 0,
                        "itemIndex": 0,
                    },
                    "target": {
                        "estimateId": 52,
                        "sectionIndex": 0,
                        "itemIndex": 0,
                    },
                },
            }],
        })
        self.assertRegex(first["requestItemSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(first["contentSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            first["contentSha256"],
            rfq_content.calculate_content_sha256(first),
        )
        self.assertTrue(first["readOnlyTransaction"])
        self.assertTrue(first["rolledBack"])
        serialized = json.dumps(first, ensure_ascii=False)
        for forbidden in (
            "Private material", "Private project", "must-not-leak",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)
        self.assertEqual(len(cursor.calls), 7)
        for sql, params in cursor.calls:
            self.assertTrue(sql.upper().startswith("SELECT "))
            self.assertNotIn("FOR UPDATE", sql.upper())
            self.assertIsInstance(params, tuple)
        project_sql = cursor.calls[1][0]
        self.assertGreaterEqual(project_sql.upper().count("LIMIT 2"), 3)
        schema_sql, schema_params = cursor.calls[0]
        self.assertIn("jsonb_to_recordset", schema_sql)
        self.assertIn("pg_catalog.pg_attribute", schema_sql)
        self.assertNotIn("information_schema", schema_sql)
        self.assertIn("LIMIT %s", schema_sql)
        self.assertEqual(
            schema_params[-1],
            sum(
                len(columns)
                for columns in rfq_content.RFQ_CONTENT_REQUIRED_COLUMNS.values()
            ) + 1,
        )

        alias_report = confirmed_alias_report()
        alias_estimates = (
            estimate_row(
                51,
                sections(quantity="10", name="Old material", estimateItemKey=None),
            ),
            estimate_row(
                52,
                sections(
                    quantity="12", name="Canonical material",
                    estimateItemKey=None,
                ),
            ),
        )
        alias_result, _, _ = run_case(
            report=alias_report,
            result_sets=valid_result_sets(
                estimates=alias_estimates,
                aliases=({
                    "id": 7,
                    "project_name": "Private project",
                    "alias_name": "Old material",
                    "canonical_name": "Canonical material",
                    "canonical_unit": "кг",
                    "active": True,
                },),
                requests=(request_row(items=[confirmed_alias_request_item()]),),
                deliveries=(delivery_row(material_name="Old material"),),
            ),
        )
        self.assertEqual(alias_result["state"], "draft_ready")
        self.assertEqual(
            alias_result["rfqDraft"]["items"][0]["materialName"],
            "Canonical material",
        )
        self.assertEqual(alias_result["candidate"]["matchKind"], "confirmed_alias")
        self.assertEqual(alias_result["candidate"]["aliasIds"], [7])

        report = valid_report()
        real_cursor = FakeCursor((
            *full_collector_result_sets(),
            *valid_result_sets(),
        ))
        real_connection = FakeConnection(real_cursor)
        get_db = mock.Mock(return_value=real_connection)
        real_baseline = rfq_content.run_supply_rfq_content_preview(
            get_db,
            report,
            {"requestId": 21, "requestItemIndex": 0},
        )
        self.assertEqual(real_baseline["state"], "draft_ready")
        self.assertEqual(len(real_cursor.calls), 21)
        self.assertEqual(real_connection.rollbacks, 1)
        get_db.assert_called_once_with()
        for sql, params in real_cursor.calls:
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            if "COUNT(*)" in normalized:
                self.assertIn("WITH LIMITED AS MATERIALIZED", normalized)
                self.assertIn("COUNT(*) OVER ()", normalized)
            self.assertNotIn("FOR UPDATE", normalized)
            self.assertIsInstance(params, tuple)

    def test_rejects_invalid_readiness_and_selection_before_opening_database(self):
        invalid = valid_report()
        invalid["evidenceSha256"] = "0" * 64
        blocked = valid_report()
        blocked["domains"]["supply"]["openSupply"] = []
        blocked["domains"]["supply"]["summary"]["openSupplyItems"] = 0
        rehash(blocked)
        cases = (
            (invalid, {"requestId": 21, "requestItemIndex": 0},
             "supply_rfq_readiness_invalid"),
            (blocked, {"requestId": 21, "requestItemIndex": 0},
             "supply_rfq_readiness_blocked"),
            (valid_report(), {"requestId": 22, "requestItemIndex": 0},
             "supply_rfq_selection_invalid"),
            (valid_report(), {
                "requestId": 21, "requestItemIndex": 0, "target": {},
            }, "supply_rfq_selection_invalid"),
            (valid_report(), {"requestId": True, "requestItemIndex": 0},
             "supply_rfq_selection_invalid"),
            (valid_report(), {"requestId": 21, "requestItemIndex": -1},
             "supply_rfq_selection_invalid"),
        )

        for report, selection, expected in cases:
            with self.subTest(expected=expected):
                get_db = mock.Mock(side_effect=AssertionError("must not open"))
                with self.assertRaises(rfq_content.SupplyRfqContentError) as error:
                    rfq_content.run_supply_rfq_content_preview(
                        get_db, report, selection,
                    )
                self.assertEqual(error.exception.code, expected)
                self.assertEqual(str(error.exception), expected)
                get_db.assert_not_called()

    def test_current_source_schema_and_material_drift_fail_closed(self):
        missing_schema, _, _ = run_case(
            result_sets=valid_result_sets(schema=()),
        )
        self.assertEqual(missing_schema["state"], "incomplete")
        self.assertEqual(missing_schema["blockers"], [
            "supply_rfq_schema_not_ready",
        ])

        schema_overflow, _, _ = run_case(
            result_sets=valid_result_sets(
                schema=schema_rows() + ({
                    "table_name": "projects",
                    "column_name": "id",
                },),
            ),
        )
        self.assertEqual(schema_overflow["state"], "incomplete")
        self.assertEqual(schema_overflow["blockers"], [
            "supply_rfq_schema_not_ready",
        ])

        source_not_ready, _, source_cursor = run_case(
            baseline=baseline_report(
                sourceReady=False,
                readyForDomainScan=False,
                reasonCounts={"source_revision_mismatch": 1},
            ),
        )
        self.assertEqual(source_not_ready["state"], "incomplete")
        self.assertEqual(source_not_ready["blockers"], [
            "supply_rfq_source_not_ready",
        ])
        self.assertEqual(source_cursor.calls, [])

        changed_reconciliation = baseline_report()
        changed_reconciliation["source"]["reconciliationStatus"] = "Отклонена"
        source_drift, _, drift_cursor = run_case(
            baseline=changed_reconciliation,
        )
        self.assertEqual(source_drift["state"], "needs_review")
        self.assertEqual(source_drift["blockers"], ["supply_rfq_source_drift"])
        self.assertEqual(drift_cursor.calls, [])

        changed_target = (
            estimate_row(51, sections(quantity="10")),
            estimate_row(
                52,
                sections(
                    quantity="12", name="PRIVATE MATERIAL",
                    estimateItemKey="different-key",
                ),
            ),
        )
        lineage_drift, _, lineage_cursor = run_case(
            result_sets=valid_result_sets(estimates=changed_target),
        )
        self.assertEqual(lineage_drift["state"], "needs_review")
        self.assertEqual(lineage_drift["blockers"], [
            "supply_rfq_material_lineage_drift",
        ])
        self.assertIsNone(lineage_drift["rfqDraft"])
        self.assertNotIn(
            "Private material",
            json.dumps(lineage_drift, ensure_ascii=False),
        )
        self.assertEqual(len(lineage_cursor.calls), 4)

    def test_status_scope_and_request_lineage_drift_never_emit_content(self):
        for status in (
            "Новая", "Подтверждена прорабом", "В пути", "Поставлено", "",
        ):
            with self.subTest(status=status):
                result, _, cursor = run_case(result_sets=valid_result_sets(
                    requests=(request_row(request_status=status),),
                ))
                self.assertEqual(result["state"], "no_action")
                self.assertEqual(result["blockers"], [
                    "supply_rfq_request_status_ineligible",
                ])
                self.assertIsNone(result["rfqDraft"])
                self.assertEqual(len(cursor.calls), 5)

        legacy_ineligible = request_item()
        legacy_ineligible["estimateLineage"]["version"] = 1
        for label, row in (
            (
                "invalid lineage",
                request_row(
                    request_status="Новая", items=[legacy_ineligible],
                ),
            ),
            (
                "oversized snapshot",
                request_row(
                    request_status="Новая",
                    items_json=None,
                    items_bytes=rfq_content.MAX_REQUEST_JSON_BYTES + 1,
                ),
            ),
        ):
            with self.subTest(ineligible_status_precedence=label):
                result, _, cursor = run_case(result_sets=valid_result_sets(
                    requests=(row,),
                ))
                self.assertEqual(result["state"], "no_action")
                self.assertEqual(result["blockers"], [
                    "supply_rfq_request_status_ineligible",
                ])
                self.assertIsNone(result["rfqDraft"])
                self.assertEqual(len(cursor.calls), 5)

        oversized_ineligible = request_row(
            request_status="Новая",
            items_json=None,
            items_bytes=rfq_content.MAX_REQUEST_JSON_BYTES + 1,
        )
        real_status_cursor = FakeCursor((
            *full_collector_result_sets(
                requests=(oversized_ineligible,),
            )[:6],
            *valid_result_sets(requests=(oversized_ineligible,)),
        ))
        real_status_connection = FakeConnection(real_status_cursor)
        real_status = rfq_content.run_supply_rfq_content_preview(
            lambda: real_status_connection,
            valid_report(),
            {"requestId": 21, "requestItemIndex": 0},
        )
        self.assertEqual(real_status["state"], "no_action")
        self.assertEqual(real_status["blockers"], [
            "supply_rfq_request_status_ineligible",
        ])
        self.assertIsNone(real_status["rfqDraft"])

        kp_requested, _, _ = run_case(result_sets=valid_result_sets(
            requests=(request_row(request_status="КП запрошены"),),
        ))
        self.assertEqual(kp_requested["state"], "draft_ready")

        bad_items = []
        legacy = request_item()
        legacy["estimateLineage"]["version"] = 1
        bad_items.append(("legacy", [legacy]))
        unvalidated = request_item()
        unvalidated["estimateLineage"]["validated"] = False
        bad_items.append(("unvalidated", [unvalidated]))
        wrong_coordinate = request_item()
        wrong_coordinate["estimateLineage"]["sources"][0]["itemIndex"] = 1
        bad_items.append(("coordinate", [wrong_coordinate]))
        conflicting_name = request_item(name="Conflicting material")
        bad_items.append(("conflicting name", [conflicting_name]))
        bad_items.append(("quantity", [request_item(quantity="1.0000001")]))

        for name, items in bad_items:
            with self.subTest(name=name):
                result, _, cursor = run_case(result_sets=valid_result_sets(
                    requests=(request_row(items=items),),
                ))
                self.assertEqual(result["state"], "needs_review")
                self.assertEqual(result["blockers"], [
                    "supply_rfq_request_invalid",
                ])
                self.assertIsNone(result["rfqDraft"])
                serialized = json.dumps(result, ensure_ascii=False)
                self.assertNotIn("Private material", serialized)
                self.assertNotIn("must-not-leak", serialized)
                self.assertEqual(len(cursor.calls), 5)

        wrong_project, _, _ = run_case(result_sets=valid_result_sets(
            projects=(project_row(same_company_owner_count=2),),
        ))
        self.assertEqual(wrong_project["blockers"], [
            "supply_rfq_project_identity_invalid",
        ])

    def test_ambiguous_or_invalid_balance_and_bounds_fail_closed(self):
        duplicate_items = [request_item(), request_item()]
        ambiguous, _, _ = run_case(result_sets=valid_result_sets(
            requests=(request_row(items=duplicate_items),),
        ))
        self.assertEqual(ambiguous["state"], "needs_review")
        self.assertEqual(ambiguous["blockers"], [
            "supply_rfq_supply_evidence_invalid",
        ])

        mixed_request = request_row(items=[
            request_item(),
            {
                "name": "Private material",
                "unit": "кг",
                "quantity": "10",
            },
        ])
        mixed_cursor = FakeCursor((
            *full_collector_result_sets(requests=(mixed_request,)),
            *valid_result_sets(requests=(mixed_request,)),
        ))
        mixed_connection = FakeConnection(mixed_cursor)
        mixed_manual_identity = rfq_content.run_supply_rfq_content_preview(
            lambda: mixed_connection,
            valid_report(),
            {"requestId": 21, "requestItemIndex": 0},
        )
        self.assertEqual(mixed_manual_identity["state"], "needs_review")
        self.assertEqual(mixed_manual_identity["blockers"], [
            "supply_rfq_supply_evidence_invalid",
        ])
        self.assertIsNone(mixed_manual_identity["rfqDraft"])
        self.assertEqual(len(mixed_cursor.calls), 21)

        no_delivery_cursor = FakeCursor((
            *full_collector_result_sets(
                requests=(mixed_request,), deliveries=(),
            ),
            *valid_result_sets(
                requests=(mixed_request,), deliveries=(),
            ),
        ))
        no_delivery_connection = FakeConnection(no_delivery_cursor)
        no_delivery = rfq_content.run_supply_rfq_content_preview(
            lambda: no_delivery_connection,
            valid_report(),
            {"requestId": 21, "requestItemIndex": 0},
        )
        self.assertEqual(no_delivery["state"], "draft_ready")
        self.assertEqual(
            no_delivery["balance"]["openQuantity"], "8.000000",
        )

        foreign_delivery, _, _ = run_case(result_sets=valid_result_sets(
            deliveries=(delivery_row(delivery_company_id=999),),
        ))
        self.assertEqual(foreign_delivery["blockers"], [
            "supply_rfq_supply_evidence_invalid",
        ])

        invalid_quantity, _, _ = run_case(result_sets=valid_result_sets(
            deliveries=(delivery_row(received_quantity="NaN"),),
        ))
        self.assertEqual(invalid_quantity["blockers"], [
            "supply_rfq_supply_evidence_invalid",
        ])

        allocation_drift, _, _ = run_case(result_sets=valid_result_sets(
            allocations=(allocation_row(source_item_index=9),),
        ))
        self.assertEqual(allocation_drift["blockers"], [
            "supply_rfq_supply_evidence_invalid",
        ])

        overprotected, _, _ = run_case(result_sets=valid_result_sets(
            deliveries=(delivery_row(received_quantity="9"),),
            allocations=(allocation_row(allocation_quantity="2"),),
        ))
        self.assertEqual(overprotected["blockers"], [
            "supply_rfq_supply_evidence_invalid",
        ])

        zero, _, _ = run_case(result_sets=valid_result_sets(
            deliveries=(delivery_row(received_quantity="10"),),
            allocations=(),
        ))
        self.assertEqual(zero["state"], "no_action")
        self.assertEqual(zero["blockers"], ["supply_rfq_open_balance_zero"])
        self.assertIsNone(zero["rfqDraft"])

        too_many = tuple(
            delivery_row(delivery_id=index + 1, received_quantity="0")
            for index in range(rfq_content.MAX_CHILD_ROWS + 1)
        )
        bounded, _, _ = run_case(result_sets=valid_result_sets(
            deliveries=too_many,
        ))
        self.assertEqual(bounded["state"], "incomplete")
        self.assertEqual(bounded["blockers"], [
            "supply_rfq_child_scan_limit_exceeded",
        ])

        for result in (
            ambiguous, mixed_manual_identity, foreign_delivery,
            invalid_quantity, allocation_drift, overprotected, zero, bounded,
        ):
            serialized = json.dumps(result, ensure_ascii=False)
            self.assertNotIn("Private material", serialized)
            self.assertNotIn("must-not-leak", serialized)
            self.assertIsNone(result["contentSha256"])

    def test_current_full_supply_and_warehouse_projection_gates_content(self):
        foreign_invoice_cursor = FakeCursor((
            *full_collector_result_sets(supplier_invoices=({
                "supplier_invoice_id": 501,
                "request_id": 21,
                "invoice_company_id": 999,
            },)),
            *valid_result_sets(),
        ))
        foreign_invoice_connection = FakeConnection(foreign_invoice_cursor)
        foreign_invoice = rfq_content.run_supply_rfq_content_preview(
            lambda: foreign_invoice_connection,
            valid_report(),
            {"requestId": 21, "requestItemIndex": 0},
        )
        self.assertEqual(foreign_invoice["state"], "needs_review")
        self.assertEqual(foreign_invoice["blockers"], [
            "supply_rfq_supply_warehouse_not_ready",
        ])
        self.assertIsNone(foreign_invoice["rfqDraft"])
        self.assertEqual(len(foreign_invoice_cursor.calls), 19)

        duplicate_request = request_row(request_id=22)
        duplicate_cursor = FakeCursor((
            *full_collector_result_sets(requests=(
                request_row(), duplicate_request,
            )),
            *valid_result_sets(),
        ))
        duplicate_connection = FakeConnection(duplicate_cursor)
        ambiguous = rfq_content.run_supply_rfq_content_preview(
            lambda: duplicate_connection,
            valid_report(),
            {"requestId": 21, "requestItemIndex": 0},
        )
        self.assertEqual(ambiguous["state"], "needs_review")
        self.assertEqual(ambiguous["blockers"], [
            "supply_rfq_open_request_ambiguous",
        ])
        self.assertIsNone(ambiguous["rfqDraft"])

        current_projection = copy.deepcopy(
            current_supply_report()["supplyWarehouseImpact"]
        )
        unrelated = dict(current_projection["openSupply"][0])
        unrelated.update({
            "requestId": 22,
            "sourceItemIndex": 1,
        })
        current_projection["openSupply"].append(unrelated)
        current_projection["summary"].update({
            "supplyRequestRows": 2,
            "supplyItems": 2,
            "openSupplyItems": 2,
        })
        missing_lineage, _, _ = run_case(
            current_supply=current_supply_report(
                projection=current_projection,
            ),
        )
        self.assertEqual(missing_lineage["state"], "needs_review")
        self.assertEqual(missing_lineage["blockers"], [
            "supply_rfq_material_lineage_drift",
        ])
        self.assertIsNone(missing_lineage["rfqDraft"])

        unrelated_duplicate = dict(unrelated)
        unrelated_duplicate["requestId"] = 23
        current_projection["openSupply"].append(unrelated_duplicate)
        current_projection["summary"].update({
            "supplyRequestRows": 3,
            "supplyItems": 3,
            "openSupplyItems": 3,
        })
        unrelated_ambiguous, _, _ = run_case(
            current_supply=current_supply_report(
                projection=current_projection,
            ),
        )
        self.assertEqual(unrelated_ambiguous["state"], "needs_review")
        self.assertEqual(unrelated_ambiguous["blockers"], [
            "supply_rfq_open_request_ambiguous",
        ])
        self.assertIsNone(unrelated_ambiguous["rfqDraft"])

    def test_error_rolls_back_and_static_boundary_has_no_writer_or_runtime_hook(self):
        class FailingCursor(FakeCursor):
            def execute(self, sql, params=()):
                super().execute(sql, params)
                raise RuntimeError("private database detail")

        report = valid_report()
        cursor = FailingCursor(())
        connection = FakeConnection(cursor)
        with mock.patch.object(
            rfq_content,
            "collect_supply_warehouse_impact_audit",
            return_value=current_supply_report(report),
        ):
            with self.assertRaises(rfq_content.SupplyRfqContentError) as error:
                rfq_content.run_supply_rfq_content_preview(
                    lambda: connection,
                    report,
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_rfq_read_failed")
        self.assertNotIn("private database detail", str(error.exception))
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

        class CursorCloseFails(FakeCursor):
            def close(self):
                self.closed = True
                raise RuntimeError("private cursor close detail")

        close_cursor = CursorCloseFails(valid_result_sets())
        close_connection = FakeConnection(close_cursor)
        with mock.patch.object(
            rfq_content,
            "collect_supply_warehouse_impact_audit",
            return_value=current_supply_report(report),
            create=True,
        ):
            with self.assertRaises(rfq_content.SupplyRfqContentError) as error:
                rfq_content.run_supply_rfq_content_preview(
                    lambda: close_connection,
                    report,
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_rfq_cleanup_failed")
        self.assertNotIn("private cursor close detail", str(error.exception))
        self.assertTrue(close_cursor.closed)
        self.assertTrue(close_connection.closed)

        class ConnectionCloseFails(FakeConnection):
            def close(self):
                self.closed = True
                raise RuntimeError("private connection close detail")

        connection_cursor = FakeCursor(valid_result_sets())
        connection_close_fails = ConnectionCloseFails(connection_cursor)
        with mock.patch.object(
            rfq_content,
            "collect_supply_warehouse_impact_audit",
            return_value=current_supply_report(report),
            create=True,
        ):
            with self.assertRaises(rfq_content.SupplyRfqContentError) as error:
                rfq_content.run_supply_rfq_content_preview(
                    lambda: connection_close_fails,
                    report,
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_rfq_cleanup_failed")
        self.assertNotIn(
            "private connection close detail", str(error.exception),
        )
        self.assertTrue(connection_cursor.closed)
        self.assertTrue(connection_close_fails.closed)

        class RollbackFails(FakeConnection):
            def rollback(self):
                self.rollbacks += 1
                raise RuntimeError("private rollback detail")

        rollback_cursor = FailingCursor(())
        rollback_connection = RollbackFails(rollback_cursor)
        with mock.patch.object(
            rfq_content,
            "collect_supply_warehouse_impact_audit",
            side_effect=RuntimeError("private read detail"),
            create=True,
        ):
            with self.assertRaises(rfq_content.SupplyRfqContentError) as error:
                rfq_content.run_supply_rfq_content_preview(
                    lambda: rollback_connection,
                    report,
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_rfq_rollback_failed")
        self.assertNotIn("private rollback detail", str(error.exception))
        self.assertTrue(rollback_connection.closed)

        safe_cursor = FakeCursor(())
        safe_rollback_connection = RollbackFails(safe_cursor)
        with mock.patch.object(
            rfq_content,
            "_collect",
            side_effect=rfq_content.SupplyRfqContentError(
                "supply_rfq_content_invalid",
            ),
        ):
            with self.assertRaises(rfq_content.SupplyRfqContentError) as error:
                rfq_content.run_supply_rfq_content_preview(
                    lambda: safe_rollback_connection,
                    report,
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_rfq_rollback_failed")
        self.assertTrue(safe_cursor.closed)
        self.assertTrue(safe_rollback_connection.closed)

        root = Path(__file__).resolve().parents[3]
        source_text = (
            root / "backend/features/supply_recommendation_preview/rfq_content.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "backend.main", "request_kp_from_suppliers", "supplier_offers",
            "messenger_outbox", "_send_email", "log_audit", "compare-kp",
            "suggest_suppliers", "from backend.db import", "commit(", "FOR UPDATE",
            "INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE ",
        ):
            self.assertNotIn(forbidden, source_text)
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "package.json",
        ):
            self.assertNotIn(
                "supply_recommendation_preview.rfq_content",
                (root / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
