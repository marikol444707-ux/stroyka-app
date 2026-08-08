import json
import unittest

from backend.features.estimate_revision_impact.supply_warehouse_projection import (
    MAX_INVOICE_LINES,
    MAX_REQUEST_ITEMS,
    build_supply_warehouse_projection,
)


def context(**overrides):
    value = {
        "companyId": 4,
        "projectId": 17,
        "projectName": "Private project",
        "projectNameOwnerCount": 1,
        "baseEstimateId": 51,
        "targetEstimateId": 52,
        "workPackage": "Основная",
        "baseSections": [{
            "name": "Private section",
            "items": [{
                "itemType": "material",
                "name": "Private material",
                "unit": "кг",
                "quantity": "10",
                "estimateItemKey": "base-material",
            }],
        }],
    }
    value.update(overrides)
    return value


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
        "privateNote": "must never be public",
    }
    item.update(overrides)
    return item


def request_row(**overrides):
    row = {
        "request_id": 61,
        "request_company_id": 4,
        "request_project": "Private project",
        "request_work_package": "Основная",
        "request_status": "Новая",
        "items_json": json.dumps([request_item()], ensure_ascii=False),
    }
    row.update(overrides)
    return row


def delivery_row(**overrides):
    row = {
        "delivery_id": 71,
        "request_id": 61,
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
        "allocation_id": 81,
        "request_id": 61,
        "request_item_index": 0,
        "allocation_company_id": 4,
        "source_estimate_id": 51,
        "source_section_index": 0,
        "source_item_index": 0,
        "allocation_quantity": "2",
    }
    row.update(overrides)
    return row


def supplier_invoice_row(**overrides):
    row = {
        "supplier_invoice_id": 91,
        "request_id": 61,
        "invoice_company_id": 4,
    }
    row.update(overrides)
    return row


def warehouse_invoice_row(**overrides):
    row = {
        "warehouse_invoice_id": 101,
        "invoice_company_id": 4,
        "supply_request_id": 61,
        "supply_delivery_id": 71,
        "supplier_invoice_id": 91,
        "invoice_project": "Private project",
        "items": json.dumps([{
            "name": "Private material",
            "unit": "кг",
            "quantity": "3",
            "price": 999,
        }], ensure_ascii=False),
    }
    row.update(overrides)
    return row


def history_row(**overrides):
    row = {
        "history_id": 111,
        "history_company_id": 4,
        "history_work_package": "Основная",
        "source_invoice_id": 101,
        "source_invoice_line_index": 0,
    }
    row.update(overrides)
    return row


def lot_row(**overrides):
    row = {
        "lot_id": 121,
        "lot_company_id": 4,
        "lot_project_id": 17,
        "warehouse_invoice_id": 101,
        "invoice_line_index": 0,
    }
    row.update(overrides)
    return row


def movement_row(**overrides):
    row = {
        "movement_id": 131,
        "movement_company_id": 4,
        "movement_work_package": "Основная",
        "source_invoice_id": 101,
        "source_invoice_line_index": 0,
    }
    row.update(overrides)
    return row


def lot_movement_row(**overrides):
    row = {
        "lot_movement_id": 141,
        "lot_id": 121,
        "lot_movement_company_id": 4,
        "warehouse_movement_id": 131,
    }
    row.update(overrides)
    return row


def project(**overrides):
    return build_supply_warehouse_projection(
        context(),
        [request_row()],
        [delivery_row()],
        [allocation_row()],
        [supplier_invoice_row()],
        [warehouse_invoice_row()],
        [history_row()],
        [lot_row()],
        [movement_row()],
        [lot_movement_row()],
        **overrides,
    )



class SupplyWarehouseProjectionContractTests(unittest.TestCase):
    def test_exact_open_balance_and_protected_chain_are_id_only(self):
        projection = project()

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["state"], "complete")
        self.assertEqual(projection["openSupply"], [{
            "requestId": 61,
            "requestItemIndex": 0,
            "sourceEstimateId": 51,
            "sourceSectionIndex": 0,
            "sourceItemIndex": 0,
            "state": "open_balance",
        }])
        self.assertEqual(projection["protectedEvidence"], {
            "closedSupplyRequestIds": [],
            "deliveryIds": [71],
            "allocationIds": [81],
            "supplierInvoiceIds": [91],
            "warehouseInvoiceIds": [101],
            "warehouseHistoryIds": [111],
            "receiptLotIds": [121],
            "warehouseMovementIds": [131],
            "lotMovementIds": [141],
        })
        serialized = json.dumps(projection, ensure_ascii=False)
        for forbidden in (
            "Private project", "Private section", "Private material",
            "must never be public", "base-material", "999", '"quantity"',
            '"unit"',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_fully_received_open_item_is_protected_not_open(self):
        projection = build_supply_warehouse_projection(
            context(),
            [request_row()],
            [delivery_row(received_quantity="10")],
            [], [], [], [], [], [], [],
        )

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["openSupply"], [])
        self.assertEqual(projection["summary"]["protectedSupplyItems"], 1)

    def test_closed_request_is_reported_without_open_balance(self):
        projection = build_supply_warehouse_projection(
            context(),
            [request_row(request_status="Поставлено")],
            [], [], [], [], [], [], [], [],
        )

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["openSupply"], [])
        self.assertEqual(
            projection["protectedEvidence"]["closedSupplyRequestIds"], [61],
        )

    def test_duplicate_request_identity_with_delivery_requires_review(self):
        duplicate_items = json.dumps(
            [request_item(), request_item()], ensure_ascii=False,
        )
        projection = build_supply_warehouse_projection(
            context(),
            [request_row(items_json=duplicate_items)],
            [delivery_row()],
            [], [], [], [], [], [], [],
        )

        self.assertFalse(projection["complete"])
        self.assertEqual(projection["reasonCounts"], {
            "supply_delivery_allocation_ambiguous": 1,
            "supply_source_coordinate_duplicate": 2,
        })

    def test_foreign_rows_are_reviewed_and_their_ids_are_not_exposed(self):
        projection = build_supply_warehouse_projection(
            context(),
            [request_row()],
            [delivery_row(delivery_id=7001, delivery_company_id=5)],
            [allocation_row(allocation_id=8001, allocation_company_id=5)],
            [supplier_invoice_row(supplier_invoice_id=9001, invoice_company_id=5)],
            [warehouse_invoice_row(warehouse_invoice_id=10001, invoice_company_id=5)],
            [history_row(
                history_id=11001, history_company_id=5,
                source_invoice_id=10001,
            )],
            [lot_row(
                lot_id=12001, lot_company_id=5,
                warehouse_invoice_id=10001,
            )],
            [movement_row(
                movement_id=13001, movement_company_id=5,
                source_invoice_id=10001,
            )],
            [lot_movement_row(
                lot_movement_id=14001, lot_movement_company_id=5,
                lot_id=12001, warehouse_movement_id=13001,
            )],
        )

        self.assertFalse(projection["complete"])
        serialized = json.dumps(projection)
        for foreign_id in range(7001, 14002, 1000):
            self.assertNotIn(str(foreign_id), serialized)
        self.assertGreaterEqual(projection["summary"]["needsReview"], 8)

    def test_invalid_invoice_line_and_missing_lot_link_are_fixed_reviews(self):
        projection = build_supply_warehouse_projection(
            context(),
            [request_row()],
            [delivery_row()],
            [], [],
            [warehouse_invoice_row(supplier_invoice_id=None)],
            [history_row(source_invoice_line_index=4)],
            [],
            [movement_row()],
            [],
        )

        self.assertFalse(projection["complete"])
        self.assertEqual(projection["reasonCounts"], {
            "warehouse_movement_lot_missing": 1,
            "warehouse_receipt_line_invalid": 1,
        })

    def test_request_item_and_invoice_line_counts_are_bounded(self):
        oversized_request = request_row(items_json=json.dumps(
            [request_item() for _ in range(MAX_REQUEST_ITEMS + 1)],
            ensure_ascii=False,
        ))
        oversized_invoice = warehouse_invoice_row(
            supplier_invoice_id=None,
            items=json.dumps([
                {"name": "private", "unit": "кг", "quantity": 1}
                for _ in range(MAX_INVOICE_LINES + 1)
            ]),
        )

        projection = build_supply_warehouse_projection(
            context(), [oversized_request], [delivery_row()], [], [],
            [oversized_invoice], [], [], [], [],
        )

        self.assertEqual(projection["reasonCounts"], {
            "supply_request_item_limit_exceeded": 1,
            "warehouse_invoice_items_limit_exceeded": 1,
        })

    def test_movement_requires_its_exact_immutable_lot_event(self):
        projection = build_supply_warehouse_projection(
            context(), [request_row()], [delivery_row()], [], [],
            [warehouse_invoice_row(supplier_invoice_id=None)],
            [history_row()], [lot_row()], [movement_row()], [],
        )

        self.assertEqual(projection["reasonCounts"], {
            "warehouse_lot_movement_missing": 1,
        })

    def test_lot_event_cannot_link_different_invoice_lines(self):
        invoice = warehouse_invoice_row(
            supplier_invoice_id=None,
            items=json.dumps([
                {"name": "private one"}, {"name": "private two"},
            ]),
        )
        projection = build_supply_warehouse_projection(
            context(), [request_row()], [delivery_row()], [], [], [invoice],
            [history_row()], [lot_row(invoice_line_index=0)],
            [movement_row(source_invoice_line_index=1)],
            [lot_movement_row()],
        )

        self.assertIn(
            "warehouse_lot_movement_source_mismatch",
            projection["reasonCounts"],
        )

    def test_manual_request_history_is_outside_revision_impact(self):
        manual_request = request_row(items_json=json.dumps([{
            "name": "Manual private material",
            "quantity": 10,
            "unit": "кг",
        }]))
        projection = build_supply_warehouse_projection(
            context(), [manual_request], [delivery_row()], [allocation_row()],
            [supplier_invoice_row()], [warehouse_invoice_row()],
            [history_row()], [lot_row()], [movement_row()], [lot_movement_row()],
        )

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["openSupply"], [])
        self.assertEqual(projection["protectedEvidence"], {
            "closedSupplyRequestIds": [],
            "deliveryIds": [],
            "allocationIds": [],
            "supplierInvoiceIds": [],
            "warehouseInvoiceIds": [],
            "warehouseHistoryIds": [],
            "receiptLotIds": [],
            "warehouseMovementIds": [],
            "lotMovementIds": [],
        })



if __name__ == "__main__":
    unittest.main()
