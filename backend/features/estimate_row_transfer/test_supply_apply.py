import json
import unittest
from decimal import Decimal

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.plan import (
    build_reviewed_plan,
    normalize_draft_payload,
)
from backend.features.estimate_row_transfer.supply_apply import (
    SupplyApplyError,
    apply_supply_plan,
    normalize_supply_apply_payload,
    prepare_supply_allocations,
)
from backend.features.estimate_row_transfer.test_audit import (
    _sections,
    supply_request_row,
)
from backend.features.estimate_row_transfer.test_plan import (
    supply_mapping,
    supply_report,
)


def supply_plan():
    entries = normalize_draft_payload({
        "reconciliationId": 9,
        "entries": [supply_mapping()],
    })["entries"]
    source_sections = _sections("old-material", name="Смесь", unit="кг")
    snapshots = {(61, 0, 71): {
        "estimateId": 14,
        "estimateVersionId": 71,
        "sectionIndex": 0,
        "itemIndex": 0,
        "itemKey": "old-material",
        "sectionsSha256": sections_sha256(source_sections),
    }}
    report = supply_report()
    report["supplyCandidates"][0]["receivedQuantity"] = 2
    report["supplyCandidates"][0]["protectedQuantity"] = 2
    report["supplyCandidates"][0]["transferableQuantity"] = 8
    return build_reviewed_plan(report, entries, snapshots)


def approved_stored_supply_plan():
    plan = supply_plan()
    return {
        "id": 5,
        "status": "approved",
        "approvedPlanSha256": plan["planSha256"],
        "canonicalPlan": plan,
    }


def supply_entry_row(plan=None):
    plan = plan or supply_plan()
    entry = plan["entries"][0]
    return {
        "id": 8,
        "plan_id": 5,
        "company_id": plan["companyId"],
        "project_id": plan["projectId"],
        "source_kind": entry["sourceKind"],
        "source_id": entry["sourceId"],
        "source_parent_id": entry["sourceParentId"],
        "request_item_index": entry["requestItemIndex"],
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
        "source_total_quantity": Decimal(entry["sourceTotalQuantity"]),
        "source_protected_quantity": Decimal(entry["sourceProtectedQuantity"]),
        "source_available_quantity": Decimal(entry["sourceAvailableQuantity"]),
        "quantity": Decimal(entry["quantity"]),
    }


def request_row(**overrides):
    source = supply_request_row()
    row = {
        "id": source["request_id"],
        "company_id": source["request_company_id"],
        "project_id": 3,
        "project": source["request_project"],
        "status": source["request_status"],
        "work_package": source["request_work_package"],
        "items_json": source["items_json"],
    }
    row.update(overrides)
    return row


def delivery_row(quantity="2", **overrides):
    row = {
        "id": 81,
        "request_id": 61,
        "company_id": 1,
        "material_name": "Смесь",
        "unit": "кг",
        "received_quantity": Decimal(quantity),
    }
    row.update(overrides)
    return row


def snapshot(version_id, estimate_id, item_key):
    sections = _sections(item_key, name="Смесь", unit="кг")
    return {
        "id": version_id,
        "estimate_id": estimate_id,
        "sections_json": json.dumps(sections, ensure_ascii=False),
        "sections_sha256": sections_sha256(sections),
    }


def source_snapshot():
    return snapshot(71, 14, "old-material")


def target_snapshot():
    return snapshot(72, 15, "new-material")


def prior_allocation(quantity="1", **overrides):
    row = {
        "id": 301,
        "entry_id": 7,
        "plan_id": 4,
        "company_id": 1,
        "request_id": 61,
        "request_item_index": 0,
        "allocation_quantity": Decimal(quantity),
    }
    row.update(overrides)
    return row


def allocation_receipt(plan=None, **overrides):
    plan = plan or supply_plan()
    row = {
        "id": 401,
        "entry_id": 8,
        "plan_id": 5,
        "company_id": 1,
        "project_id": 3,
        "plan_sha256": plan["planSha256"],
        "request_id": 61,
        "request_item_index": 0,
        "allocation_quantity": Decimal("3"),
        "applied_at": "2026-08-07 18:00:00+03",
    }
    row.update(overrides)
    return row


class SupplyApplyPayloadTests(unittest.TestCase):
    def test_accepts_only_exact_lowercase_plan_hash(self):
        digest = "a" * 64
        self.assertEqual(
            normalize_supply_apply_payload({"planSha256": digest}),
            {"planSha256": digest},
        )
        for payload in ({}, {"planSha256": digest, "confirm": True},
                        {"planSha256": digest.upper()}, {"planSha256": "a" * 63}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(SupplyApplyError, "supply_apply_payload_invalid"):
                    normalize_supply_apply_payload(payload)


class SupplyApplyPreparationTests(unittest.TestCase):
    def _prepare(self, *, include_prior=False, **overrides):
        stored = approved_stored_supply_plan()
        if include_prior:
            entry = stored["canonicalPlan"]["entries"][0]
            entry["sourceProtectedQuantity"] = "3"
            entry["sourceAvailableQuantity"] = "7"
            entry["quantity"] = "3"
            stored["canonicalPlan"]["planSha256"] = ""
            from backend.features.estimate_row_transfer.plan import calculate_plan_sha256
            stored["canonicalPlan"]["planSha256"] = calculate_plan_sha256(stored["canonicalPlan"])
            stored["approvedPlanSha256"] = stored["canonicalPlan"]["planSha256"]
        values = {
            "stored": stored,
            "supply_entries": [supply_entry_row(stored["canonicalPlan"])],
            "requests": [request_row()],
            "deliveries": [delivery_row()],
            "prior_allocations": [prior_allocation()] if include_prior else [],
            "source_snapshots": [source_snapshot()],
            "target_snapshot": target_snapshot(),
        }
        values.update(overrides)
        return prepare_supply_allocations(**values)

    def test_prepares_ledger_only_open_balance_allocation(self):
        operations = self._prepare()

        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual(operation["entryId"], 8)
        self.assertEqual(operation["requestId"], 61)
        self.assertEqual(operation["requestItemIndex"], 0)
        self.assertEqual(operation["requestedQuantity"], Decimal("10"))
        self.assertEqual(operation["receivedQuantity"], Decimal("2"))
        self.assertEqual(operation["previouslyAllocatedQuantity"], Decimal("0"))
        self.assertEqual(operation["allocationQuantity"], Decimal("3"))
        self.assertEqual(operation["remainingUnallocatedQuantity"], Decimal("5"))
        self.assertRegex(operation["requestItemSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(operation["target"]["materialName"], "Смесь")
        self.assertEqual(operation["target"]["unit"], "кг")
        self.assertEqual(operation["target"]["estimateId"], 15)

    def test_prior_allocation_is_subtracted_from_open_balance(self):
        operation = self._prepare(include_prior=True)[0]

        self.assertEqual(operation["previouslyAllocatedQuantity"], Decimal("1"))
        self.assertEqual(operation["remainingUnallocatedQuantity"], Decimal("4"))

    def test_delivery_or_request_drift_blocks_the_complete_apply(self):
        with self.assertRaisesRegex(SupplyApplyError, "supply_plan_stale"):
            self._prepare(deliveries=[delivery_row("3")])
        with self.assertRaisesRegex(SupplyApplyError, "supply_request_status_closed"):
            self._prepare(requests=[request_row(status="Поставлено")])

    def test_ambiguous_delivery_allocation_and_overallocation_fail_closed(self):
        source = supply_request_row()
        items = json.loads(source["items_json"])
        items.append(dict(items[0]))
        with self.assertRaisesRegex(SupplyApplyError, "supply_delivery_allocation_ambiguous"):
            self._prepare(requests=[request_row(items_json=json.dumps(items, ensure_ascii=False))])

        with self.assertRaisesRegex(SupplyApplyError, "supply_plan_stale"):
            self._prepare(deliveries=[delivery_row("8")])


class SupplyApplyCursor:
    def __init__(self, existing_receipts=None):
        self.calls = []
        self.current = None
        self.receipt_reads = 0
        self.existing_receipts = list(existing_receipts or [])

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        lowered = compact.lower()
        self.calls.append((compact, params))
        if "from public.estimate_row_transfer_entries" in lowered:
            self.current = [supply_entry_row(supply_plan())]
        elif "from public.estimate_row_supply_allocations" in lowered and "request_id=any" not in lowered:
            self.receipt_reads += 1
            self.current = self.existing_receipts if self.receipt_reads == 1 else [allocation_receipt()]
        elif "from public.supply_requests" in lowered:
            self.current = [request_row()]
        elif "from public.supply_deliveries" in lowered:
            self.current = [delivery_row()]
        elif "from public.estimate_row_supply_allocations" in lowered:
            self.current = []
        elif "from public.estimate_versions" in lowered:
            self.current = [source_snapshot(), target_snapshot()]
        elif lowered.startswith("insert into public.estimate_row_supply_allocations"):
            self.current = {"id": 401, "applied_at": "2026-08-07 18:00:00+03"}
        else:
            raise AssertionError("unexpected SQL: " + compact)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return list(self.current or [])


class SupplyApplyTransactionTests(unittest.TestCase):
    actor = {"id": 2, "companyId": 1, "name": "Директор", "role": "директор"}

    def test_first_apply_inserts_only_immutable_allocation_receipt(self):
        cursor = SupplyApplyCursor()

        result = apply_supply_plan(cursor, stored=approved_stored_supply_plan(), actor=self.actor)

        self.assertFalse(result["idempotent"])
        self.assertEqual(result["state"], "supply_allocated")
        self.assertEqual(result["supplyCount"], 1)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("INSERT INTO public.estimate_row_supply_allocations", sql)
        self.assertNotIn("UPDATE public.supply_requests", sql)
        self.assertNotIn("UPDATE public.supply_deliveries", sql)
        self.assertNotIn("supplier_invoices SET", sql)
        self.assertNotIn("warehouse_invoices SET", sql)

    def test_repeated_exact_apply_is_read_only(self):
        cursor = SupplyApplyCursor(existing_receipts=[allocation_receipt()])

        result = apply_supply_plan(cursor, stored=approved_stored_supply_plan(), actor=self.actor)

        self.assertTrue(result["idempotent"])
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertNotIn("INSERT INTO public.estimate_row_supply_allocations", sql)

    def test_partial_existing_receipts_fail_before_any_insert(self):
        cursor = SupplyApplyCursor(existing_receipts=[allocation_receipt(entry_id=999)])

        with self.assertRaisesRegex(SupplyApplyError, "supply_apply_partial_state"):
            apply_supply_plan(cursor, stored=approved_stored_supply_plan(), actor=self.actor)

        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertNotIn("INSERT INTO public.estimate_row_supply_allocations", sql)


if __name__ == "__main__":
    unittest.main()
