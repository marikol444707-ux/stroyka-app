import json
import unittest

from backend.features.estimate_row_transfer.supply_apply import (
    canonical_request_item_snapshot,
)
from backend.features.estimate_row_transfer.supply_projection import (
    attach_supply_allocation_projection,
)
from backend.features.estimate_row_transfer.test_audit import supply_request_row


class FakeCursor:
    def __init__(self, allocations, table_ready=True):
        self.allocations = allocations
        self.table_ready = table_ready
        self.calls = []
        self.current = None

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        self.calls.append((compact, params))
        if "to_regclass" in compact:
            self.current = {"ready": self.table_ready}
        elif "FROM public.estimate_row_supply_allocations" in compact:
            self.current = self.allocations
        else:
            raise AssertionError("unexpected SQL: " + compact)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return list(self.current or [])


def visible_request(**overrides):
    source = supply_request_row()
    row = {
        "id": 61,
        "companyId": 1,
        "itemsJson": source["items_json"],
    }
    row.update(overrides)
    return row


def allocation(**overrides):
    item = json.loads(supply_request_row()["items_json"])[0]
    _payload, digest = canonical_request_item_snapshot(item)
    row = {
        "entry_id": 8,
        "plan_id": 5,
        "company_id": 1,
        "request_id": 61,
        "request_item_index": 0,
        "request_item_sha256": digest,
        "source_estimate_id": 14,
        "source_estimate_version_id": 71,
        "source_section_index": 0,
        "source_item_index": 0,
        "source_item_key": "old-material",
        "target_estimate_id": 15,
        "target_estimate_version_id": 72,
        "target_section_index": 0,
        "target_item_index": 1,
        "target_item_key": "new-material",
        "target_material_name": "Новая смесь",
        "target_unit": "кг",
        "target_work_package": "Отделка",
        "requested_quantity": 10,
        "received_quantity": 2,
        "previously_allocated_quantity": 0,
        "allocation_quantity": 3,
        "remaining_unallocated_quantity": 5,
        "applied_at": "2026-08-07 18:00:00+03",
    }
    row.update(overrides)
    return row


class SupplyProjectionAttachmentTests(unittest.TestCase):
    def test_main_attaches_internal_projection_only_for_internal_supply_readers(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[2] / "main.py").read_text(
            encoding="utf-8"
        )
        route = source[source.index("def get_supply_requests("):source.index(
            '@app.post("/supply-requests")'
        )]

        self.assertIn("if is_internal_supply_reader", route)
        self.assertIn("attach_supply_allocation_projection", route)

    def test_attaches_only_exact_live_item_allocation_to_visible_owner(self):
        rows = [visible_request()]
        cursor = FakeCursor([allocation(), allocation(company_id=2, entry_id=9)])

        result = attach_supply_allocation_projection(cursor, rows)

        self.assertEqual(len(result[0]["supplyTransferAllocations"]), 1)
        self.assertEqual(result[0]["supplyTransferAllocations"][0], {
            "entryId": 8,
            "planId": 5,
            "requestItemIndex": 0,
            "state": "ready",
            "reasonCode": "exact_request_item_snapshot",
            "quantity": "3",
            "remainingQuantity": "5",
            "sourceEstimateId": 14,
            "sourceEstimateVersionId": 71,
            "sourceSectionIndex": 0,
            "sourceItemIndex": 0,
            "sourceItemKey": "old-material",
            "targetEstimateId": 15,
            "targetEstimateVersionId": 72,
            "targetSectionIndex": 0,
            "targetItemIndex": 1,
            "targetItemKey": "new-material",
            "targetMaterialName": "Новая смесь",
            "targetUnit": "кг",
            "targetWorkPackage": "Отделка",
            "appliedAt": "2026-08-07 18:00:00+03",
        })

    def test_hash_drift_is_exposed_as_review_not_silently_applied(self):
        cursor = FakeCursor([allocation(request_item_sha256="0" * 64)])

        result = attach_supply_allocation_projection(cursor, [visible_request()])

        self.assertEqual(
            result[0]["supplyTransferAllocations"][0]["state"],
            "needs_review",
        )
        self.assertEqual(
            result[0]["supplyTransferAllocations"][0]["reasonCode"],
            "request_item_snapshot_drift",
        )

    def test_invalid_stored_quantity_equation_fails_closed(self):
        cursor = FakeCursor([allocation(remaining_unallocated_quantity=6)])

        result = attach_supply_allocation_projection(cursor, [visible_request()])

        self.assertEqual(
            result[0]["supplyTransferAllocations"][0]["state"],
            "needs_review",
        )
        self.assertEqual(
            result[0]["supplyTransferAllocations"][0]["reasonCode"],
            "allocation_projection_invalid",
        )

    def test_missing_schema_returns_empty_projection_without_querying_ledger(self):
        cursor = FakeCursor([], table_ready=False)

        result = attach_supply_allocation_projection(cursor, [visible_request()])

        self.assertEqual(result[0]["supplyTransferAllocations"], [])
        self.assertEqual(len(cursor.calls), 1)


if __name__ == "__main__":
    unittest.main()
